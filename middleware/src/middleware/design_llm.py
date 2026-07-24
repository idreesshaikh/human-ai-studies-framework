"""LLM-driven design-conversation proposals (FR-CONV-1.4).

The design conversation's degradation path (``design_assistant._pick_script``)
stays exactly as it is — this module is the LLM seam that swaps in *ahead*
of it when a provider is configured (``assistant.make_client``), never a
second, parallel path to the compiled protocol.

**Cite-what-you-retrieved, enforced twice.** Retrieval happens first,
unconditionally, via the platform's existing deterministic tools
(``matching.match_papers``, ``design_assistant.recommend_templates``)
*before* the model ever runs. The model only ever rephrases and selects
against that closed, already-retrieved candidate menu — it never gets to
invent what to search for and cite in the same breath. Any ``ref`` the
model returns that isn't in the menu is dropped here; whatever survives is
checked *again*, unchanged, by ``design_assistant._resolve_grounding``
(which drops anything that doesn't resolve to a real corpus row). Wall #3
(FR-CONV-2, "cite only what you retrieved") is enforced by construction at
both boundaries, not trusted from the model's output.

Mirrors ``matching.rerank_with_llm``'s shape exactly: one
``try/except Exception`` around the whole call, log + return ``None`` on
any failure, so ``design_assistant.respond`` always has the scripted
assistant to fall back to (NFR-4/5 - degrade, never break).
"""

from __future__ import annotations

import json
import logging

from middleware.design_assistant import Script, ScriptedMove

log = logging.getLogger(__name__)

#: The only move kinds the compiler/UI understand (mirrors the kinds the
#: scripted assistant's own Script objects already use) - an unrecognized
#: kind is dropped, never passed through blind.
_ALLOWED_KINDS = frozenset(
    {
        "add-rq",
        "add-measure",
        "set-parameter",
        "choose-template",
        "add-instrument",
        "reconfigure-instrument",
        "caution",
    }
)

#: Draft sections a generic append/set patch may target (``compiler.py``'s
#: ``SECTIONS``, minus "design" and "instruments" which have their own
#: dedicated kinds/shapes, validated separately below).
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

#: Rendered into SYSTEM_PROMPT so the model's `patch.section` choices always
#: match what `_validate_patch` actually accepts — drifting these apart is
#: exactly what silently drops a move's patch (it still renders and can
#: still be "accepted", but never lands in the compiled draft).
_SECTION_LIST = ", ".join(sorted(_PATCHABLE_SECTIONS))

