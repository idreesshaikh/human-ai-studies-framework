"""LLM-driven design-conversation proposals."""

from __future__ import annotations

import difflib
import json
import logging
import re

from middleware.compiler import FILLABLE_SLOTS
from middleware.design_assistant import ProposedMove, Turn

log = logging.getLogger(__name__)

# The only move kinds the compiler/UI understand (mirrors the kinds the compiler's own
# move kinds) - an unrecognized kind is dropped, never passed through blind.
_ALLOWED_KINDS = frozenset(
    {
        "add-rq",
        "add-measure",
        "set-parameter",
        "set-field",
        "declare-task",
        "prescribe-statistics",
        "choose-template",
        "merge-templates",
        "add-instrument",
        "reconfigure-instrument",
        "caution",
    }
)

_PATCHABLE_SECTIONS = frozenset(
    {
        "researchQuestions",
        "participants",
        "conditions",
        "measures",
        "statisticalPlan",
        "ethics",
    }
)

# Rendered into SYSTEM_PROMPT so the model's `patch.section` choices always match what
# `_validate_patch` actually accepts  -  drifting these apart is exactly what silently
# drops a move's patch (it still renders and can still be "accepted", but never lands in
# the compiled draft).
_SECTION_LIST = ", ".join(sorted(_PATCHABLE_SECTIONS))

_FILLABLE_KEYS = ", ".join(f"`{key}`" for key in FILLABLE_SLOTS)

# Names a model tends to reach for instead of the slot's real key.
_SLOT_ALIASES = {
    "participants.samplesize": "participants.planned",
    "participants.size": "participants.planned",
    "participants.n": "participants.planned",
    "participants.count": "participants.planned",
    "participants.numparticipants": "participants.planned",
    "participants.numberofparticipants": "participants.planned",
    "samplesize": "participants.planned",
    "size": "participants.planned",
    "n": "participants.planned",
    "numparticipants": "participants.planned",
    "session.duration": "session.durationMinutes",
    "session.minutes": "session.durationMinutes",
}

# Handled by the compiler's own mapping of older field names.
_LEGACY_FIELD_KEYS = frozenset({"comparison", "design.conditionOrder"})


def _canonical_slot_path(path: list[str]) -> list[str] | None:
    """The fillable slot a set-field path means, or None if there is none."""
    key = ".".join(path)
    if key in FILLABLE_SLOTS or key in _LEGACY_FIELD_KEYS:
        return list(path)
    alias = _SLOT_ALIASES.get(key.lower())
    if alias is not None:
        log.info("mapped set-field path %r to %r", key, alias)
        return alias.split(".")
    log.info("dropped a set-field move for %r: not a fillable slot", key)
    return None


_PATCH_SHAPE_RULE = (
    'PATCH SHAPES. Conditions are a section patch with `section: "conditions"` '
    'and `op: "append"`; never use a `set-field` path named `comparison`. '
    "Counterbalancing is a `set-field` at `participants.counterbalanced`; never "
    "use `design.conditionOrder`. A statistics move must target a declared RQ id "
    "such as `RQ-1`, not the full question text. A TERN instrument uses the "
    "standard `session`, `fatigue`, `stuck`, and `output` sections, each an "
    "object, never a bare word. A `set-field` path must be exactly one of these "
    f"slot keys: {_FILLABLE_KEYS}. Never invent others such as a sample size "
    "key; the planned participant count is `participants.planned`. "
    "Never put a `comparison` parameter on a template.\n\n"
)

_HOUSE_STYLE = (
    "VOICE. Write like a methodologist talking to a colleague: plain, direct, "
    "unhedged. Short sentences. Say what is grounded and what is not. Never "
    "sell, never congratulate, never open with a compliment.\n"
    "EXPERT VOICE. The reader is an experienced software-engineering researcher. "
    "Address a peer. Never define basic research concepts (within-subjects, "
    "counterbalancing, power) unless asked. Never assume the researcher is a "
    "student or the study a course project. Never restate the brief or what "
    "they just said. No preamble, no sign-off, no filler ('Great question', "
    "'Certainly', 'I understand'), no negative lists of what the template or "
    "study will NOT include. Lead with the decision-relevant point.\n"
    "PACE. For a focused choice, reply in about 70 words, two to four short sentences, "
    "in this priority: (a) what you propose and why, with the specific "
    "trade-off or threat to validity that matters for THIS design; (b) the "
    "source in the form (Author Year) when the move is grounded, keeping the "
    "reference id in the move's refs; (c) exactly one next question that "
    "unblocks the protocol, phrased specifically (for example 'Counterbalance "
    "order, or fix AI-first?'), never generic. If the turn instruction marks "
    "BATCH INTAKE, return the complete set of safe "
    "moves in that response instead of making the researcher walk through them "
    "one by one. For a batch brief or a requested explanation, use up to about "
    "180 words when the trade-offs need it. Lead with a short synthesis; keep "
    "individual decisions in their cards rather than repeating them in prose. "
    "A brief's wording does not mandate a study design: distinguish an option, "
    "a recommendation and a requirement. Let the researcher redirect, defer, "
    "or answer in their own "
    "order. Do not turn the conversation into a checklist.\n"
    "PUNCTUATION: do not use em dashes (the long dash). Use a full stop, a "
    "comma, a colon, or brackets instead. One idea per sentence beats one "
    "sentence with a dash in the middle. Do not use semicolons to join two "
    "independent clauses either; start a new sentence.\n\n"
    "SUPPORTED LANE. This is setup for a task-based human–AI software-development "
    "study in VS Code. Students are valid participants when they are programming. "
    "Do not generalise the workflow to exams, classroom learning, healthcare, "
    "marketing, or other non-developer study types. The server has already stopped "
    "those ideas before this prompt when it can identify them.\n"
    "SETUP PACE. Treat a complete brief as enough to move forward. If the researcher "
    "has already named the coding task, AI comparison, outcome, and practical "
    "constraint, do not ask them to restate those facts. Propose the next runnable "
    "setup choice directly.\n\n"
    "DECISION CONTRACT. When proposals are permitted and the researcher is not "
    "asking you to explain a previous turn, do not return prose alone if the "
    "next safe decision is clear. Return exactly one actionable move card with "
    "the reply, unless the turn instruction marks BATCH INTAKE, in which case "
    "return one card for each distinct safe fact or setup choice. A card is the "
    "platform's unit of progress: the researcher can accept it, reject it, or "
    "correct it. Return no move only when the turn is a follow-up explanation, a "
    "methodological caution, or a genuinely unsafe guess.\n\n"
    "CARD ORDER. A turn that contains a move card is a decision sheet. Its text "
    "explains the proposal and its trade-off. Its one question may only be about "
    "the open choice inside that proposal (for example 'Counterbalance order, or "
    "fix AI-first?'), never a different protocol topic. The next topic is raised "
    "in the follow-up turn after the researcher decides the card.\n\n"
    "NO INVENTED MOTIVES. Never state, guess or imply why the researcher accepted, "
    "rejected, noted or undid a card. They gave no reason unless they typed one. "
    "Acknowledge the decision neutrally and continue.\n"
    "NO UNRECORDED FACTS. In reply text, only restate details that appear as "
    "accepted moves in the state block or as cards in this turn; otherwise offer "
    "them as cards instead of claiming the researcher said them.\n\n"
    "UNCERTAINTY. 'I do not know', 'not sure', 'you decide', 'whatever is best', "
    "'later', and 'skip' are valid instructions, not failed answers. Never repeat "
    "the same question because the researcher is uncertain. Choose a conservative "
    "default when one is defensible and label it as a recommendation, or leave the "
    "choice open and move to another useful decision. The researcher may redirect "
    "the conversation at any time.\n\n"
)

