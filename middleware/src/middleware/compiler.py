"""The server-side protocol compiler.

Turns accepted design moves into a protocol draft. **Pure function**: no LLM,
no clock, no randomness — replaying the same accepted moves against the same
base yields a byte-identical draft (F3.1). The conversation proposes moves;
only this deterministic step produces YAML. The protocol stays the sole
document of record (FR-PROT-1); this emits *drafts*, applied only on approval.

Two kinds of move compile here:

- **Template application** (`kind: "choose-template"`, patch carries
  ``templateId`` + ``parameters``): instantiates a registry template into a
  *complete, valid* protocol (the F1.1 path — a conversation reaches a
  validating protocol without leaving the surface). The compiler treats the
  instantiation as the draft's base.
- **Free-text refinements** (append/set into the eight draft sections,
  mirroring the client-side ``compiler.ts``): accumulate research questions,
  conditions, measures, etc. Without a template these produce a *scaffold*
  whose missing mandatory sections are named (F1.3 — never a silent gap),
  not a valid protocol; with a template they refine the instantiated base.

Every compile runs ``protocol validate`` (FR-CONV-3.2): a move that would
break the schema surfaces as errors the conversation shows as a turn (F3.2),
never a silently-invalid draft.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

import yaml
from protocol.loader import validate_protocol

#: The eight draft sections, mirroring the client model (``platform/src/lib/
#: types.ts``). Order is fixed for deterministic rendering.
SECTIONS: tuple[str, ...] = (
    "researchQuestions",
    "design",
    "participants",
    "conditions",
    "measures",
    "instruments",
    "statisticalPlan",
    "ethics",
)

#: The mandatory protocol sections a valid draft must fill (FR-PROT-1).
MANDATORY_SLOTS: tuple[str, ...] = SECTIONS


@dataclass(frozen=True)
class Slot:
    """One thing a protocol needs before it can be run, named the way a
    researcher would name it.

    The eight conversation :data:`SECTIONS` are how a researcher *talks*; they
    are not what the protocol schema requires, and the two were never the same
    list. ``measures`` has no protocol field at all, while ``session
    .durationMinutes``, ``participants.planned`` and ``study.title`` are
    required and were never asked about. So a conversation could fill all
    eight sections, be told nothing was outstanding, and still fail to
    compile - the gap this model closes.
    """

    #: Stable id, and the dotted protocol path this slot fills.
    path: tuple[str, ...]
    #: What it is, in the researcher's words. This is the text they see.
    label: str
    #: The question that fills it, asked one at a time.
    question: str
    #: How the slot is filled. ``"text"``/``"integer"``/``"enum"`` slots take a
    #: single value and can be written by a ``set-field`` move; ``"derived"``
    #: ones are built by other move kinds (a template, an instrument move, a
    #: prescription) and must never be poked at directly.
    value_type: str = "derived"
    #: For ``"enum"``: the only values the schema accepts.
    choices: tuple[str, ...] = ()

    @property
    def fillable(self) -> bool:
        """Whether a ``set-field`` move may write this slot."""
        return self.value_type != "derived"

    @property
    def key(self) -> str:
        return ".".join(self.path)


#: Everything a protocol needs from the conversation, in the order it is worth
#: asking about. Derived from the schema's own ``required`` lists - a slot here
#: exists because the protocol genuinely cannot validate without it.
#:
#: ``study.id``, ``study.researchers``, ``phases`` and ``protocolVersion`` are
#: absent on purpose: they are structural, the platform fills them, and asking
#: a researcher for them would be ceremony.
PROTOCOL_SLOTS: tuple[Slot, ...] = (
    Slot(
        ("researchQuestions",),
        "the research question",
        "What question is this study trying to answer?",
    ),
    Slot(
        ("participants", "design"),
        "the design",
        "Does each participant do every condition, or only one?",
        value_type="enum",
        choices=("within-subjects", "between-subjects"),
    ),
    Slot(
        ("conditions",),
        "what is being compared",
        "What are the conditions you're comparing?",
    ),
    Slot(
        ("participants", "counterbalanced"),
        "whether condition order is counterbalanced",
        "Will you counterbalance the order participants meet the conditions in?",
        value_type="boolean",
    ),
    Slot(
        ("participants", "planned"),
        "how many participants",
        "How many participants can you realistically recruit?",
        value_type="integer",
    ),
    Slot(
        ("session", "taskDescription"),
        "what participants will do",
        "What will participants actually be doing in a session?",
        value_type="text",
    ),

    Slot(
        ("session", "durationMinutes"),
        "how long a session runs",
        "How long is one session, in minutes?",
        value_type="integer",
    ),
    Slot(
        ("instruments",),
        "what will be captured",
        "What should the editor capture while they work?",
    ),
    Slot(
        ("analysisPlan",),
        "the analysis plan",
        "Which analysis answers your question?",
    ),
    Slot(
        ("study", "title"),
        "the study's name",
        "What should this study be called?",
        value_type="text",
    ),
    Slot(
        ("study", "ethicsRef"),
        "your ethics reference",
        "What's your ethics approval reference?",
        value_type="text",
    ),
)

#: Conversation sections that fill no protocol field of their own. Saying so
#: is the honest alternative to inventing a home for them: measures are
#: *realised* as instruments (what gets captured) and as the analysis plan
#: (what gets tested), and the conversation should drive them there.
SECTIONS_WITHOUT_A_PROTOCOL_FIELD: tuple[str, ...] = ("measures",)


#: The capture config a study gets when nobody has said otherwise - the
#: "sample setup" a researcher adjusts rather than authors. Mirrors what the
#: registry templates instantiate, so the template path and the conversation
#: path produce the same shape.
#:
#: ``instruments`` is the one mandatory slot a researcher cannot answer in a
#: sentence: the schema wants four nested objects with required numeric
#: fields. Asking "what should be captured?" and hoping for that is how the
#: slot stayed permanently open, so the platform proposes this instead and
#: the researcher accepts, rejects, or tunes it like any other move.
def default_capture_instrument(session_minutes: int = 45) -> dict:
    """The standard TERN capture config, sized to the session."""
    return {
        "session": {"durationMinutes": int(session_minutes)},
        "fatigue": {
            "intervalMinutes": 15,
            "waitForPauseSeconds": 4,
            "jitterPercent": 20,
            "quietTailMinutes": 5,
        },
        "stuck": {
            "enabled": True,
            "thresholdSeconds": 90,
            "cooldownMinutes": 5,
        },
        "output": {"httpEndpoint": "http://127.0.0.1:8000/ingest/events"},
    }


#: A runnable starting point for the work itself, offered when a study has
#: conditions but no declared tasks. Deliberately generic maintenance work on
#: the researcher's own repository: the *shape* is what a study needs — one
#: task per condition, comparable in kind, neither tied to a condition — and
#: the content is meant to be replaced.
#:
#: Offering these is not the same as inventing them. A proposed task arrives
#: as a move the researcher accepts, edits, or rejects like any other, and the
#: reply says plainly that it is a placeholder.
SAMPLE_TASKS: tuple[dict, ...] = (
    {
        "id": "task-a",
        "title": "Maintenance task A",
        "description": (
            "A self-contained change on your own codebase: fix a reported "
            "defect, with the failing test provided."
        ),
    },
    {
        "id": "task-b",
        "title": "Maintenance task B",
        "description": (
            "A second change of comparable size and difficulty, so the two "
            "can be swapped between conditions without favouring either."
        ),
    },
)


def sample_tasks(count: int) -> list[dict]:
    """``count`` starter tasks — one per condition, so a within-subjects
    participant never has to repeat one."""
    out = []
    for i in range(max(count, 1)):
        base = SAMPLE_TASKS[i % len(SAMPLE_TASKS)]
        suffix = "" if i < len(SAMPLE_TASKS) else f"-{i + 1}"
        out.append(
            {
                **base,
                "id": f"{base['id']}{suffix}",
                "title": f"{base['title']}{suffix}",
            }
        )
    return out


def _read_path(draft: dict, path: tuple[str, ...]) -> object:
    node: object = draft
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _is_supplied(value: object) -> bool:
    """Whether a slot actually holds something the researcher gave us.

    ``None``, ``""``, ``[]`` and ``{}`` are all absent. A scaffold used to
    write ``planned: 1`` and ``taskDescription: "draft"`` rather than leave
    them out, which is why an obviously incomplete draft could report itself
    as schema-valid: the invented values were the ones that never complained.
    """
    if value is None:
        return False
    if isinstance(value, str | list | dict | tuple):
        return len(value) > 0
    return True


def task_recommendation(draft: dict) -> str:
    """Whether this draft should declare tasks, and why — or "" if it is fine.

    Tasks are not a mandatory slot. Every registry template describes its
    work in ``session.taskDescription`` and validates without them, so
    requiring them would invalidate the whole repertoire overnight and force
    a decision the researcher may not be ready to make.

    They are, though, the difference between a study whose data can answer
    "which task was this?" and one whose data cannot — so a draft that would
    benefit says so, once, rather than staying quiet and letting the gap
    surface after collection.
    """
    conditions = draft.get("conditions") or []
    tasks = draft.get("tasks") or []
    participants = draft.get("participants") or {}
    within = participants.get("design") == "within-subjects"
    if not conditions:
        return ""
    if not tasks:
        if within:
            return (
                "This study has no declared tasks, so every session runs the "
                "same undifferentiated work. In a within-subjects design that "
                "means each participant meets the same task twice and the "
                "second time they already know it — declare one task per "
                "condition and the platform will counterbalance which task "
                "goes with which."
            )
        return (
            "This study has no declared tasks. Declaring them makes each "
            "session assignable to specific work and every event "
            "attributable to it, rather than to the study as a whole."
        )
    if within and len(tasks) < len(conditions):
        return (
            f"{len(tasks)} task(s) across {len(conditions)} conditions: "
            "participants will have to repeat one. One task per condition "
            "keeps the comparison clean."
        )
    return ""


def unresolved_slots(draft: dict) -> list[Slot]:
    """The slots this draft still cannot answer for, in ask order."""
    return [s for s in PROTOCOL_SLOTS if not _is_supplied(_read_path(draft, s.path))]


@dataclass
class MoveTrace:
    """One accepted move's contribution to the draft (the FR-CONV-6 chain
    link: move → grounding → the protocol section it touched). ``grounding``
    is the move's citation refs, or ``["none"]`` for an unsourced move — so
    the elicitation record shows how sure we are of each change, honesty
    recorded not merely displayed (F2.3)."""

    move_id: str
    kind: str
    section: str
    grounding: list[str]


@dataclass
class CompileResult:
    """The outcome of a compile: the draft protocol, its YAML, a diff from the
    base, whether it validates, and — when it doesn't — the errors (F3.2) and
    the named unresolved slots (F1.3)."""

    draft: dict
    yaml: str
    diff: str
    valid: bool
    errors: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    #: Non-blocking honesty notes — e.g. a template move whose hallucinated
    #: parameters were ignored, or a broken later template move that was
    #: skipped in favour of an earlier working one. Never silent (F1.3).
    warnings: list[str] = field(default_factory=list)
    template_id: str | None = None
    template_version: int | None = None
    #: Per-move grounding trace, in application order (F6.1 chain, F2.3).
    trace: list[MoveTrace] = field(default_factory=list)


def empty_sections() -> dict[str, list]:
    return {s: [] for s in SECTIONS}


def _as_section_items(value: object) -> list[str]:
    """A patch value as the string items it contributes to a section.

    Every list-valued protocol section holds strings, but an LLM-proposed
    move sometimes packs a list into one value ("Two conditions: A vs. B"
    arriving as ``["A", "B"]``) or a bare number — flatten and stringify so
    an accepted move lands as valid section entries instead of failing the
    whole draft with a type error nobody can un-accept."""
    items = value if isinstance(value, list) else [value]
    return [i if isinstance(i, str) else str(i) for i in items if i is not None]


def compile_sections(moves: list[dict]) -> dict[str, list]:
    """Fold accepted moves' patches into the section model. Pure and
    deterministic — the same moves always yield the same sections. Mirrors
    the client ``compileAll``; rejecting a move (status != accepted) simply
    leaves it out, so re-folding removes its effect cleanly."""
    sections = empty_sections()
    for move in moves:
        if move.get("status") != "accepted":
            continue
        patch = move.get("patch")
        if not patch:  # caution moves carry no patch
            continue
        section = patch.get("section")
        if section not in sections:
            continue
        op = patch.get("op", "append")
        items = _as_section_items(patch.get("value"))
        if op == "append":
            for item in items:
                if item not in sections[section]:
                    sections[section].append(item)
        elif op == "set":
            sections[section] = items
    return sections


def _build_trace(moves: list[dict]) -> list[MoveTrace]:
    """The grounding trace for every accepted move, in order. A caution
    (no patch) still traces — its grounding is why the researcher was
    warned — targeting the section it advised on."""
    trace = []
    for move in moves:
        if move.get("status") != "accepted":
            continue
        patch = move.get("patch") or {}
        section = patch.get("section") or move.get("target", "")
        refs = [g.get("ref", "") for g in move.get("grounding", []) if g.get("ref")]
        trace.append(
            MoveTrace(
                move_id=move.get("moveId", ""),
                kind=move.get("kind", ""),
                section=section,
                grounding=refs or ["none"],
            )
        )
    return trace


def _accepted_template_moves(moves: list[dict]) -> list[dict]:
    """Accepted template-application moves, in order. The last one that
    actually instantiates wins (a later choice supersedes an earlier one —
    deterministic); one that can't instantiate is reported and skipped,
    never allowed to crash the compile — an accepted move can't be
    re-decided, so a single bad template choice must not wedge the study."""
    return [
        m
        for m in moves
        if m.get("status") == "accepted"
        and m.get("kind") == "choose-template"
        and (m.get("patch") or {}).get("templateId")
    ]


def _instantiate_leniently(patch: dict) -> tuple[dict, list[str]]:
    """Instantiate a template patch, tolerating invented parameter names.

    An LLM-proposed move may carry parameters the template never declared;
    dropping them (with a note) keeps an otherwise-sound template choice
    compilable instead of failing the whole draft. Everything else — unknown
    template id, missing required parameter, out-of-bounds value, invalid
    fill — still raises ``TemplateError`` for the caller to report.
    """
    from middleware import template_registry

    template_id = patch["templateId"]
    version = patch.get("templateVersion")
    parameters = dict(patch.get("parameters") or {})
    template = template_registry.load_template(template_id, version)
    declared = set(template.get("parameters", {}))
    notes = []
    unknown = sorted(set(parameters) - declared)
    if unknown:
        for name in unknown:
            parameters.pop(name)
        notes.append(
            f"{template_id}: ignored parameter(s) {', '.join(unknown)} "
            "the template doesn't declare"
        )
    instantiated = template_registry.instantiate_template(
        template_id, parameters, version=version
    )
    return instantiated, notes


def _scaffold_from_sections(sections: dict[str, list]) -> dict:
    """Build a protocol from free-text sections alone (no template).

    Deliberately a *scaffold*: it will fail validation until the mandatory
    slots are filled, and that failure is the F1.3 "named unresolved slots"
    signal, not an error to hide.

    Crucially it invents nothing. An earlier version wrote ``planned: 1``,
    ``durationMinutes: 1`` and ``taskDescription: "draft"`` so the document
    would have the right *shape*, which meant the three values a researcher
    most needs to supply were the three that never raised an error. A draft
    that quietly claims one participant doing a task called "draft" for one
    minute is worse than one that says it doesn't know yet - so absent values
    stay absent, and :func:`unresolved_slots` names them.
    """
    draft: dict = {
        # Current schema version - every real protocol (templates, examples)
        # is on 4 since the kite->tern rename.
        "protocolVersion": 4,
        # Structural, and the platform's to fill: a draft is identified by the
        # study it belongs to, and phases are inert since the lifecycle board
        # was removed (the schema still requires the key).
        "study": {"id": "draft", "researchers": ["Researcher"]},
        "phases": [{"name": "design", "gates": []}],
    }
    if sections["researchQuestions"]:
        draft["researchQuestions"] = [
            {"id": f"RQ-{i + 1}", "text": t}
            for i, t in enumerate(sections["researchQuestions"])
        ]
    if sections["conditions"]:
        draft["conditions"] = list(sections["conditions"])
    return draft


def _apply_instrument_moves(draft: dict, moves: list[dict]) -> None:
    """Apply accepted instrument moves onto the draft in place — the FR-CONV-4.4
    "instrument evolution rides the same path" contract. Instruments is a dict
    section (not one of the eight list-valued sections), so these moves don't
    fold into ``compile_sections``; they add or replace a whole instrument
    config, or deep-set one field (a threshold/interval tweak, F4.2).

    Deterministic: applied in move order, last write per target wins. Adding an
    instrument is a new data stream (consent-relevant, F4.1); a deep-set of a
    numeric threshold is not (``evolution.consent_relevance`` draws that line).
    """
    # Only materialise the key if a move actually fills it. Creating an empty
    # ``instruments: {}`` made the draft *look* like it had the section while
    # the schema rejected it, and buried the real gap under a schema message
    # ("{} is not valid under any of the given schemas") no researcher can act
    # on. An absent key is named by :func:`unresolved_slots` instead.
    instruments = draft.get("instruments")
    if not isinstance(instruments, dict):
        instruments = None
    for move in moves:
        if move.get("status") != "accepted":
            continue
        patch = move.get("patch") or {}
        if patch.get("section") != "instruments":
            continue
        name = patch.get("name")
        if not name:
            continue
        op = patch.get("op")
        if instruments is None:
            instruments = draft["instruments"] = {}
        if op in ("add-instrument", "set-instrument"):
            instruments[name] = patch.get("config") or {}
        elif op == "reconfigure":
            target = instruments.setdefault(name, {})
            path = list(patch.get("path") or [])
            for key in path[:-1]:
                nxt = target.get(key)
                if not isinstance(nxt, dict):
                    nxt = {}
                    target[key] = nxt
                target = nxt
            if path:
                target[path[-1]] = patch.get("value")


#: Slots a ``set-field`` move is allowed to write, by dotted key. A move
#: naming anything else is refused: the conversation may fill the protocol's
#: declared gaps and nothing more, so a model cannot invent structure by
#: writing a path the schema never had.
FILLABLE_SLOTS: dict[str, Slot] = {s.key: s for s in PROTOCOL_SLOTS if s.fillable}


def _coerce(slot: Slot, value: object) -> object | None:
    """A move's value as the slot's type, or None if it cannot be one.

    A model asked for a participant count will sometimes answer ``"24"``, and
    occasionally ``"24 participants"``. The first is the same answer in the
    wrong type and is accepted; the second is not a number and is refused
    rather than guessed at, because a silently mangled sample size is worse
    than a slot that stays open.
    """
    if slot.value_type == "integer":
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 1 else None
        if isinstance(value, str) and value.strip().isdigit():
            return int(value) or None
        return None
    if slot.value_type == "boolean":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("true", "yes", "y", "1"):
            return True
        if text in ("false", "no", "n", "0"):
            return False
        return None
    if slot.value_type == "enum":
        text = str(value).strip().lower()
        return text if text in slot.choices else None
    text = str(value).strip() if value is not None else ""
    return text or None


def _apply_field_moves(draft: dict, moves: list[dict]) -> list[str]:
    """Write accepted ``set-field`` moves into the draft; returns warnings.

    This is the mechanism the conversation was missing. The eight sections are
    all list-appends, so there was no way to say "planned: 24" at all - which
    is why a template was the only route to a valid protocol, however much the
    researcher typed.

    Deterministic and last-write-wins, like every other move kind. A move for
    an unknown slot, or one whose value cannot be the slot's type, is recorded
    as a warning and skipped - never applied, never silent.
    """
    warnings: list[str] = []
    for move in moves:
        if move.get("status") != "accepted":
            continue
        patch = move.get("patch") or {}
        if patch.get("op") != "set-field":
            continue
        key = ".".join(str(p) for p in patch.get("path") or [])
        slot = FILLABLE_SLOTS.get(key)
        if slot is None:
            warnings.append(
                f"ignored a set-field move for {key or '(no path)'!r}: "
                "not one of the protocol's fillable slots"
            )
            continue
        value = _coerce(slot, patch.get("value"))
        # ``False`` is a perfectly good answer to "counterbalanced?", so the
        # refusal signal is `None` specifically, never falsiness.
        if value is None:
            warnings.append(
                f"ignored {slot.label} = {patch.get('value')!r}: "
                f"not a valid {slot.value_type} for {slot.key}"
            )
            continue
        node = draft
        for part in slot.path[:-1]:
            nxt = node.get(part)
            if not isinstance(nxt, dict):
                nxt = {}
                node[part] = nxt
            node = nxt
        node[slot.path[-1]] = value
    return warnings


def _refine(protocol: dict, sections: dict[str, list]) -> dict:
    """Apply free-text refinements onto a template-instantiated base protocol.
    Only additive, non-destructive edits — appending research questions the
    researcher added in conversation, and union-ing conditions. The template's
    prescribed statistics and instruments are authoritative and untouched."""
    out = yaml.safe_load(yaml.safe_dump(protocol))  # deep copy, plain types
    existing_rq = {rq.get("text") for rq in out.get("researchQuestions", [])}
    next_i = len(out.get("researchQuestions", []))
    for t in sections["researchQuestions"]:
        if t not in existing_rq:
            next_i += 1
            out.setdefault("researchQuestions", []).append(
                {"id": f"RQ-{next_i}", "text": t}
            )
    for c in sections["conditions"]:
        if c not in out.get("conditions", []):
            out.setdefault("conditions", []).append(c)
    return out


def _apply_task_moves(draft: dict, moves: list[dict]) -> list[str]:
    """Compile accepted ``declare-task`` moves into ``tasks`` (schema v5).

    A task is the unit of work a session is assigned and its data attributed
    to, so it has to be addressable: an id, a title, and optionally what the
    participant is asked to do, how long it should take, where the materials
    live, and which conditions it may run under.

    ``session.taskDescription`` stays as the study's prose summary - the two
    are not redundant. One says what the study is about; the others say what
    each session actually runs.

    Deterministic and last-write-wins per id, like every other move kind. A
    task with no usable id or title is warned about and skipped, never
    written half-formed.
    """
    warnings: list[str] = []
    tasks: dict[str, dict] = {t["id"]: dict(t) for t in draft.get("tasks") or []}
    for move in moves:
        if move.get("status") != "accepted" or move.get("kind") != "declare-task":
            continue
        patch = move.get("patch") or {}
        task_id = _slugify(patch.get("id") or patch.get("title") or "")
        title = str(patch.get("title") or "").strip()
        if not task_id or not title:
            warnings.append(
                "ignored a task with no usable id or title: a task has to be "
                "nameable to be assigned"
            )
            continue
        task: dict = {"id": task_id, "title": title}
        for key in ("description", "materials"):
            value = str(patch.get(key) or "").strip()
            if value:
                task[key] = value
        minutes = patch.get("minutes")
        if isinstance(minutes, str) and minutes.strip().isdigit():
            minutes = int(minutes)
        if isinstance(minutes, int) and not isinstance(minutes, bool) and minutes >= 1:
            task["minutes"] = minutes
        conditions = patch.get("conditions")
        if isinstance(conditions, list):
            named = [str(c).strip() for c in conditions if str(c).strip()]
            if named:
                task["conditions"] = named
        tasks[task_id] = task
    if tasks:
        draft["tasks"] = list(tasks.values())
        # `tasks` only exists from v5. A draft that declares them has to say
        # so, or it fails validation against the version it claims to be.
        if int(draft.get("protocolVersion") or 0) < 5:
            draft["protocolVersion"] = 5
    return warnings


#: Task ids are lowercase, hyphenated, and stable - they are stamped onto
#: every event the task produces, so they have to survive a round trip
#: through a filename, a CSV column, and a URL.
_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_STRIP.sub("-", str(text).strip().lower()).strip("-")
    return slug[:48]


def _apply_analysis_moves(draft: dict, moves: list[dict]) -> None:
    """Compile accepted ``prescribe-statistics`` moves into ``analysisPlan``.

    The plan is ``[{rq, recipes: [recipeId]}]`` - recipe *ids*, because that is
    what the protocol schema accepts. This used to write
    ``{id, params: {...}}`` objects per the FR-ANA-8 "parameterised recipe"
    contract, a shape the schema has no version of: every accepted prescription
    produced a protocol that could not validate. Nothing emitted the move, so
    the bug never fired - but ``analysisPlan`` is a slot the conversation now
    has to be able to fill, which means this is the path that fills it.

    A recipe's parameters and its figure form are not protocol content; they
    are already surfaced on the turn (``prescription``, ``figureSuggestions``)
    for the researcher to read. Deterministic: recipe ids are appended once,
    in move order.
    """
    plan = draft.get("analysisPlan") or []
    plan_by_rq: dict[str, dict] = {}
    for entry in plan:
        plan_by_rq.setdefault(entry["rq"], entry)

    for move in moves:
        if move.get("status") != "accepted" or move.get("kind") != (
            "prescribe-statistics"
        ):
            continue
        patch = move.get("patch") or {}
        recipe_id = patch.get("recipeId")
        if not recipe_id:
            continue
        rq = patch.get("rq") or "RQ-1"
        entry = plan_by_rq.setdefault(rq, {"rq": rq, "recipes": []})
        if recipe_id not in entry["recipes"]:
            entry["recipes"].append(recipe_id)

    # As with instruments: an empty plan is an unfilled slot, not an empty
    # list the schema then rejects on its own terms.
    if plan_by_rq:
        draft["analysisPlan"] = list(plan_by_rq.values())


_REQUIRED_PROPERTY = re.compile(r"^'([^']+)' is a required property$")


def _error_target(error: str) -> tuple[str, ...] | None:
    """The protocol path a validator message is about, or None if unparseable.

    ``validate_protocol`` returns ``"<dotted path>: <message>"``. A missing key
    is reported against its *parent* ("study: 'title' is a required
    property"), so the named property is appended to reconstruct the path the
    researcher would recognise.
    """
    head, _, message = error.partition(": ")
    if not message:
        return None
    parts: tuple[str, ...] = (
        () if head == "(document root)" else tuple(head.split("."))
    )
    named = _REQUIRED_PROPERTY.match(message)
    return (*parts, named.group(1)) if named else parts


def _explained_by_slot(error: str, unresolved: list[Slot]) -> bool:
    """Whether an unresolved slot already says what this error says, better.

    Schema messages are precise and useless to a researcher ("instruments: {}
    is not valid under any of the given schemas"). When a slot covers the same
    ground its own words are shown instead. Anything *not* covered is a real,
    unexpected problem and is passed through untouched - the filter can only
    ever remove a message that has a plainer twin.
    """
    target = _error_target(error)
    if target is None:
        return False
    return any(
        target[: len(slot.path)] == slot.path or slot.path[: len(target)] == target
        for slot in unresolved
    )


def compile_moves(moves: list[dict], *, base_yaml: str | None = None) -> CompileResult:
    """Compile accepted moves into a validated protocol draft.

    ``base_yaml`` is the current draft (for the diff); when omitted the diff
    is against the empty draft. Deterministic: same moves + same base → same
    result (F3.1).
    """
    sections = compile_sections(moves)

    # Import here to avoid a hard import cycle at module load (the registry
    # imports the analysis catalogue).
    from middleware.template_registry import TemplateError

    # Walk accepted template moves newest-first and instantiate the first
    # that works. A move whose template can't instantiate (hallucinated id,
    # missing required parameter) is recorded and skipped rather than raised:
    # a 500 here would leave the conversation with no draft and no error.
    template_id = template_version = None
    instantiated = None
    warnings: list[str] = []
    failed: list[str] = []
    for move in reversed(_accepted_template_moves(moves)):
        patch = move["patch"]
        try:
            instantiated, notes = _instantiate_leniently(patch)
        except TemplateError as err:
            failed.append(
                f"choose-template move {move.get('moveId', '?')} "
                f"({patch['templateId']}) could not be applied: {err}"
            )
            continue
        warnings.extend(notes)
        break

    if instantiated:
        template_id = instantiated["templateId"]
        template_version = instantiated["templateVersion"]
        draft = _refine(instantiated["protocol"], sections)
        # Later accepted template moves that failed were skipped in favour
        # of this one — say so, but don't block a valid draft on them.
        warnings.extend(failed)
        failed = []
    else:
        draft = _scaffold_from_sections(sections)

    # Instrument moves apply to the dict section directly (F4.1/F4.2), after
    # the base is built so an added instrument survives both paths.
    _apply_instrument_moves(draft, moves)

    # Prescription/figure moves (Phase 22 / Slice C): compile the chosen test
    # and figure into the protocol's analysisPlan as runnable recipe entries.
    _apply_analysis_moves(draft, moves)

    # Declared tasks (schema v5): what participants actually do, as units a
    # session can be assigned and data attributed to.
    warnings.extend(_apply_task_moves(draft, moves))

    # Scalar slot fills (participant count, session length, study title...).
    # Applied last so an explicit answer from the researcher wins over a
    # template's default - they were asked, and they answered.
    warnings.extend(_apply_field_moves(draft, moves))

    new_yaml = yaml.safe_dump(draft, sort_keys=False, default_flow_style=False)
    base = base_yaml or ""
    diff = "".join(
        difflib.unified_diff(
            base.splitlines(keepends=True),
            new_yaml.splitlines(keepends=True),
            fromfile="draft-before",
            tofile="draft-after",
        )
    )

    # The gaps, computed from the draft itself - so this is honest whether or
    # not a template was applied. It used to short-circuit to ``[]`` the moment
    # a template instantiated, which reported "nothing outstanding" for any
    # slot the template happened to leave empty.
    outstanding = unresolved_slots(draft)
    unresolved = [slot.label for slot in outstanding]
    errors = failed + [
        err
        for err in validate_protocol(draft)
        if not _explained_by_slot(err, outstanding)
    ]

    return CompileResult(
        draft=draft,
        yaml=new_yaml,
        diff=diff,
        # An outstanding slot is a reason the draft cannot be applied, exactly
        # as a schema error is. Validity must not be computable from ``errors``
        # alone now that a slot's plainer wording *replaces* its schema
        # message - that would make filtering an error look like fixing one.
        valid=not errors and not unresolved,
        errors=errors,
        unresolved=unresolved,
        warnings=warnings,
        template_id=template_id,
        template_version=template_version,
        trace=_build_trace(moves),
    )
