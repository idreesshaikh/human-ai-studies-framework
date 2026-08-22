"""The server-side protocol compiler."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

import yaml
from protocol.loader import validate_protocol

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

MANDATORY_SLOTS: tuple[str, ...] = SECTIONS


@dataclass(frozen=True)
class Slot:
    """
    One thing a protocol needs before it can be run, named the way a researcher would
    name it.
    """

    path: tuple[str, ...]
    label: str
    question: str
    # ``"text"``/``"integer"``/``"enum"`` slots take a single value and can be written
    # by a ``set-field`` move; ``"derived"`` ones are built by other move kinds (a
    # template, an instrument move, a prescription) and must never be poked at directly.
    value_type: str = "derived"
    choices: tuple[str, ...] = ()

    @property
    def fillable(self) -> bool:
        """Whether a ``set-field`` move may write this slot."""
        return self.value_type != "derived"

    @property
    def key(self) -> str:
        return ".".join(self.path)


# Derived from the schema's own ``required`` lists - a slot here exists because the
# protocol genuinely cannot validate without it.
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

SECTIONS_WITHOUT_A_PROTOCOL_FIELD: tuple[str, ...] = ("measures",)


# ``instruments`` is the one mandatory slot a researcher cannot answer in a sentence:
# the schema wants four nested objects with required numeric fields.
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


# Deliberately generic maintenance work on the researcher's own repository: the *shape*
# is what a study needs  -  one task per condition, comparable in kind, neither tied to
# a condition  -  and the content is meant to be replaced.
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
    """
    ``count`` starter tasks  -  one per condition, so a within-subjects participant
    never has to repeat one.
    """
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
    """Whether a slot actually holds something the researcher gave us."""
    if value is None:
        return False
    if isinstance(value, str | list | dict | tuple):
        return len(value) > 0
    return True


def task_recommendation(draft: dict) -> str:
    """Whether this draft should declare tasks, and why  -  or "" if it is fine."""
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
                "second time they already know it  -  declare one task per "
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
    """
    One accepted move's contribution to the draft (the FR-CONV-6 chain link: move →
    grounding → the protocol section it touched).
    """

    move_id: str
    kind: str
    section: str
    grounding: list[str]


@dataclass
class CompileResult:
    """
    The outcome of a compile: the draft protocol, its YAML, a diff from the base,
    whether it validates, and  -  when it doesn't  -  the errors (F3.2) and the named
    unresolved slots (F1.3).
    """

    draft: dict
    yaml: str
    diff: str
    valid: bool
    errors: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    # Never silent (F1.3).
    warnings: list[str] = field(default_factory=list)
    template_id: str | None = None
    template_version: int | None = None
    trace: list[MoveTrace] = field(default_factory=list)


def empty_sections() -> dict[str, list]:
    return {s: [] for s in SECTIONS}


def _as_section_items(value: object) -> list[str]:
    """A patch value as the string items it contributes to a section."""
    items = value if isinstance(value, list) else [value]
    return [i if isinstance(i, str) else str(i) for i in items if i is not None]


def compile_sections(moves: list[dict]) -> dict[str, list]:
    """Fold accepted moves' patches into the section model."""
    sections = empty_sections()
    for move in moves:
        if move.get("status") != "accepted":
            continue
        patch = move.get("patch")
        if not patch:
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
    """The grounding trace for every accepted move, in order."""
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
    """Accepted design-shape moves (single template or a merge), in order."""
    return [
        m
        for m in moves
        if m.get("status") == "accepted"
        and m.get("kind") in ("choose-template", "merge-templates")
        and (
            (m.get("patch") or {}).get("templateId")
            or (m.get("patch") or {}).get("templateIds")
        )
    ]


def _instantiate_leniently(patch: dict) -> tuple[dict, list[str]]:
    """Instantiate a template patch, tolerating invented parameter names."""
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


def _seeded_draft(base_yaml: str | None) -> dict | None:
    """A protocol to start from when this call's moves establish no template
    of their own  -  either a study created from a "derive from paper" or
    "merge templates" promotion (seeded at creation, `app.py`'s
    `create_study`), or an in-progress study's own last compiled state.
    Without this, a freshly seeded study's very first auto-compile (zero
    moves yet) silently discarded the seed for a blank scaffold  -  the
    promotion flow's own copy promises "this design seeds its draft",
    which was false the moment the researcher landed on the page."""
    if not base_yaml:
        return None
    try:
        parsed = yaml.safe_load(base_yaml)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("study"), dict):
        return None
    return parsed