SYSTEM_PROMPT = (
    _HOUSE_STYLE
    + _PATCH_SHAPE_RULE
    + "You are the design-conversation partner for a human-AI developer study "
    "platform. A researcher describes a study idea in plain language. Help "
    "them DERIVE a good, methodologically sound protocol, ask a clarifying "
    "question when the idea is ambiguous, then propose concrete design moves "
    "they accept or reject.\n\n"
    "Each move's `proposal` is one imperative sentence naming the concrete "
    "value, for example 'Set 12 participants (within-subjects).' not 'Set the "
    "participant count to 12 professional developers.'. Put no rationale in "
    "the proposal: the reason belongs in the reply text. Name the concrete "
    "research question, measure, parameter, or design, never a vague gesture "
    "('consider your measures'). "
    "Across the conversation aim for a complete protocol: cover the core "
    "sections, pair any self-report with an objective measure, and raise a "
    "`caution` when a choice risks a known validity threat. When the turn "
    "carries a design-state block, use its coverage line to pick targets: "
    "prioritize moves for the EMPTY sections over adding more to already "
    "filled ones. The typical order once design and measures are set: "
    "participants (population, sample size), then statisticalPlan. Even with "
    "an accepted template the statisticalPlan section still needs its own "
    "entry. Use a `prescribe-statistics` move with a runnable recipe id, "
    "never a free-text field that the compiler cannot execute. The standard "
    "within-subjects recipe is `paired-nonparametric`; record or refine the "
    "template's prescribed statistics, never contradict them.\n\n"
    "A `caution` is advisory and never fills a section (it carries no "
    "patch). The ethics section is optional and is filled only by a "
    "`set-parameter` move "
    'with `patch.section` "ethics" (consent, data handling, privacy/'
    "withdrawal posture), when the researcher wants ethics covered. Raise a "
    "caution first when needed, then ask for the posture in the next turn. "
    "Never ask for or invent an ethics approval/reference number. The platform "
    "does not issue or verify university approval. If the researcher has no "
    "reference yet, leave it open and continue with the study design. "
    "NEVER use `add-instrument` for this: "
    "that kind is reserved for an actual capture instrument (e.g. "
    'agentCapture) and its patch always needs `section: "instruments"`, '
    "so an ethics posture sent as `add-instrument` never reaches the "
    "draft.\n\n"
    "INSTRUMENT NAMES. Use only real protocol instruments: `tern`, `metrics`, "
    "`agentCapture`, or `taskHarness`. `taskTimer`, `screenRecorder`, and "
    "similar labels are measures or implementation ideas, not instrument keys; "
    "never invent them. For ordinary live coding sessions, add `tern` with the "
    "standard capture config supplied by the study runtime.\n\n"
    "REPETITION: NEVER re-propose a move the design state lists as accepted, "
    "rejected, or awaiting decision, nor a near-duplicate or rewording of "
    "one. An accepted move is already in the draft; a rejected one was "
    "declined for a reason (address the reason in your reply text if "
    "relevant, but do not pitch the move again). Every move you propose "
    "must be genuinely new.\n\n"
    "GROUNDING, prefer papers. You may cite ONLY the papers and templates in "
    "the candidate menu given to you this turn (never one you were not given). "
    "The menu is retrieved to be relevant, so MOST moves should carry at least "
    "one `ref` from it, reach for the grounding. Leave `refs` empty ONLY for "
    "a genuine researcher-judgment call the literature can't settle (a scoping "
    "or tuning decision); that should be the exception, not the norm. Never "
    "fabricate a citation, but do not leave a move unsourced when a fitting "
    "candidate is right there.\n\n"
    "TASKS. What participants actually do is the study's most replicable "
    "detail and the one most often left as a sentence. When the researcher "
    "describes the work, propose a `declare-task` move, combining "
    "closely related activities from the same session (for example, writing "
    "and debugging code) into one coherent task instead of making a card for "
    "each verb. Give it a title and, where they said so, how long it should "
    "take and where the materials live. A within-subjects study "
    "needs at least one task per condition, or participants must repeat a "
    "task and the second encounter is contaminated by the first; say so if "
    "they have fewer. Do not invent tasks they never mentioned.\n\n"
    "FINISHING THE PROTOCOL. A template is the fastest route to a complete "
    "design - it brings a vetted shape and the statistics that go with it - "
    "so once the study is understood well enough, propose the one that fits, "
    "and say so in the reply text if none of the candidates do. When no "
    "single template fits but two or three of the candidates together would "
    "cover the study (a behavioural/telemetry shape plus a self-report "
    "survey shape is the classic pair), propose a `merge-templates` move "
    "instead, with the reason the pairing works and the refs grounding each "
    "shape. But a "
    "template is not the only route: the turn instruction below lists the "
    "protocol slots still outstanding, and a `set-field` move fills a named "
    "one directly. Prefer a template when one fits; use `set-field` to fill "
    "what a template left open, or to build the protocol slot by slot when "
    "the study is unusual enough that no template does. Keep open slots visible, "
    "but do not nag for a value the researcher does not have. Fill it when they "
    "give the value, offer a labelled default when safe, or leave it open and "
    "continue with another useful choice.\n\n"
    "BUT NOT YET, AND NOT BLIND. A design shape is a *consequence* of who "
    "takes part, what they do, what is compared, what is measured, and what "
    "is practically possible. Naming a shape before you know those boxes the "
    "researcher into a design chosen from almost nothing, which is worse than "
    "asking. The turn instruction below tells you which of these the "
    "conversation still doesn't know and whether you may propose a design "
    "yet; use it as guidance, not as a questionnaire. While you are still "
    "learning the study, ask ONE genuine question at a time (never a list of "
    "five), but accept a deferral or a redirect, reflect back what you "
    "understood so they can correct you, and propose only moves that are "
    "already safe, a research question in their own words, a measure they "
    "named themselves, a caution.\n\n"
    "ANSWER WHAT WAS ASKED. If the researcher asks about something you "
    "already said, 'why did you propose that?', 'what do you mean?', 'on "
    "what basis?', then ANSWER IT, in the reply text, referring to the "
    "specific move you proposed and the reasoning and papers behind it. Your "
    "own earlier proposals are in the conversation history above, with what "
    "the researcher decided about each. Replying to a question with a fresh "
    "batch of proposals instead of an answer is the single worst thing you "
    "can do here: it tells the researcher you were not listening. Do not "
    "re-propose something they already rejected without acknowledging that "
    "they rejected it and saying what changed.\n\n"
    "PLAIN TEXT. The reply text is shown verbatim to a researcher, so write "
    "plain prose: no markdown (no **bold**, no backticks, no bullet "
    "syntax), never write template ids, paper refs (corpus:..., arxiv:...) "
    "or slot keys (like session.durationMinutes) in it. Name a template by "
    "its title, cite a paper as (Author Year) from the menu's bracketed author "
    "and year, or (Short title Year) when no author is given, "
    "and name a field in everyday words.\n\n"
    "Reply with a single JSON object, no prose outside it:\n"
    '{"text": "expert-voice reply, (Author Year) citations only; the '
    'reference ids live in moves[].refs", '
    '"moves": [{"kind": "...", "target": "researchQuestions[]", "proposal": '
    '"one imperative sentence, no rationale", "patch": {...} or null, '
    '"refs": ["..."]}]}\n\n'
    "Valid kinds: add-rq, add-measure, set-parameter, set-field, "
    "declare-task, prescribe-statistics, choose-template, merge-templates, "
    "add-instrument, "
    "reconfigure-instrument, caution. "
    "`refs` entries must come from the candidate menu only (a paper's ref or "
    "a template's id).\n\n"
    "`patch` shapes (anything else is dropped and the move never reaches "
    "the draft, even if accepted):\n"
    f'- add-rq, add-measure, set-parameter: {{"section": one of '
    f'[{_SECTION_LIST}], "op": "append" or "set", "value": "..."}}. Pick '
    "whichever section the change actually belongs to, e.g. a sample-size "
    'or alpha parameter is "participants" or "statisticalPlan", not '
    '"parameters" (not a real section).\n'
    '- set-field: {"op": "set-field", "path": ["..."], "value": ...} - `path` '
    "is an outstanding slot's key split on dots, and `value` must match that "
    "slot's type (an integer slot takes a number, an enum slot one of its "
    "listed choices, a boolean slot true/false). Only the slots named in the "
    "turn instruction can be written; anything else is refused.\n"
    '- declare-task: {"title": "...", "description": "...", "minutes": N, '
    '"materials": "repo url or path", "conditions": ["..."]}, one move per '
    "task. Only `title` is required; `conditions` restricts a task to some "
    "of the study's arms and should be left out unless the researcher means "
    "it, since a task tied to one condition confounds the two.\n"
    '- prescribe-statistics: {"recipeId": "paired-nonparametric", "rq": "RQ-1"}. '
    "Use a recipe from the platform catalogue and point it at a declared research "
    "question.\n"
    '- choose-template: {"templateId": "...", "parameters": {...}}\n'
    '- merge-templates: {"templateIds": ["...", "..."], "reason": "..."} - '
    "two or more candidate template ids plus why this pairing works (what "
    "each shape contributes, e.g. objective behaviour data plus self-report "
    "perception). `refs` should carry each merged template's id.\n"
    '- add-instrument: {"section": "instruments", "op": "add-instrument" or '
    '"set-instrument", "name": "...", "config": {...}}\n'
    '- reconfigure-instrument: {"section": "instruments", "op": '
    '"reconfigure", "name": "...", "path": ["..."], "value": ...}\n'
    "- caution: patch is always null."
)


