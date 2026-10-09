"""The server-side protocol compiler."""

from __future__ import annotations

import difflib
import json
import logging
import re
from dataclasses import dataclass, field

import yaml
from protocol.loader import validate_protocol
from protocol.measure_catalog import apply_catalog_measures

log = logging.getLogger(__name__)

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
VALID_INSTRUMENTS: frozenset[str] = frozenset(
    {"tern", "metrics", "agentCapture", "taskHarness"}
)


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


# Derived from the schema's own ``required`` lists. A slot here exists because the
# protocol genuinely cannot validate without it. Ethics approval is deliberately not
# in this list: the platform can record an ethics status or posture, but it does not
# grant approval and must not make an approval reference a prerequisite for drafting
# or applying a protocol.
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
)

# Optional metadata can be recorded when the researcher has it, without turning an
# external administrative decision into a conversational gate. Keeping this in the
# fillable catalogue preserves old ethics-reference moves and existing protocol
# exports while leaving the required-slot calculation honest.
OPTIONAL_SLOTS: tuple[Slot, ...] = (
    Slot(
        ("participants", "description"),
        "the participant profile",
        "Who are you recruiting for this study?",
        value_type="text",
    ),
    Slot(
        ("study", "ethicsRef"),
        "ethics status or reference",
        "Do you have an ethics status or reference to record?",
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
    One accepted move's contribution to the draft (the chain link: move →
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


def _as_section_items(value: object, *, typed_measures: bool = False) -> list:
    """A patch value as the string items it contributes to a section."""
    items = value if isinstance(value, list) else [value]
    return [
        i if isinstance(i, str) or (typed_measures and isinstance(i, dict)) else str(i)
        for i in items
        if i is not None
    ]


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
        items = _as_section_items(
            patch.get("value"), typed_measures=section == "measures"
        )
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


def _instantiate_leniently(
    patch: dict, sections: dict[str, list] | None = None
) -> tuple[dict, list[str]]:
    """Instantiate a template patch, tolerating invented parameter names.

    A template's default conditions can be placeholders (``control`` and
    ``treatment``). When the researcher named entirely different conditions in
    other accepted moves and the template move did not set them, those fill
    the parameter, so the placeholders are replaced rather than kept beside
    the researcher's conditions. Conditions that merely differ in spelling
    keep the template's spelling (see ``_dedupe_conditions``)."""
    from middleware import template_registry
    from middleware.template_registry import TemplateError

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
            f"Skipped setting(s) the {_template_title(template_id)} design "
            f"doesn't have: {', '.join(unknown)}."
        )
    supplied = dict(parameters)
    named = list((sections or {}).get("conditions") or [])
    if named and "conditions" in declared and "conditions" not in supplied:
        default = template["parameters"]["conditions"].get("default") or []
        placeholders = {str(c).strip().lower() for c in default}
        if not placeholders & {str(c).strip().lower() for c in named}:
            supplied["conditions"] = named
    try:
        instantiated = template_registry.instantiate_template(
            template_id, supplied, version=version
        )
    except TemplateError:
        # The researcher's values do not fit this template's parameter rules
        # (for example a single condition); keep the template's own defaults.
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
        "study": {"id": "draft", "researchers": [RESEARCHER_PLACEHOLDER]},
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


def _accepted_session_minutes(moves: list[dict]) -> int | None:
    """The researcher's accepted ``session.durationMinutes`` slot value, if any."""
    slot = FILLABLE_SLOTS.get("session.durationMinutes")
    found = None
    for move in moves:
        patch = move.get("patch") or {}
        if (
            move.get("status") == "accepted"
            and patch.get("op") == "set-field"
            and list(patch.get("path") or []) == ["session", "durationMinutes"]
        ):
            value = _coerce(slot, patch.get("value")) if slot else None
            if isinstance(value, int):
                found = value
    return found


_MINUTES_IN_TEXT = re.compile(r"\b(\d{1,3})\s*-?\s*(?:minutes?|mins?)\b", re.I)


def _task_text_session_minutes(moves: list[dict]) -> int | None:
    """A session length the researcher wrote into an accepted ``declare-task`` move
    (its fields or its proposal sentence), such as "30 minutes per condition"."""
    found = None
    for move in moves:
        if move.get("status") != "accepted" or move.get("kind") != "declare-task":
            continue
        patch = move.get("patch") or {}
        texts = [patch.get(k) for k in ("description", "title", "materials")]
        texts.append(move.get("proposal"))
        for text in texts:
            match = _MINUTES_IN_TEXT.search(str(text or ""))
            if match and 1 <= int(match.group(1)) <= 480:
                found = int(match.group(1))
                break
    return found


def _stated_tern_minutes(moves: list[dict]) -> bool:
    return any(
        move.get("status") == "accepted"
        and (move.get("patch") or {}).get("name") in ("tern", "taskTimer")
        and _explicit_minutes((move.get("patch") or {}).get("config")) is not None
        for move in moves
    )


def _sync_tern_session_minutes(
    draft: dict, moves: list[dict], slot_minutes: int | None
) -> None:
    """An accepted duration slot also sizes a TERN config the researcher left open
    (for example one a template brought); a duration they stated on the
    instrument itself is left alone."""
    if slot_minutes is None:
        return
    tern = (draft.get("instruments") or {}).get("tern")
    if not isinstance(tern, dict) or not isinstance(tern.get("session"), dict):
        return
    for move in moves:
        patch = move.get("patch") or {}
        if (
            move.get("status") == "accepted"
            and patch.get("name") == "tern"
            and _explicit_minutes(patch.get("config")) is not None
        ):
            return
    tern["session"]["durationMinutes"] = slot_minutes


def _apply_instrument_moves(
    draft: dict, moves: list[dict], session_minutes: int | None = None
) -> list[str]:
    """
    Apply accepted instrument moves onto the draft in place: the
    "instrument evolution rides the same path" contract.
    """
    warnings: list[str] = []
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
            config = patch.get("config") or {}
            # Older model turns called the timestamp helper `taskTimer`, but
            # that is not a protocol instrument. Letting that name through
            # produced an accepted move and an invalid protocol, which made
            # the draft look full while Apply stayed impossible. Task timing
            # is captured by the real TERN instrument; repair the legacy shape
            # at compile time and keep the warning visible to the caller.
            if name == "taskTimer":
                name = "tern"
                config = default_capture_instrument(
                    _session_minutes_from_config(config, default=session_minutes or 45)
                )
                warnings.append(
                    "A task timer is not a capture tool, so the standard TERN "
                    "capture was used instead."
                )
            elif name == "tern":
                config, config_warnings = _normalise_tern_config(
                    config, default_minutes=session_minutes or 45
                )
                warnings.extend(config_warnings)
            elif name not in VALID_INSTRUMENTS:
                warnings.append(
                    f"Left out {name!r}: it is not a capture tool this platform "
                    "supports (use tern, metrics, agentCapture, or taskHarness)."
                )
                continue
            instruments[name] = config
        elif op == "reconfigure":
            if name == "taskTimer":
                name = "tern"
                warnings.append(
                    "A task timer is not a capture tool, so its setting was "
                    "applied to the standard TERN capture."
                )
            elif name not in VALID_INSTRUMENTS:
                warnings.append(
                    f"Left out a setting for {name!r}: it is not a capture tool "
                    "this platform supports."
                )
                continue
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
    return warnings


def _explicit_minutes(config: object) -> int | None:
    """A session duration the config itself states (any nesting), else None."""
    if not isinstance(config, dict):
        return None
    value = config.get("minutes") or config.get("durationMinutes")
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    for nested_key in ("capture", "session"):
        found = _explicit_minutes(config.get(nested_key))
        if found is not None:
            return found
    return None


def _session_minutes_from_config(config: object, default: int = 45) -> int:
    """Read a legacy timer duration without trusting its invalid shape."""
    found = _explicit_minutes(config)
    return found if found is not None else default


def _normalise_tern_config(
    config: object, default_minutes: int = 45
) -> tuple[dict, list[str]]:
    """
    Repair legacy/incomplete TERN add moves into the schema's capture shape.

    Defaults only ever fill what is missing; every supplied value is kept.
    """
    source = config if isinstance(config, dict) else {}
    warnings: list[str] = []
    if isinstance(source.get("capture"), dict):
        source = source["capture"]
        warnings.append(
            "The TERN capture settings were tidied into the standard layout."
        )

    normalized = default_capture_instrument(
        _session_minutes_from_config(config, default=default_minutes)
    )
    required = ("session", "fatigue", "stuck", "output")
    added = [
        f"{section}.{key}"
        for section in required
        for key in normalized[section]
        if not isinstance(source.get(section), dict) or key not in source[section]
    ]
    if added:
        warnings.append("Standard TERN capture settings were added.")

    optional_sections = {"ideHealth", "behavior", "comprehensionProbe"}
    unknown: list[str] = []
    for section, value in source.items():
        if section in normalized:
            if not isinstance(value, dict):
                # A bare placeholder ("standard", true) means "use the standard
                # settings for this section", which is already in place.
                continue
            for key, item in value.items():
                if key in normalized[section]:
                    normalized[section][key] = item
                else:
                    unknown.append(f"{section}.{key}")
        elif section in optional_sections and isinstance(value, dict):
            normalized[section] = value
        else:
            unknown.append(section)
    if unknown:
        warnings.append(
            "Some TERN capture settings are not supported and were left out: "
            + ", ".join(sorted(unknown))
        )
    return normalized, warnings


# A move naming anything else is refused: the conversation may fill the protocol's
# declared gaps and nothing more, so a model cannot invent structure by writing a path
# the schema never had.
FILLABLE_SLOTS: dict[str, Slot] = {
    s.key: s for s in (*PROTOCOL_SLOTS, *OPTIONAL_SLOTS) if s.fillable
}


_VALUE_WORDS = {
    "integer": "a whole number",
    "boolean": "yes or no",
    "enum": "one of the listed choices",
    "text": "text",
}


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
        if key == "comparison":
            values = _legacy_comparison_values(patch.get("value"))
            if values:
                conditions = draft.setdefault("conditions", [])
                for value in values:
                    if value not in conditions:
                        conditions.append(value)
                warnings.append(
                    "The comparison you described was read as the study's conditions."
                )
            else:
                warnings.append("Ignored an empty comparison.")
            continue
        if key == "design.conditionOrder":
            counterbalanced = _legacy_counterbalanced_value(patch.get("value"))
            if counterbalanced is None:
                warnings.append(
                    f"Ignored condition order {patch.get('value')!r}: "
                    "expected counterbalanced or fixed."
                )
            else:
                draft.setdefault("participants", {})["counterbalanced"] = (
                    counterbalanced
                )
                warnings.append(
                    "The condition order was read as your counterbalancing choice."
                )
            continue
        slot = FILLABLE_SLOTS.get(key)
        if slot is None:
            log.info("ignored a set-field move for %r: not a fillable slot", key)
            warnings.append(
                "Ignored a suggested value for a setting the protocol does not have."
            )
            continue
        value = _coerce(slot, patch.get("value"))
        # ``False`` is a perfectly good answer to "counterbalanced?", so the refusal
        # signal is `None` specifically, never falsiness.
        if value is None:
            warnings.append(
                f"Ignored {slot.label} = {patch.get('value')!r}: "
                f"expected {_VALUE_WORDS[slot.value_type]}."
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
        analysis = patch.get("evidenceAnalysis")
        if (
            key == "participants.design"
            and isinstance(analysis, dict)
            and any(g.get("evidence") for g in move.get("grounding", []))
        ):
            # One reviewed choice changes its design and mapped analysis atomically.
            # Other RQs and unrelated accepted choices remain untouched; Undo
            # replays the prior plan rather than destructively rewriting it.
            rq = analysis.get("rq")
            if rq in {r["id"] for r in draft.get("researchQuestions", [])}:
                plan = draft.setdefault("analysisPlan", [])
                entry = next((p for p in plan if p.get("rq") == rq), None)
                if entry is None:
                    entry = {"rq": rq}
                    plan.append(entry)
                entry["recipes"] = analysis.get("recipes", [])
    return warnings


def _legacy_comparison_values(value: object) -> list[str]:
    """Turn an old comparison sentence into named condition values."""
    raw = value if isinstance(value, list) else [value]
    values: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        values.extend(re.split(r"\s+(?:vs\.?|versus)\s+|\r?\n", item, flags=re.I))
    return [item.strip(" ,;") for item in values if item.strip(" ,;")]


def _legacy_counterbalanced_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"fixed", "ordered", "not counterbalanced", "false", "no"}:
        return False
    if "not counter" in text or text in {"unbalanced", "unrandomized", "unrandomised"}:
        return False
    if "counter" in text or text in {"balanced", "randomized", "randomised"}:
        return True
    return None


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
    existing_measures = {
        json.dumps(m, sort_keys=True) for m in (out.get("measures") or [])
    }
    for measure in sections["measures"]:
        if json.dumps(measure, sort_keys=True) not in existing_measures:
            out.setdefault("measures", []).append(measure)
            existing_measures.add(json.dumps(measure, sort_keys=True))
    return out


_PAREN = re.compile(r"\s*\([^)]*\)")


def _measure_core(measure: str) -> str:
    return " ".join(_PAREN.sub("", measure).lower().split())


def _dedupe_measures(draft: dict) -> list[str]:
    """Collapse measures that are the same thing written twice (case, or one being
    the other plus a parenthetical unit), keeping the more specific wording."""
    measures = draft.get("measures")
    if not isinstance(measures, list):
        return []
    kept: list = []
    warnings: list[str] = []
    for measure in measures:
        if not isinstance(measure, str):
            kept.append(measure)
            continue
        core = _measure_core(measure)
        twin = next(
            (
                i
                for i, k in enumerate(kept)
                if isinstance(k, str) and _measure_core(k) == core
            ),
            None,
        )
        if twin is None:
            kept.append(measure)
            continue
        old = kept[twin]
        more_specific = len(_PAREN.findall(measure)) > len(_PAREN.findall(old))
        dropped, keeper = (old, measure) if more_specific else (measure, old)
        kept[twin] = keeper
        warnings.append(f"Dropped the duplicate measure '{dropped}'; kept '{keeper}'")
    kept, combined = _drop_combined_measures(kept)
    warnings.extend(combined)
    draft["measures"] = kept
    return warnings


_WORD = re.compile(r"[a-z0-9]+")
_FILLER_WORDS = frozenset({"and", "or", "the", "of", "a", "an", "&", "plus"})


def _measure_words(measure: str) -> set[str]:
    return set(_WORD.findall(_measure_core(measure))) - _FILLER_WORDS


def _drop_combined_measures(measures: list) -> tuple[list, list[str]]:
    """Drop a measure whose words are all covered by two or more other measures
    (a conjunction such as "A and B" sitting beside A and B)."""
    words = {i: _measure_words(m) for i, m in enumerate(measures) if isinstance(m, str)}
    drop: set[int] = set()
    for i, mine in words.items():
        if not mine:
            continue
        parts = [
            j
            for j, other in words.items()
            if j != i and j not in drop and other and other < mine
        ]
        covered = set().union(*(words[j] for j in parts)) if parts else set()
        if len(parts) >= 2 and covered >= mine:
            drop.add(i)
    warnings = [
        f"Dropped the duplicate measure '{measures[i]}'; its parts are already "
        "listed as separate measures"
        for i in sorted(drop)
    ]
    return [m for i, m in enumerate(measures) if i not in drop], warnings


def _dedupe_conditions(draft: dict) -> None:
    """Drop conditions that repeat an earlier one apart from case or spacing."""
    conditions = draft.get("conditions")
    if not isinstance(conditions, list):
        return
    seen: set[str] = set()
    kept: list = []
    for condition in conditions:
        key = condition.strip().lower() if isinstance(condition, str) else None
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        kept.append(condition)
    draft["conditions"] = kept


def _canonical_task_conditions(draft: dict) -> None:
    """Tasks name conditions the way the protocol's own condition list spells them."""
    conditions = [c for c in draft.get("conditions") or [] if isinstance(c, str)]
    canonical = {c.strip().lower(): c for c in conditions}
    for task in draft.get("tasks") or []:
        named = task.get("conditions")
        if isinstance(named, list):
            task["conditions"] = [
                canonical.get(str(c).strip().lower(), c) for c in named
            ]


def _template_title(template_id: str | None) -> str:
    from middleware import template_registry

    if not template_id:
        return "chosen"
    try:
        return str(template_registry.load_template(template_id).get("title") or "")
    except Exception:  # noqa: BLE001 - a title is only for display
        return ""


RESEARCHER_PLACEHOLDER = "Lead researcher (edit me)"

RECIPE_LABELS: dict[str, str] = {
    "control_arm_audit": "control-arm AI-use audit",
    "typed-measures": "protocol-declared survey scoring",
    "mean-comparison": "mean comparison or ANCOVA",
    "agent-interaction-dynamics": "agent conversation analysis",
    "ai-review-behavior": "AI suggestion review analysis",
    "code-quality-by-condition": "code quality comparison",
    "correlation": "rank correlation",
    "fatigue-by-condition": "fatigue comparison",
    "meyer-fragmentation": "work fragmentation analysis",
    "paired-nonparametric": "paired nonparametric test",
    "paste-behavior": "paste behaviour analysis",
    "stuck-episodes": "stuck episode analysis",
    "task-outcome-by-condition": "task outcome comparison",
    "tlx-debrief": "NASA-TLX debrief analysis",
    "two-group-nonparametric": "two-group nonparametric test",
    "two-proportion": "two-proportion test",
    "ziegler-acceptance-rate": "suggestion acceptance rate analysis",
}

METRIC_SET_LABELS: dict[str, str] = {
    "cognitive-load-9": "NASA-TLX cognitive-load measure set",
    "code-quality-5": "code-quality measure set",
}


def _plain_id(ident: object, labels: dict[str, str]) -> str:
    text = str(ident)
    return labels.get(text) or text.replace("-", " ")


def _template_supplied_notes(
    template_id: str | None,
    skeleton: dict,
    draft: dict,
    sections: dict[str, list],
) -> list[str]:
    """Plain-language notes, one per item the template brought beyond the researcher."""
    stated = set(sections["researchQuestions"])
    title = _template_title(template_id) or str(template_id or "chosen")
    lead = f"From the {title} template: "
    notes: list[str] = []
    for index, rq in enumerate(skeleton.get("researchQuestions") or [], start=1):
        if not isinstance(rq, dict) or rq.get("text") in stated:
            continue
        match = re.search(r"(\d+)\s*$", str(rq.get("id") or ""))
        number = match.group(1) if match else str(index)
        notes.append(
            f'research question {number}, "{rq.get("text")}" '
            "(you did not state it; remove it if unwanted)."
        )
    notes = [lead + n for n in notes[:1]] + [
        "From the template: " + n for n in notes[1:]
    ]
    metric_set = ((skeleton.get("instruments") or {}).get("metrics") or {}).get(
        "metricSet"
    )
    if metric_set:
        notes.append(
            f"From the template: the {_plain_id(metric_set, METRIC_SET_LABELS)}."
        )
    final_plan = {
        str(e.get("rq")): e.get("recipes")
        for e in draft.get("analysisPlan") or []
        if isinstance(e, dict)
    }
    recipes = [
        r
        for e in skeleton.get("analysisPlan") or []
        if isinstance(e, dict) and final_plan.get(str(e.get("rq"))) == e.get("recipes")
        for r in e.get("recipes") or []
    ]
    if recipes:
        labels = [_plain_id(r, RECIPE_LABELS) for r in dict.fromkeys(recipes)]
        notes.append("From the template: the " + " and the ".join(labels) + ".")
    return notes


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
                "Ignored a task with no title: a task needs a name before it "
                "can be assigned."
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


def _legacy_recipe(value: object) -> str | None:
    """Translate pre-v5 free-text statistical moves to a runnable recipe.

    Early conversation records used ``set-field statisticalPlan`` and displayed a
    method sentence, but the protocol has always needed executable recipe ids. Keep
    those records recoverable when a researcher reopens an old study. New turns use
    ``prescribe-statistics`` and never take this compatibility path.
    """
    text = str(value or "").lower()
    if any(
        term in text
        for term in ("paired", "within-subject", "wilcoxon", "signed-rank", "repeated")
    ):
        return "paired-nonparametric"
    return None


def _apply_analysis_moves(draft: dict, moves: list[dict]) -> list[str]:
    """Compile executable and legacy statistical moves into ``analysisPlan``."""
    warnings: list[str] = []
    declared_rqs = [
        str(rq.get("id")) for rq in draft.get("researchQuestions") or [] if rq.get("id")
    ]
    fallback_rq = declared_rqs[0] if declared_rqs else "RQ-1"
    plan = draft.get("analysisPlan") or []
    plan_by_rq: dict[str, dict] = {}
    for entry in plan:
        if not isinstance(entry, dict):
            continue
        rq = _resolve_analysis_rq(draft, entry.get("rq"), None, warnings)
        if rq:
            normalized = dict(entry)
            normalized["rq"] = rq
            plan_by_rq.setdefault(rq, normalized)

    for move in moves:
        if move.get("status") != "accepted":
            continue
        patch = move.get("patch") or {}
        recipe_id = (
            patch.get("recipeId")
            if move.get("kind") == "prescribe-statistics"
            else None
        )
        if recipe_id is not None and not isinstance(recipe_id, str):
            recipe_id = None
        legacy = False
        if recipe_id is None:
            path = patch.get("path") or []
            section = patch.get("section")
            if move.get("kind") in ("set-field", "set-parameter", "add-measure") and (
                path == ["statisticalPlan"] or section == "statisticalPlan"
            ):
                recipe_id = _legacy_recipe(patch.get("value"))
                legacy = recipe_id is not None
        if not recipe_id:
            if not legacy and move.get("kind") == "prescribe-statistics":
                warnings.append(
                    "Ignored an analysis suggestion that did not name "
                    "an analysis to run."
                )
            continue
        rq = _resolve_analysis_rq(draft, patch.get("rq"), fallback_rq, warnings)
        if rq is None:
            continue
        entry = plan_by_rq.setdefault(rq, {"rq": rq, "recipes": []})
        if recipe_id not in entry["recipes"]:
            entry["recipes"].append(recipe_id)
        if legacy:
            warnings.append(
                f"The statistical-plan wording was matched to the {recipe_id} analysis."
            )

    if plan_by_rq:
        draft["analysisPlan"] = list(plan_by_rq.values())
    return warnings


def _resolve_analysis_rq(
    draft: dict,
    requested: object,
    fallback: str | None,
    warnings: list[str],
) -> str | None:
    """Keep analysis entries keyed by declared RQ ids, even for old moves."""
    if requested is None or not str(requested).strip():
        return fallback
    value = str(requested).strip()
    declared = draft.get("researchQuestions") or []
    for rq in declared:
        if not isinstance(rq, dict) or not rq.get("id"):
            continue
        rq_id = str(rq["id"])
        if value == rq_id:
            return rq_id
        if str(rq.get("text") or "").strip().casefold() == value.casefold():
            warnings.append(f"The analysis was matched to research question {rq_id}.")
            return rq_id
    warnings.append(
        f"Ignored analysis target {value!r}: it is not one of the study's "
        "research questions."
    )
    return None


_REQUIRED_PROPERTY = re.compile(r"^'([^']+)' is a required property$")


def _error_target(error: str) -> tuple[str, ...] | None:
    """The protocol path a validator message is about, or None if unparseable."""
    head, _, message = error.partition(": ")
    if not message:
        return None
    parts: tuple[str, ...] = () if head == "(document root)" else tuple(head.split("."))
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


def _since_manual_entry(moves: list[dict]) -> list[dict]:
    """A manual protocol entry replaces every move accepted before it."""
    for i in range(len(moves) - 1, -1, -1):
        move = moves[i]
        if move.get("status") == "accepted" and (move.get("patch") or {}).get("manual"):
            return moves[i:]
    return moves


def compile_moves(moves: list[dict], *, base_yaml: str | None = None) -> CompileResult:
    """Compile accepted moves into a validated protocol draft."""
    moves = _since_manual_entry(moves)
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
                instantiated, notes = _instantiate_leniently(patch, sections)
        except TemplateError as err:
            label = (
                patch.get("templateId")
                or "+".join(patch.get("templateIds") or [])
                or "?"
            )
            failed.append(f"The design '{label}' could not be applied: {err}")
            continue
        warnings.extend(notes)
        break

    skeleton: dict = {}
    if instantiated:
        skeleton = instantiated["protocol"]
        template_id = instantiated.get("templateId")
        template_version = instantiated.get("templateVersion")
        draft = _refine(instantiated["protocol"], sections)
        if patch.get("manual") and isinstance(patch.get("baseProtocol"), dict):
            draft = _refine(patch["baseProtocol"], sections)
            params = patch["parameters"]
            draft["study"].update(id=params["studyId"], title=params["title"])
            draft["conditions"] = params["conditions"]
            draft["participants"].update(
                planned=params["participantPlan"],
                design=patch["design"],
                counterbalanced=patch["counterbalanced"],
            )
            draft.setdefault("session", {}).update(
                durationMinutes=params["sessionMinutes"],
                taskDescription=params["taskDescription"],
            )
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

    manual_patch = next(
        (
            move["patch"]
            for move in moves
            if move.get("status") == "accepted"
            and move.get("kind") == "choose-template"
            and (move.get("patch") or {}).get("manual")
            and isinstance((move.get("patch") or {}).get("researchQuestions"), list)
        ),
        None,
    )
    if manual_patch:
        draft["researchQuestions"] = [
            {"id": f"RQ-{index}", "text": text}
            for index, text in enumerate(manual_patch["researchQuestions"], start=1)
        ]
        declared = {row["id"] for row in draft["researchQuestions"]}
        draft["analysisPlan"] = (
            []
            if manual_patch.get("typedMeasures")
            else [
                entry
                for entry in draft.get("analysisPlan", [])
                if entry["rq"] in declared
            ]
        )

    slot_minutes = _accepted_session_minutes(moves)
    text_minutes = (
        None if slot_minutes is not None else _task_text_session_minutes(moves)
    )
    if slot_minutes is None:
        slot_minutes = text_minutes
    warnings.extend(_apply_instrument_moves(draft, moves, slot_minutes))

    warnings.extend(_apply_analysis_moves(draft, moves))

    warnings.extend(_apply_task_moves(draft, moves))

    warnings.extend(_apply_field_moves(draft, moves))
    if any(isinstance(value, dict) for value in sections["measures"]) and any(
        move.get("status") == "accepted"
        and (move.get("patch") or {}).get("section") == "measures"
        and (move.get("patch") or {}).get("op") == "set"
        for move in moves
    ):
        draft["measures"] = sections["measures"]
    catalog_errors = apply_catalog_measures(draft)
    warnings.extend(_dedupe_measures(draft))
    _dedupe_conditions(draft)
    _canonical_task_conditions(draft)
    if instantiated:
        warnings.extend(
            _template_supplied_notes(template_id, skeleton, draft, sections)
        )
    if text_minutes is not None:
        draft.setdefault("session", {})["durationMinutes"] = text_minutes
    _sync_tern_session_minutes(draft, moves, slot_minutes)
    if slot_minutes is None and not _stated_tern_minutes(moves):
        tern_session = ((draft.get("instruments") or {}).get("tern") or {}).get(
            "session"
        )
        assumed = (draft.get("session") or {}).get("durationMinutes")
        if assumed is None and isinstance(tern_session, dict):
            assumed = tern_session.get("durationMinutes")
        if assumed == 45:
            warnings.append("Session length was not stated, so 45 minutes was assumed")

    study = draft.get("study")
    if isinstance(study, dict) and study.get("researchers") == ["Researcher"]:
        # The schema needs at least one name; make the placeholder obviously editable.
        study["researchers"] = [RESEARCHER_PLACEHOLDER]

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
    errors = (
        failed
        + catalog_errors
        + [
            err
            for err in validate_protocol(draft)
            if not _explained_by_slot(err, outstanding)
        ]
    )

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