SYSTEM_PROMPT = (
    "You are the design-conversation partner for a human-AI developer study "
    "platform. A researcher describes a study idea in plain language; help "
    "them DERIVE a good, methodologically sound protocol — ask a clarifying "
    "question when the idea is ambiguous, then propose concrete design moves "
    "they accept or reject. Offer, don't lead.\n\n"
    "Each move's `proposal` is ONE specific, actionable sentence a researcher "
    "can accept as-is: name the concrete research question, measure, "
    "parameter, or design — never a vague gesture ('consider your measures'). "
    "Across the conversation aim for a complete protocol: cover the mandatory "
    "sections, pair any self-report with an objective measure, and raise a "
    "`caution` when a choice risks a known validity threat. When the turn "
    "carries a design-state block, use its coverage line to pick targets: "
    "prioritize moves for the EMPTY sections over adding more to already "
    "filled ones. The typical order once design and measures are set: "
    "participants (population, sample size), then statisticalPlan — but when "
    "an accepted template already prescribes the statistics, never propose a "
    "standalone statisticalPlan move.\n\n"
    "REPETITION: NEVER re-propose a move the design state lists as accepted, "
    "rejected, or awaiting decision — nor a near-duplicate or rewording of "
    "one. An accepted move is already in the draft; a rejected one was "
    "declined for a reason (address the reason in your reply text if "
    "relevant, but do not pitch the move again). Every move you propose "
    "must be genuinely new.\n\n"
    "GROUNDING — prefer papers. You may cite ONLY the papers and templates in "
    "the candidate menu given to you this turn (never one you were not given). "
    "The menu is retrieved to be relevant, so MOST moves should carry at least "
    "one `ref` from it — reach for the grounding. Leave `refs` empty ONLY for "
    "a genuine researcher-judgment call the literature can't settle (a scoping "
    "or tuning decision); that should be the exception, not the norm. Never "
    "fabricate a citation, but do not leave a move unsourced when a fitting "
    "candidate is right there.\n\n"
    "IMPORTANT: the protocol's `design` section (its overall shape - RCT, "
    "crossover, pre/post, etc. - and prescribed statistics) can ONLY be set "
    "by a choose-template move; no other move kind can ever fill it, no "
    "matter how many research questions, measures, or parameters get "
    "accepted. A conversation that never proposes one can never reach a "
    "compilable protocol. Whenever the researcher asks about design, "
    "statistics, or a specific study type (an RCT, a within-subjects/"
    "crossover study, a pre/post study, etc.) - even loosely worded - "
    "always include a choose-template move for whichever candidate "
    "template fits best, alongside any other moves. Only omit it if truly "
    "none of the candidate templates fit at all, and say so explicitly in "
    "the reply text.\n\n"
    "Reply with a single JSON object, no prose outside it:\n"
    '{"text": "conversational reply, no inline citations - refs live only '
    'in moves[].refs", '
    '"moves": [{"kind": "...", "target": "protocol.path", "proposal": '
    '"one sentence", "patch": {...} or null, "refs": ["..."]}]}\n\n'
    "Valid kinds: add-rq, add-measure, set-parameter, choose-template, "
    "add-instrument, reconfigure-instrument, caution. `refs` entries must "
    "come from the candidate menu only (a paper's ref or a template's id).\n\n"
    "`patch` shapes (anything else is dropped and the move never reaches "
    "the draft, even if accepted):\n"
    f'- add-rq, add-measure, set-parameter: {{"section": one of '
    f'[{_SECTION_LIST}], "op": "append" or "set", "value": "..."}}. Pick '
    "whichever section the change actually belongs to — e.g. a sample-size "
    'or alpha parameter is "participants" or "statisticalPlan", not '
    '"parameters" (not a real section).\n'
    '- choose-template: {"templateId": "...", "parameters": {...}}\n'
    '- add-instrument: {"section": "instruments", "op": "add-instrument" or '
    '"set-instrument", "name": "...", "config": {...}}\n'
    '- reconfigure-instrument: {"section": "instruments", "op": '
    '"reconfigure", "name": "...", "path": ["..."], "value": ...}\n'
    '- caution: patch is always null.'
)


#: Proposal truncation when rendering the design-state block (render-time
#: only — dedup in ``design_assistant`` always compares full texts).
_STATE_PROPOSAL_CHARS = 140


def _clip(text: str) -> str:
    if len(text) <= _STATE_PROPOSAL_CHARS:
        return text
    return text[: _STATE_PROPOSAL_CHARS - 1] + "…"