_STATE_PROPOSAL_CHARS = 140
_STATE_PROMPT_MOVES_PER_BUCKET = 8


def _clip(text: str) -> str:
    if len(text) <= _STATE_PROPOSAL_CHARS:
        return text
    return text[: _STATE_PROPOSAL_CHARS - 1] + "…"


def _design_state_block(state: dict | None) -> str:
    """
    Render ``design_assistant._load_design_state`` for the user message: every prior
    move by decision status plus the draft's coverage, the structured facts the prose
    history can't carry, and what the prompt's REPETITION and coverage rules key on.
    """
    if not state:
        return ""
    lines = ["Design state so far:"]
    for title, bucket in (
        ("Accepted (already in the draft, do not re-propose):", "accepted"),
        ("Rejected (the researcher said no, do not re-pitch):", "rejected"),
        ("Awaiting decision (do not duplicate):", "proposed"),
    ):
        entries = state.get(bucket) or []
        lines.append(title)
        if not entries:
            lines.append("- (none)")
        omitted = max(0, len(entries) - _STATE_PROMPT_MOVES_PER_BUCKET)
        if omitted:
            lines.append(
                f"- ({omitted} earlier move(s) omitted; the server still "
                "prevents repeats)"
            )
        for e in entries[-_STATE_PROMPT_MOVES_PER_BUCKET:]:
            caution = e["kind"] == "caution"
            advisory = " (advisory, fills no section)" if caution else ""
            lines.append(
                f"- {e['kind']} [{e['section']}]{advisory}: {_clip(e['proposal'])}"
            )
    outstanding = state.get("outstandingSlots")
    if outstanding is None:
        pass
    elif outstanding:
        lines.append(
            "The protocol still has open required fields: "
            + ", ".join(s["label"] for s in outstanding)
            + ". The draft can still be saved and reviewed. Fill a slot with a "
            "set-field move when the researcher has given you the value, or ask "
            "about one only when they want to settle it."
        )
    else:
        lines.append(
            "The protocol has every slot it needs and will compile. Do not "
            "tell the researcher something is missing."
        )
    if state.get("templateId"):
        lines.append(
            f"Template {state['templateId']} is accepted and prescribes the "
            "statistics, statisticalPlan moves should record or refine that "
            "prescription (test, alpha, correction, exclusions), never "
            "contradict it."
        )
    return "\n".join(lines)


