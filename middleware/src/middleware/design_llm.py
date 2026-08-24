"""LLM-driven design-conversation proposals (FR-CONV-1.4)."""

from __future__ import annotations

import json
import logging

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

_HOUSE_STYLE = (
    "VOICE. Write like a methodologist talking to a colleague: plain, direct, "
    "unhedged. Short sentences. Say what is grounded and what is not. Never "
    "sell, never congratulate, never open with a compliment.\n"
    "PACE. Keep the reply text to at most two short sentences, about 35 words. "
    "Ask no more than one question and propose at most one move per turn. Keep "
    "the next step small, but let the researcher redirect, defer, or answer in "
    "their own order. Do not turn the conversation into a checklist. Do not "
    "bundle a participant question with a separate research-question, measure, "
    "or design proposal.\n"
    "PUNCTUATION: do not use em dashes (the long dash). Use a full stop, a "
    "comma, a colon, or brackets instead. One idea per sentence beats one "
    "sentence with a dash in the middle. Do not use semicolons to join two "
    "independent clauses either; start a new sentence.\n\n"
    "DECISION CONTRACT. When proposals are permitted and the researcher is not "
    "asking you to explain a previous turn, do not return prose alone if the "
    "next safe decision is clear. Return exactly one actionable move card with "
    "the reply. A card is the platform's unit of progress: the researcher can "
    "accept it, reject it, or correct it. Return no move only when the turn is "
    "a follow-up explanation, a methodological caution, or a genuinely unsafe "
    "guess.\n\n"
    "CARD ORDER. A turn that contains a move card is a decision sheet. Its text "
    "must explain the proposal or why it matters, and must not ask the next "
    "protocol question. The next question is emitted only in the follow-up "
    "turn after the researcher accepts, rejects, or notes the card. Never put "
    "a forward-looking question before or beside a new move card.\n\n"
    "UNCERTAINTY. 'I do not know', 'not sure', 'you decide', 'whatever is best', "
    "'later', and 'skip' are valid instructions, not failed answers. Never repeat "
    "the same question because the researcher is uncertain. Choose a conservative "
    "default when one is defensible and label it as a recommendation, or leave the "
    "choice open and move to another useful decision. The researcher may redirect "
    "the conversation at any time.\n\n"
)

SYSTEM_PROMPT = (
    _HOUSE_STYLE
    + "You are the design-conversation partner for a human-AI developer study "
    "platform. A researcher describes a study idea in plain language. Help "
    "them DERIVE a good, methodologically sound protocol, ask a clarifying "
    "question when the idea is ambiguous, then propose concrete design moves "
    "they accept or reject.\n\n"
    "Each move's `proposal` is ONE specific, actionable sentence a researcher "
    "can accept as-is: name the concrete research question, measure, "
    "parameter, or design, never a vague gesture ('consider your measures'). "
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
    "agentCapture) and its patch always needs `section: \"instruments\"`, "
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
    "describes the work, propose one `declare-task` move at a time, combining "
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
    "Reply with a single JSON object, no prose outside it:\n"
    '{"text": "conversational reply, no inline citations - refs live only '
    'in moves[].refs", '
    '"moves": [{"kind": "...", "target": "researchQuestions[]", "proposal": '
    '"one sentence", "patch": {...} or null, "refs": ["..."]}]}\n\n'
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
    '- caution: patch is always null.'
)


_STATE_PROPOSAL_CHARS = 140


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
        for e in entries:
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
    paper_lines = [f"- {p['ref']}: {p.get('title', '')}" for p in papers]
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
            return {
                "templateId": template_id,
                "parameters": patch.get("parameters") or {},
            }
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
            return {"op": "set-field", "path": list(path), "value": patch["value"]}
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
        return frozenset(
            t["templateId"] for t in template_registry.list_templates()
        )
    except Exception:  # noqa: BLE001 - degrade, never break a turn
        return frozenset()


def _parse_moves(
    raw_moves: object, candidate_refs: set[str]
) -> tuple[ProposedMove, ...]:
    known_templates = _known_template_ids()
    out = []
    for m in raw_moves if isinstance(raw_moves, list) else []:
        if not isinstance(m, dict):
            continue
        kind = m.get("kind")
        if kind not in _ALLOWED_KINDS:
            continue
        proposal = str(m.get("proposal", "")).strip()
        if not proposal:
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
        out.append(ProposedMove(kind, str(m.get("target", "")), proposal, patch, refs))
    return tuple(out)


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

    def feed(self, chunk: str) -> str:
        """Return whatever prose this chunk contributed (often "")."""
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
                    out.append(self.feed(chunk_tail))
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
):
    """:func:`propose_turn`, yielding the reply's prose as it arrives."""
    stream = getattr(client, "stream", None)
    if stream is None:
        return propose_turn(
            client, text, history, papers, templates, directive,
            design_state=design_state,
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
                "max_tokens": 768,
            },
            {"Authorization": f"Bearer {client.api_key}"},
        ):
            body += piece
            prose = extractor.feed(piece)
            if prose:
                yield prose
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError("LLM reply was not a JSON object")
        reply_text = str(parsed.get("text", "")).strip()
    except Exception as exc:  # noqa: BLE001 - any provider/parse failure degrades
        log.warning("streaming conversation turn failed, falling back: %s", exc)
        return propose_turn(
            client, text, history, papers, templates, directive,
            design_state=design_state,
        )
    moves = _parse_moves(parsed.get("moves"), candidate_refs)
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
                "max_tokens": 768,
            },
            {"Authorization": f"Bearer {client.api_key}"},
        )
        content = (res.get("choices") or [{}])[0].get("message", {}).get("content", "")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("LLM reply was not a JSON object")
        reply_text = str(parsed.get("text", "")).strip()
    except Exception as exc:  # noqa: BLE001 - any provider/parse failure degrades
        log.warning(
            "LLM conversation turn unavailable: %s", exc
        )
        return None
    moves = _parse_moves(parsed.get("moves"), candidate_refs)
    if not reply_text and not moves:
        log.warning("LLM conversation turn produced no usable content, falling back")
        return None
    return Turn(text=reply_text or "(no reply text)", moves=moves, match_query=None)