def _design_state_block(state: dict | None) -> str:
    """Render ``design_assistant._load_design_state`` for the user message:
    every prior move by decision status plus the draft's coverage — the
    structured facts the prose history can't carry, and what the prompt's
    REPETITION and coverage rules key on. Empty string when there's no
    state (no study / no moves yet)."""
    if not state:
        return ""
    lines = ["Design state so far:"]
    for title, bucket in (
        ("Accepted (already in the draft — do not re-propose):", "accepted"),
        ("Rejected (the researcher said no — do not re-pitch):", "rejected"),
        ("Awaiting decision (do not duplicate):", "proposed"),
    ):
        entries = state.get(bucket) or []
        lines.append(title)
        if not entries:
            lines.append("- (none)")
        for e in entries:
            lines.append(f"- {e['kind']} [{e['section']}]: {_clip(e['proposal'])}")
    filled = ", ".join(state.get("filled") or []) or "(none)"
    empty = ", ".join(state.get("empty") or []) or "(none)"
    lines.append(f"Draft coverage — filled: {filled}. Empty: {empty}.")
    if state.get("templateId"):
        lines.append(
            f"Template {state['templateId']} is accepted; its statisticalPlan "
            "is prescribed — do not propose a standalone statisticalPlan move."
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
    """Structural check against the compiler's known op shapes
    (``compiler.py``'s ``compile_sections``/``_apply_instrument_moves``/
    ``_accepted_template_moves``). Anything that doesn't match is dropped - the
    move still renders (informational, no draft change) rather than an
    unvalidated shape ever reaching the compiler."""
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
    if kind == "add-instrument":
        if (
            patch.get("section") == "instruments"
            and patch.get("op") in ("add-instrument", "set-instrument")
            and isinstance(patch.get("name"), str)
            and patch.get("name")
            and isinstance(patch.get("config"), dict)
        ):
            return patch
        return None
    if kind == "reconfigure-instrument":
        if (
            patch.get("section") == "instruments"
            and patch.get("op") == "reconfigure"
            and isinstance(patch.get("name"), str)
            and patch.get("name")
            and isinstance(patch.get("path"), list)
            and patch["path"]
            and all(isinstance(p, str) for p in patch["path"])
            and "value" in patch
        ):
            return patch
        return None
    # add-rq / add-measure / set-parameter: a generic section append/set.
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
    """Coerce a section-patch value to what the sections actually hold.

    Every list-valued protocol section holds strings; the model sometimes
    sends a number, or packs several entries into one list ("Two
    conditions: A vs. B" as ``["A", "B"]`` — the compiler flattens a list
    into one entry per item). Anything that can't become clean strings
    (a dict, an empty list) drops the patch."""
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
    """Every template id the registry can actually instantiate. A registry
    read failure returns the empty set — the turn degrades (template moves
    dropped) rather than raising into the conversation."""
    from middleware import template_registry

    try:
        return frozenset(
            t["templateId"] for t in template_registry.list_templates()
        )
    except Exception:  # noqa: BLE001 - degrade, never break a turn
        return frozenset()


def _parse_moves(
    raw_moves: object, candidate_refs: set[str]
) -> tuple[ScriptedMove, ...]:
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
        if kind == "choose-template" and (
            patch is None or patch["templateId"] not in known_templates
        ):
            # A hallucinated template id can never instantiate, and a
            # patch-less choose-template is the "accepted but only noted"
            # trap — drop the whole move rather than offer a dud.
            continue
        raw_refs = m.get("refs")
        refs = (
            tuple(r for r in raw_refs if isinstance(r, str) and r in candidate_refs)
            if isinstance(raw_refs, list)
            else ()
        )
        out.append(ScriptedMove(kind, str(m.get("target", "")), proposal, patch, refs))
    return tuple(out)


def propose_turn(
    client,
    text: str,
    history: list[dict],
    papers: list[dict],
    templates: list[dict],
    *,
    design_state: dict | None = None,
) -> Script | None:
    """Ask the configured LLM provider for this turn's prose + proposed
    moves, constrained to ``papers``/``templates`` already retrieved this
    exchange (both built by the caller *before* this call, via the
    existing deterministic ``matching.match_papers`` /
    ``design_assistant.recommend_templates``). ``history`` is prior turns
    as ``{"role": "user"|"assistant", "content": str}`` dicts;
    ``design_state`` (``design_assistant._load_design_state``) carries the
    structured accepted/rejected/undecided moves + draft coverage the
    prose history can't — rendered into the user message so the model
    can avoid repetition and steer at the empty sections.

    Returns ``None`` on any failure - bad key, timeout, malformed JSON,
    or a reply with neither usable text nor any valid move. The caller
    (``design_assistant.respond``) falls back to the scripted assistant;
    this function never raises and never returns a partial/hybrid result.
    """
    candidate_refs = {p["ref"] for p in papers if p.get("ref")}
    candidate_refs |= {t["templateId"] for t in templates if t.get("templateId")}
    menu = _candidate_menu(papers, templates)
    content = f"{text}\n\nCandidate menu this turn:\n{menu}"
    state_block = _design_state_block(design_state)
    if state_block:
        content += f"\n\n{state_block}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": content},
    ]
    try:
        res = client.post(
            client.base_url,
            {
                "model": client.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_tokens": 1536,
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
            "LLM conversation turn unavailable, falling back to scripted: %s", exc
        )
        return None
    moves = _parse_moves(parsed.get("moves"), candidate_refs)
    if not reply_text and not moves:
        log.warning("LLM conversation turn produced no usable content, falling back")
        return None
    return Script(text=reply_text or "(no reply text)", moves=moves, match_query=None)