def _candidate_menu(papers: list[dict], templates: list[dict]) -> str:
    paper_lines = [
        f"- {p['ref']}: {p.get('title', '')}"
        + (
            f" [{p['authors']} {p['year']}]"
            if p.get("authors") and p.get("year")
            else ""
        )
        + (f" [{p['year']}]" if not p.get("authors") and p.get("year") else "")
        for p in papers
    ]
    template_lines = [
        f"- {t['templateId']}: {t.get('title', '')} "
        f"({t.get('designShape') or 'unspecified shape'})"
        for t in templates
    ]
    return (
        "Papers:\n"
        + ("\n".join(paper_lines) or "(none retrieved)")
        + "\nTemplates:\n"
        + ("\n".join(template_lines) or "(none matched)")
    )


def _validate_patch(kind: str, patch: object) -> dict | None:
    """
    Structural check against the compiler's known op shapes (``compiler.py``'s
    ``compile_sections``/``_apply_instrument_moves``/ ``_accepted_template_moves``).
    """
    if kind == "caution":
        return None
    if not isinstance(patch, dict):
        return None
    if kind == "choose-template":
        template_id = patch.get("templateId")
        if isinstance(template_id, str) and template_id:
            parameters = dict(patch.get("parameters") or {})
            # The comparison is a conditions section, never a template parameter.
            parameters.pop("comparison", None)
            return {"templateId": template_id, "parameters": parameters}
        return None
    if kind == "merge-templates":
        template_ids = patch.get("templateIds")
        reason = patch.get("reason")
        if (
            isinstance(template_ids, list)
            and len(template_ids) >= 2
            and all(isinstance(t, str) and t for t in template_ids)
            and isinstance(reason, str)
            and reason.strip()
        ):
            return {
                "templateIds": list(dict.fromkeys(template_ids)),
                "reason": reason.strip(),
            }
        return None
    if kind == "declare-task":
        # Slugging the id, coercing minutes and deciding what is usable is the
        # compiler's call (``_apply_task_moves``), so one place decides it and warns
        # rather than silently dropping.
        title = patch.get("title")
        if isinstance(title, str) and title.strip():
            return patch
        return None
    if kind == "prescribe-statistics":
        recipe_id = patch.get("recipeId")
        rq = patch.get("rq", "RQ-1")
        if (
            isinstance(recipe_id, str)
            and recipe_id.strip()
            and isinstance(rq, str)
            and rq.strip()
        ):
            return {"recipeId": recipe_id.strip(), "rq": rq.strip()}
        return None
    if patch.get("op") == "set-field":
        # Which slots exist, and whether the value can be the slot's type, is the
        # compiler's call (``_apply_field_moves``) - one place decides that, and it
        # warns rather than silently dropping.
        path = patch.get("path")
        if (
            isinstance(path, list)
            and path
            and all(isinstance(p, str) and p for p in path)
            and "value" in patch
        ):
            canonical = _canonical_slot_path(path)
            if canonical is None:
                return None
            return {"op": "set-field", "path": canonical, "value": patch["value"]}
        return None
    if kind == "add-instrument" and patch.get("section") == "instruments":
        if (
            patch.get("op") in ("add-instrument", "set-instrument")
            and isinstance(patch.get("name"), str)
            and patch.get("name")
            and isinstance(patch.get("config"), dict)
        ):
            return patch
        return None
    if kind == "reconfigure-instrument" and patch.get("section") == "instruments":
        if (
            patch.get("op") == "reconfigure"
            and isinstance(patch.get("name"), str)
            and patch.get("name")
            and isinstance(patch.get("path"), list)
            and patch["path"]
            and all(isinstance(p, str) for p in patch["path"])
            and "value" in patch
        ):
            return patch
        return None
    if (
        patch.get("section") in _PATCHABLE_SECTIONS
        and patch.get("op") in ("append", "set")
        and "value" in patch
    ):
        value = _normalize_value(patch["value"])
        if value is None:
            return None
        return {"section": patch["section"], "op": patch["op"], "value": value}
    return None