def _scaffold_from_sections(sections: dict[str, list]) -> dict:
    """Build a protocol from free-text sections alone (no template)."""
    draft: dict = {
        "protocolVersion": 4,
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
    """
    Apply accepted instrument moves onto the draft in place  -  the FR-CONV-4.4
    "instrument evolution rides the same path" contract.
    """
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


# A move naming anything else is refused: the conversation may fill the protocol's
# declared gaps and nothing more, so a model cannot invent structure by writing a path
# the schema never had.
FILLABLE_SLOTS: dict[str, Slot] = {s.key: s for s in PROTOCOL_SLOTS if s.fillable}


def _coerce(slot: Slot, value: object) -> object | None:
    """A move's value as the slot's type, or None if it cannot be one."""
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
    """Write accepted ``set-field`` moves into the draft; returns warnings."""
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
        # ``False`` is a perfectly good answer to "counterbalanced?", so the refusal
        # signal is `None` specifically, never falsiness.
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
    """Apply free-text refinements onto a template-instantiated base protocol."""
    out = yaml.safe_load(yaml.safe_dump(protocol))
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
    """Compile accepted ``declare-task`` moves into ``tasks`` (schema v5)."""
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
        if int(draft.get("protocolVersion") or 0) < 5:
            draft["protocolVersion"] = 5
    return warnings


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_STRIP.sub("-", str(text).strip().lower()).strip("-")
    return slug[:48]


def _apply_analysis_moves(draft: dict, moves: list[dict]) -> None:
    """Compile accepted ``prescribe-statistics`` moves into ``analysisPlan``."""
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

    if plan_by_rq:
        draft["analysisPlan"] = list(plan_by_rq.values())


_REQUIRED_PROPERTY = re.compile(r"^'([^']+)' is a required property$")


def _error_target(error: str) -> tuple[str, ...] | None:
    """The protocol path a validator message is about, or None if unparseable."""
    head, _, message = error.partition(": ")
    if not message:
        return None
    parts: tuple[str, ...] = (
        () if head == "(document root)" else tuple(head.split("."))
    )
    named = _REQUIRED_PROPERTY.match(message)
    return (*parts, named.group(1)) if named else parts


def _explained_by_slot(error: str, unresolved: list[Slot]) -> bool:
    """Whether an unresolved slot already says what this error says, better."""
    target = _error_target(error)
    if target is None:
        return False
    return any(
        target[: len(slot.path)] == slot.path or slot.path[: len(target)] == target
        for slot in unresolved
    )


def compile_moves(moves: list[dict], *, base_yaml: str | None = None) -> CompileResult:
    """Compile accepted moves into a validated protocol draft."""
    sections = compile_sections(moves)

    # A move whose template(s) can't instantiate (hallucinated id, missing required
    # parameter, an invalid merge) is recorded and skipped rather than raised: a 500
    # here would leave the conversation with no draft and no error.
    from middleware import template_registry
    from middleware.template_registry import TemplateError

    template_id = template_version = None
    instantiated = None
    warnings: list[str] = []
    failed: list[str] = []
    for move in reversed(_accepted_template_moves(moves)):
        patch = move["patch"]
        try:
            if move["kind"] == "merge-templates":
                instantiated = template_registry.merge_templates(
                    list(patch.get("templateIds") or []), {}
                )
                notes: list[str] = []
            else:
                instantiated, notes = _instantiate_leniently(patch)
        except TemplateError as err:
            label = (
                patch.get("templateId")
                or "+".join(patch.get("templateIds") or [])
                or "?"
            )
            failed.append(
                f"{move['kind']} move {move.get('moveId', '?')} "
                f"({label}) could not be applied: {err}"
            )
            continue
        warnings.extend(notes)
        break

    if instantiated:
        template_id = instantiated.get("templateId")
        template_version = instantiated.get("templateVersion")
        draft = _refine(instantiated["protocol"], sections)
        # Later accepted design moves that failed were skipped in favour of this one  -
        # say so, but don't block a valid draft on them.
        warnings.extend(failed)
        failed = []
    else:
        seeded = _seeded_draft(base_yaml)
        draft = (
            _refine(seeded, sections)
            if seeded is not None
            else _scaffold_from_sections(sections)
        )

    _apply_instrument_moves(draft, moves)

    _apply_analysis_moves(draft, moves)

    warnings.extend(_apply_task_moves(draft, moves))

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
        # An outstanding slot is a reason the draft cannot be applied, exactly as a
        # schema error is.
        valid=not errors and not unresolved,
        errors=errors,
        unresolved=unresolved,
        warnings=warnings,
        template_id=template_id,
        template_version=template_version,
        trace=_build_trace(moves),
    )
