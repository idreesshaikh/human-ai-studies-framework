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

#: The mandatory protocol sections a valid draft must fill (FR-PROT-1). Drives
#: the "unresolved slots" report (F1.3).
MANDATORY_SLOTS: tuple[str, ...] = SECTIONS


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
    """Build a best-effort protocol dict from free-text sections alone (no
    template). This is deliberately a *scaffold*: it will fail validation
    until the mandatory sections are filled, and that failure is the F1.3
    "named unresolved slots" signal, not an error to hide."""
    rqs = [
        {"id": f"RQ-{i + 1}", "text": t}
        for i, t in enumerate(sections["researchQuestions"])
    ]
    return {
        "protocolVersion": 1,
        "study": {
            "id": "draft",
            "title": "Design-conversation draft",
            "researchers": ["Researcher"],
            "ethicsRef": "",
        },
        "researchQuestions": rqs,
        "conditions": list(sections["conditions"]),
        "participants": {
            "planned": 1,
            "design": "within-subjects",
            "counterbalanced": False,
        },
        "session": {"durationMinutes": 1, "taskDescription": "draft"},
        # Free-text measures/instruments are notes, not a valid instrument
        # config; the scaffold leaves instruments empty so validation names it.
        "instruments": {},
        "phases": [{"name": "design", "gates": []}],
        "analysisPlan": [],
    }


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
    instruments = draft.setdefault("instruments", {})
    if not isinstance(instruments, dict):  # scaffold safety
        instruments = draft["instruments"] = {}
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


def _apply_analysis_moves(draft: dict, moves: list[dict]) -> None:
    """Compile accepted prescription and figure moves into the draft's
    analysisPlan (Phase 22 / Slice C — FR-CONV-3 Level 3).

    A ``prescribe-statistics`` move adds or updates a recipe entry in the
    analysis plan with its test, effect size, and parameters. A
    ``suggest-figure`` move sets the figure form on an existing recipe
    entry. Both are deterministic: last accepted move per recipeId wins.

    The entry structure follows FR-ANA-8 parameterised recipe contract:
    ``{rq, recipes: [{id, params: {...}}]}``.
    """
    plan = draft.setdefault("analysisPlan", [])
    plan_by_rq: dict[str, dict] = {}
    for entry in plan:
        plan_by_rq.setdefault(entry["rq"], entry)

    for move in moves:
        if move.get("status") != "accepted":
            continue
        patch = move.get("patch") or {}

        if move["kind"] == "prescribe-statistics":
            recipe_id = patch.get("recipeId")
            rq = patch.get("rq", "RQ-1")
            params = patch.get("params", {})
            deviates = patch.get("deviatesFromTemplate", False)

            if rq not in plan_by_rq:
                plan_by_rq[rq] = {"rq": rq, "recipes": []}
            entry = plan_by_rq[rq]
            existing = [r for r in entry["recipes"] if r.get("id") == recipe_id]
            if existing:
                existing[0]["params"] = params
                if deviates:
                    existing[0]["deviatesFromTemplate"] = True
            else:
                recipe = {"id": recipe_id, "params": params}
                if deviates:
                    recipe["deviatesFromTemplate"] = True
                entry["recipes"].append(recipe)

        elif move["kind"] == "suggest-figure":
            recipe_id = patch.get("recipeId")
            figure = patch.get("figure")
            rq = patch.get("rq")
            if rq and rq in plan_by_rq:
                for r in plan_by_rq[rq]["recipes"]:
                    if r.get("id") == recipe_id:
                        r.setdefault("params", {})["figure"] = figure
                        break

    draft["analysisPlan"] = list(plan_by_rq.values())


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

    errors = failed + validate_protocol(draft)
    unresolved = (
        [] if instantiated else [s for s in MANDATORY_SLOTS if not sections[s]]
    )

    return CompileResult(
        draft=draft,
        yaml=new_yaml,
        diff=diff,
        valid=not errors,
        errors=errors,
        unresolved=unresolved,
        warnings=warnings,
        template_id=template_id,
        template_version=template_version,
        trace=_build_trace(moves),
    )