def _normalize_value(value: object) -> str | list[str] | None:
    """Coerce a section-patch value to what the sections actually hold."""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        items = [
            v if isinstance(v, str) else str(v)
            for v in value
            if isinstance(v, (str, int, float, bool))
        ]
        return items or None
    return None


def _known_template_ids() -> frozenset[str]:
    """Every template id the registry can actually instantiate."""
    from middleware import template_registry

    try:
        return frozenset(t["templateId"] for t in template_registry.list_templates())
    except Exception:  # noqa: BLE001 - degrade, never break a turn
        return frozenset()


MAX_CARDS = 5
MAX_BATCH_CARDS = 8
_EMPTY_CAUTION = re.compile(
    r"^\W*(?:none|n/?a|nothing|no\s+(?:caution|cautions|concerns?|risks?))\W*$", re.I
)


def _move_dedupe_key(kind: str, target: str, proposal: str, patch: dict | None):
    """Two cards that would write the same thing collapse to one key."""
    where = target
    value = proposal
    if isinstance(patch, dict):
        where = str(patch.get("section") or patch.get("path") or target)
        value = str(
            patch.get("value")
            or patch.get("templateId")
            or patch.get("name")
            or patch.get("title")
            or proposal
        )
    # Count cards can spell the same value as "16" or "16 participants".
    # Other patches must not collapse just because they share a year/number.
    count = re.fullmatch(
        r"(\d+(?:\.\d+)?)(?:\s+participants(?:\s*\([^)]*\))?)?",
        value.strip(),
        re.I,
    )
    if kind == "set-parameter" and where == "participants" and count:
        return (kind, where, count.group(1))
    if isinstance(patch, dict):
        return (kind, json.dumps(patch, sort_keys=True, ensure_ascii=False))
    return (kind, _norm(where), _norm(value))


def _parse_moves(
    raw_moves: object,
    candidate_refs: set[str],
    titles: dict[str, str] | None = None,
    max_cards: int = MAX_CARDS,
) -> tuple[ProposedMove, ...]:
    known_templates = _known_template_ids()
    out: list[ProposedMove] = []
    seen_keys: set[tuple] = set()
    for m in raw_moves if isinstance(raw_moves, list) else []:
        if not isinstance(m, dict):
            continue
        kind = m.get("kind")
        if kind not in _ALLOWED_KINDS:
            continue
        proposal = str(m.get("proposal", "")).strip()
        if not proposal:
            continue
        if kind == "caution" and _EMPTY_CAUTION.match(proposal):
            continue
        patch = _validate_patch(kind, m.get("patch"))
        if kind != "caution" and patch is None:
            # Every non-caution kind is supposed to carry a patch; one that didn't
            # validate can never touch the draft even if accepted - the "accepted but
            # only noted" trap.
            continue
        if kind == "choose-template" and patch["templateId"] not in known_templates:
            # A hallucinated template id can never instantiate.
            continue
        if kind == "merge-templates" and not all(
            t in known_templates for t in patch["templateIds"]
        ):
            # A hallucinated template id can never instantiate, and a merge
            # names at least two of them.
            continue
        raw_refs = m.get("refs")
        refs = (
            tuple(r for r in raw_refs if isinstance(r, str) and r in candidate_refs)
            if isinstance(raw_refs, list)
            else ()
        )
        # Display text only: the patch keeps the real ids it needs to compile.
        proposal = tighten_proposal(sanitize_reply_text(proposal, titles or {}))
        key = _move_dedupe_key(kind, str(m.get("target", "")), proposal, patch)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        out.append(ProposedMove(kind, str(m.get("target", "")), proposal, patch, refs))
        if len(out) >= max_cards:
            break
    return tuple(out)


MAX_TOKENS = 1200
REPLY_TEXT_MAX_CHARS = 700
EXPLAIN_REPLY_MAX_CHARS = 900
CARDS_REPLY_MAX_CHARS = 520
CARDS_REPLY_MAX_SENTENCES = 3
DECISION_REPLY_MAX_CHARS = 400

_MOTIVE_SENTENCE = re.compile(
    r"\bbecause\s+you\b|\byou\s+(?:wanted|preferred|felt|thought|needed|chose)\b"
    r"|\b(?:was|were)\s+trying\s+to\b|\bto\s+clarify\s+the\s+setup\b",
    re.I,
)


def strip_attributed_motives(text: str) -> str:
    """Drop sentences that attribute a reason to the researcher's card decision."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [s for s in sentences if not _MOTIVE_SENTENCE.search(s)]
    return " ".join(kept).strip()


_FILLER_SENTENCE = re.compile(
    r"^\W*(?:great|good|excellent|interesting)\s+(?:question|point|idea)\b"
    r"|^\W*(?:certainly|of course|absolutely|sure thing|sure)\b"
    r"|^\W*i\s+understand\b|^\W*as an ai\b|^\W*hope this helps\b"
    r"|^\W*let me know if\b|^\W*feel free to\b",
    re.I,
)
_STUDENT_ASSUMPTION = re.compile(
    r"\b(?:course|class|classroom|student)\s+project\b"
    r"|\bfor (?:a|your) (?:course|class)\b",
    re.I,
)
_FILLER_MAX_CHARS = 60
_REAL_SENTENCE_END = re.compile(r"(?<=[.!?])(?<!\be\.g\.)(?<!\bi\.e\.)\s+(?=[A-Z])")


def strip_filler(text: str) -> str:
    """Drop short filler openers/sign-offs and student-assuming sentences."""
    # Keep line and paragraph breaks: flattening these made the final streamed
    # turn differ from the visible tokens and erased the reply's hierarchy.
    parts = re.split(r"(?<=[.!?])(\s+)", text.strip())
    kept = [
        s + (parts[i + 1] if i + 1 < len(parts) else "")
        for i, s in enumerate(parts)
        if i % 2 == 0
        if not (
            (_FILLER_SENTENCE.search(s) and len(s) <= _FILLER_MAX_CHARS)
            or _STUDENT_ASSUMPTION.search(s)
        )
    ]
    return "".join(kept).strip() or text.strip()


_RATIONALE_CUT = re.compile(
    r",?\s+(?:because|since|so that|given that)\b.*$"
    r"|,\s*(?:which|to (?:ensure|avoid|reduce|control))\b.*$"
    r"|\s+[-\u2013\u2014]\s+.*$",
    re.I | re.S,
)


def tighten_proposal(proposal: str) -> str:
    """One imperative sentence: keep the first sentence, drop trailing rationale."""
    first = _REAL_SENTENCE_END.split(proposal.strip(), maxsplit=1)[0]
    first = _RATIONALE_CUT.sub("", first).rstrip(" ,;:")
    if first and first[-1] not in ".!?":
        first += "."
    return first or proposal.strip()


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_MIN_REPEAT_CHARS = 15


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def trim_repeated_text(text: str) -> str:
    """
    Cut a looping reply back to its first occurrence: a paragraph, then a sentence,
    that repeats an earlier one marks where the model began to loop.
    """
    paragraphs = _PARAGRAPH_SPLIT.split(text.strip())
    kept: list[str] = []
    seen: set[str] = set()
    for para in paragraphs:
        key = _norm(para)
        if len(key) >= _MIN_REPEAT_CHARS and key in seen:
            break
        seen.add(key)
        kept.append(para)
    text = "\n\n".join(kept)
    # Sentence pass: rebuild paragraph by paragraph, stopping at the first repeat.
    seen = set()
    out_paras: list[str] = []
    for para in text.split("\n\n"):
        out: list[str] = []
        looped = False
        for sentence in _SENTENCE_SPLIT.split(para):
            key = _norm(sentence)
            if len(key) >= _MIN_REPEAT_CHARS and key in seen:
                looped = True
                break
            seen.add(key)
            out.append(sentence)
        if out:
            out_paras.append(" ".join(out) if looped else para)
        if looped:
            break
    return "\n\n".join(out_paras).strip()


def cap_reply_text(text: str, limit: int = REPLY_TEXT_MAX_CHARS) -> str:
    """Bound the reply's length, cutting at the last sentence end that fits."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", window)]
    return (window[: ends[-1]] if ends else window).rstrip()


def sanitize_reply_text(text: str, titles: dict[str, str]) -> str:
    """
    Strip markdown emphasis/backticks and swap known template/paper ids for their
    titles. Markdown links (the citation links) are left as written.
    """
    text = text.replace("`", "")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S)
    text = re.sub(r"__(.+?)__", r"\1", text, flags=re.S)
    text = re.sub(r"(?<![*\w])\*(?!\s)([^*\n]+?)\*(?![*\w])", r"\1", text)
    for ident in sorted(titles, key=len, reverse=True):
        if titles[ident]:
            text = re.sub(
                rf"(?<![\w:/-]){re.escape(ident)}(?![\w-])", titles[ident], text
            )
    return text


def _title_map(papers: list[dict], templates: list[dict]) -> dict[str, str]:
    """id -> human title for everything resolvable this turn."""
    titles: dict[str, str] = {}
    try:
        from middleware import template_registry

        for t in template_registry.list_templates():
            titles[t["templateId"]] = t.get("title", "")
    except Exception:  # noqa: BLE001 - degrade, never break a turn
        log.debug("Template titles unavailable; using this turn's supplied titles")
    for t in templates:
        if t.get("templateId") and t.get("title"):
            titles[t["templateId"]] = t["title"]
    for p in papers:
        if p.get("ref") and p.get("title"):
            titles[p["ref"]] = p["title"]
    return titles


_STOPWORDS = frozenset(
    "the a an and or of to in on for with is are was were be been this that these "  # noqa: SIM905 - compact vocabulary
    "those it its as at by from we you your our they their how what which whether "
    "about into than then so not no can could would should will may might do does "
    "did have has had thinking want know".split()
)


def _content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w.rstrip("s") if len(w) > 3 else w for w in words if w not in _STOPWORDS}


def drop_restatement(text: str, user_text: str, threshold: float = 0.6) -> str:
    """Drop leading sentences that mostly repeat the researcher's own message."""
    user_words = _content_words(user_text)
    if not user_words:
        return text
    sentences = [x for x in _SENTENCE_SPLIT.split(text.strip()) if x]
    i = 0
    while i < len(sentences) - 1:
        words = _content_words(sentences[i])
        if not words or len(words & user_words) / len(words) < threshold:
            break
        i += 1
    return " ".join(sentences[i:]) if i else text


_REJECTED_ALTERNATIVE = re.compile(
    r"\b(?:is|are)\s+(?:too\s+(?:broad|narrow)|insufficient|not\s+(?:enough|sufficient))\b"
    r"|\bwill\s+not\s+(?:include|have|contain)\b|\bdoes\s+not\s+(?:prescribe|include)\b",
    re.I,
)


def drop_rejected_alternatives(text: str) -> str:
    """Remove explicitly rejected alternatives, never infer away a limitation."""
    sentences = [x for x in _SENTENCE_SPLIT.split(text.strip()) if x]
    kept = [
        x
        for x in sentences
        if not (
            _REJECTED_ALTERNATIVE.search(x)
            and re.search(r"\b(?:rejected|not selected|unused alternative)\b", x, re.I)
        )
    ]
    return " ".join(kept) if kept and len(kept) != len(sentences) else text


def _surname(authors: object) -> tuple[str, bool] | None:
    """(first author's surname, whether there are more authors)."""
    if isinstance(authors, str):
        parts = [a for a in re.split(r"\s*(?:;|\band\b|&)\s*", authors) if a.strip()]
    elif isinstance(authors, list):
        parts = [str(a) for a in authors if str(a).strip()]
    else:
        return None
    if not parts:
        return None
    first = parts[0].strip()
    name = first.split(",")[0] if "," in first else first.split()[-1]
    return name.strip(), len(parts) > 1


def _short_citation(paper: dict, fallback_title: str = "") -> str:
    year = paper.get("year")
    who = _surname(paper.get("authors"))
    if who:
        name, more = who
        label = f"{name} et al." if more else name
        return f"{label} {year}" if year else label
    title = re.sub(r"\s+", " ", (paper.get("title") or fallback_title)).strip()
    title = title.lower().capitalize()
    if len(title) > 60:
        title = title[:60].rstrip(" ,;:-") + "\u2026"
    return f"{title} {year}" if year else title


def _same_title(a: str, b: str) -> bool:
    x = re.sub(r"[^a-z0-9 ]", "", a.lower()).strip()
    y = re.sub(r"[^a-z0-9 ]", "", b.lower()).strip()
    if not x or not y:
        return False
    if x.startswith(y[:40]) or y.startswith(x[:40]):
        return True
    return difflib.SequenceMatcher(None, x, y).ratio() >= 0.8


_PAREN = re.compile(r"\(([^()]{20,})\)")


def shorten_citations(text: str, papers: list[dict]) -> str:
    """Turn inline '(Full Paper Title)' into '(Surname Year)'."""

    def swap(match: re.Match) -> str:
        inner = match.group(1).strip().rstrip(".,; ")
        inner = re.sub(r"[,\s]*(?:\u2026|\.\.\.)$", "", inner)
        for paper in papers:
            title = paper.get("title") or ""
            if title and _same_title(inner, title):
                return f"({_short_citation(paper)})"
        if len(inner) > 60 and inner.upper() == inner:
            return f"({_short_citation({'title': inner})})"
        return match.group(0)

    return _PAREN.sub(swap, text)


_GENERIC_QUESTION = "What would you like to settle next?"


def _limit_sentences(sentences: list[str], limit: int, max_sentences: int) -> str:
    """Keep up to max_sentences within limit chars, hard-cutting the first."""
    out: list[str] = []
    for sentence in sentences[:max_sentences]:
        candidate = " ".join([*out, sentence])
        if len(candidate) > limit:
            if not out:
                out.append(cap_reply_text(sentence, limit))
            break
        out.append(sentence)
    return " ".join(out)


def _clean_reply(
    text: str,
    papers: list[dict],
    templates: list[dict],
    decision_followup: bool = False,
    directive: str = "",
    *,
    user_text: str = "",
    has_cards: bool = False,
    next_question: str = "",
) -> str:
    if decision_followup:
        # Deterministic: the model's prose after a decision is never shown.
        return "Noted." + (f" {next_question.strip()}" if next_question.strip() else "")
    if not text.strip():
        return ""
    text = strip_filler(trim_repeated_text(text))
    text = drop_rejected_alternatives(drop_restatement(text, user_text))
    text = shorten_citations(text, papers)
    structured_text = text
    explain = "QUESTION ABOUT WHAT YOU ALREADY SAID" in directive
    if explain and not has_cards:
        text = cap_reply_text(text, EXPLAIN_REPLY_MAX_CHARS)
    else:
        sentences = [x for x in _SENTENCE_SPLIT.split(text.strip()) if x]
        question = next((x for x in reversed(sentences) if x.endswith("?")), "")
        body = [x for x in sentences if x != question]
        if not question and not has_cards and not explain:
            question = next_question.strip() or _GENERIC_QUESTION
        if has_cards:
            limit, count = CARDS_REPLY_MAX_CHARS, CARDS_REPLY_MAX_SENTENCES
        else:
            limit, count = REPLY_TEXT_MAX_CHARS, 4
        if question:
            count -= 1
            limit -= len(question) + 1
        text = " ".join(
            x for x in (_limit_sentences(body, max(limit, 60), count), question) if x
        )
    # Already-concise replies retain their line breaks instead of jumping to
    # a flattened paragraph when the streamed turn is committed.
    if _norm(text) == _norm(structured_text) and len(structured_text) <= (
        CARDS_REPLY_MAX_CHARS if has_cards else REPLY_TEXT_MAX_CHARS
    ):
        text = structured_text
    return sanitize_reply_text(text, _title_map(papers, templates))


class _ReplyTextExtractor:
    """
    Pull the value of the reply's leading ``"text"`` field out of a JSON object *as it
    streams*.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._in_text = False
        self._done = False
        self._escape = False
        self.text = ""

    def feed(self, chunk: str) -> str:
        """Return whatever prose this chunk contributed (often "")."""
        prose = self._feed(chunk)
        self.text += prose
        return prose

    def _feed(self, chunk: str) -> str:
        if self._done:
            return ""
        out = []
        for ch in chunk:
            if not self._in_text:
                self._buf += ch
                marker = self._buf.find('"text"')
                if marker == -1:
                    self._buf = self._buf[-8:]
                    continue
                rest = self._buf[marker + len('"text"') :]
                opened = rest.find('"')
                if opened == -1:
                    continue
                self._in_text = True
                self._buf = ""
                chunk_tail = rest[opened + 1 :]
                if chunk_tail:
                    out.append(self._feed(chunk_tail))
                continue
            if self._escape:
                out.append({"n": "\n", "t": "\t", "r": "\r"}.get(ch, ch))
                self._escape = False
            elif ch == "\\":
                self._escape = True
            elif ch == '"':
                self._done = True
                break
            else:
                out.append(ch)
        return "".join(out)


def _messages(
    text: str,
    history: list[dict],
    papers: list[dict],
    templates: list[dict],
    directive: str,
    design_state: dict | None = None,
) -> list[dict]:
    """The chat messages for one design turn."""
    menu = _candidate_menu(papers, templates)
    content = f"{text}\n\nCandidate menu this turn:\n{menu}"
    state_block = _design_state_block(design_state)
    if state_block:
        content += f"\n\n{state_block}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        *([{"role": "system", "content": directive}] if directive else []),
        {"role": "user", "content": content},
    ]


def propose_turn_streaming(
    client,
    text: str,
    history: list[dict],
    papers: list[dict],
    templates: list[dict],
    directive: str = "",
    *,
    design_state: dict | None = None,
    decision_followup: bool = False,
    next_question: str = "",
):
    """:func:`propose_turn`, yielding the reply's prose as it arrives."""
    stream = getattr(client, "stream", None)
    if stream is None:
        return propose_turn(
            client,
            text,
            history,
            papers,
            templates,
            directive,
            design_state=design_state,
            decision_followup=decision_followup,
            next_question=next_question,
        )

    candidate_refs = {p["ref"] for p in papers if p.get("ref")}
    candidate_refs |= {t["templateId"] for t in templates if t.get("templateId")}
    messages = _messages(text, history, papers, templates, directive, design_state)
    extractor = _ReplyTextExtractor()
    body = ""
    try:
        for piece in stream(
            client.base_url,
            {
                "model": client.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_tokens": MAX_TOKENS * (2 if "BATCH INTAKE" in directive else 1),
            },
            {"Authorization": f"Bearer {client.api_key}"},
        ):
            body += piece
            prose = extractor.feed(piece)
            if prose:
                yield prose
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            # Cut off at the token cap: keep the prose already streamed rather
            # than paying for a second full call that would likely loop again.
            salvaged = _clean_reply(
                extractor.text.strip(),
                papers,
                templates,
                decision_followup,
                directive,
                user_text=text,
                next_question=next_question,
            )
            if not salvaged:
                raise
            log.warning("streaming turn truncated; keeping its prose")
            return Turn(text=salvaged, moves=(), match_query=None)
        if not isinstance(parsed, dict):
            raise ValueError("LLM reply was not a JSON object")
        moves = _parse_moves(
            parsed.get("moves"),
            candidate_refs,
            _title_map(papers, templates),
            MAX_BATCH_CARDS if "BATCH INTAKE" in directive else MAX_CARDS,
        )
        reply_text = _clean_reply(
            str(parsed.get("text", "")).strip(),
            papers,
            templates,
            decision_followup,
            directive,
            user_text=text,
            has_cards=bool(moves),
            next_question=next_question,
        )
    except Exception as exc:  # noqa: BLE001 - any provider/parse failure degrades
        log.warning("streaming conversation turn failed, falling back: %s", exc)
        return propose_turn(
            client,
            text,
            history,
            papers,
            templates,
            directive,
            design_state=design_state,
            decision_followup=decision_followup,
            next_question=next_question,
        )
    if not reply_text and not moves:
        log.warning("LLM conversation turn produced no usable content, falling back")
        return None
    return Turn(text=reply_text or "(no reply text)", moves=moves, match_query=None)


def propose_turn(
    client,
    text: str,
    history: list[dict],
    papers: list[dict],
    templates: list[dict],
    directive: str = "",
    *,
    design_state: dict | None = None,
    decision_followup: bool = False,
    next_question: str = "",
) -> Turn | None:
    """
    Ask the configured LLM provider for this turn's prose + proposed moves, constrained
    to ``papers``/``templates`` already retrieved this exchange (both built by the
    caller *before* this call, via the existing deterministic ``matching.match_papers``
    / ``design_assistant.recommend_templates``).
    """
    candidate_refs = {p["ref"] for p in papers if p.get("ref")}
    candidate_refs |= {t["templateId"] for t in templates if t.get("templateId")}
    messages = _messages(text, history, papers, templates, directive, design_state)
    try:
        res = client.post(
            client.base_url,
            {
                "model": client.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_tokens": MAX_TOKENS * (2 if "BATCH INTAKE" in directive else 1),
            },
            {"Authorization": f"Bearer {client.api_key}"},
        )
        content = (res.get("choices") or [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("LLM reply was not a JSON object")
        moves = _parse_moves(
            parsed.get("moves"),
            candidate_refs,
            _title_map(papers, templates),
            MAX_BATCH_CARDS if "BATCH INTAKE" in directive else MAX_CARDS,
        )
        reply_text = _clean_reply(
            str(parsed.get("text", "")).strip(),
            papers,
            templates,
            decision_followup,
            directive,
            user_text=text,
            has_cards=bool(moves),
            next_question=next_question,
        )
    except Exception as exc:  # noqa: BLE001 - any provider/parse failure degrades
        log.warning("LLM conversation turn unavailable: %s", exc)
        return None
    if not reply_text and not moves:
        log.warning("LLM conversation turn produced no usable content, falling back")
        return None
    return Turn(text=reply_text or "(no reply text)", moves=moves, match_query=None)
