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
    "`caution` when a choice risks a known validity threat.\n\n"
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
    "compilable protocol — so once the study is understood well enough, "
    "propose the template that fits, and say so explicitly in the reply text "
    "if truly none of the candidates fit.\n\n"
    "BUT NOT YET, AND NOT BLIND. A design shape is a *consequence* of who "
    "takes part, what they do, what is compared, what is measured, and what "
    "is practically possible. Naming a shape before you know those boxes the "
    "researcher into a design chosen from almost nothing, which is worse than "
    "asking. The turn instruction below tells you which of these the "
    "conversation still doesn't know and whether you may propose a design "
    "yet; follow it exactly. While you are still learning the study, ask ONE "
    "genuine question at a time (never a list of five), reflect back what you "
    "understood so they can correct you, and propose only moves that are "
    "already safe — a research question in their own words, a measure they "
    "named themselves, a caution.\n\n"
    "ANSWER WHAT WAS ASKED. If the researcher asks about something you "
    "already said — 'why did you propose that?', 'what do you mean?', 'on "
    "what basis?' — then ANSWER IT, in the reply text, referring to the "
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


class _ReplyTextExtractor:
    """Pull the value of the reply's leading ``"text"`` field out of a JSON
    object *as it streams*.

    The design turn is one structured JSON completion — prose plus moves —
    and the prompt puts ``text`` first, so its characters arrive long before
    the moves do. Feeding raw JSON to the UI would show the researcher
    braces; this hands back only the prose fragments, decoded, and stops at
    the closing quote. Purely additive: the full body is still parsed
    normally at the end, so a stream this misreads costs a live preview, not
    the reply.
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
                    # Keep only enough tail to still match a split marker.
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
) -> list[dict]:
    """The chat messages for one design turn.

    ``directive`` is this turn's stance — who is being talked to, what the
    conversation still doesn't understand, and whether a design may be
    proposed yet — sent as its own system message *after* the history so it
    cannot be mistaken for something the researcher said, and so it outranks
    the general instructions for this turn.
    """
    menu = _candidate_menu(papers, templates)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        *([{"role": "system", "content": directive}] if directive else []),
        {"role": "user", "content": f"{text}\n\nCandidate menu this turn:\n{menu}"},
    ]


def propose_turn_streaming(
    client,
    text: str,
    history: list[dict],
    papers: list[dict],
    templates: list[dict],
    directive: str = "",
):
    """:func:`propose_turn`, yielding the reply's prose as it arrives.

    A generator: it yields prose fragments, and its ``return`` value (via
    ``StopIteration.value``) is the same ``Script | None`` as the blocking
    call — so a caller gets live text *and* the identical validated moves,
    with the same never-raises, degrade-to-scripted contract. A provider
    without a ``stream`` seam, or any streaming failure, falls back to the
    blocking call rather than losing the turn.
    """
    stream = getattr(client, "stream", None)
    if stream is None:
        return propose_turn(client, text, history, papers, templates, directive)

    candidate_refs = {p["ref"] for p in papers if p.get("ref")}
    candidate_refs |= {t["templateId"] for t in templates if t.get("templateId")}
    messages = _messages(text, history, papers, templates, directive)
    extractor = _ReplyTextExtractor()
    body = ""
    try:
        for piece in stream(
            client.base_url,
            {
                "model": client.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
                "max_tokens": 1536,
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
        return propose_turn(client, text, history, papers, templates, directive)
    moves = _parse_moves(parsed.get("moves"), candidate_refs)
    if not reply_text and not moves:
        log.warning("LLM conversation turn produced no usable content, falling back")
        return None
    return Script(text=reply_text or "(no reply text)", moves=moves, match_query=None)


def propose_turn(
    client,
    text: str,
    history: list[dict],
    papers: list[dict],
    templates: list[dict],
    directive: str = "",
) -> Script | None:
    """Ask the configured LLM provider for this turn's prose + proposed
    moves, constrained to ``papers``/``templates`` already retrieved this
    exchange (both built by the caller *before* this call, via the
    existing deterministic ``matching.match_papers`` /
    ``design_assistant.recommend_templates``). ``history`` is prior turns
    as ``{"role": "user"|"assistant", "content": str}`` dicts.

    Returns ``None`` on any failure - bad key, timeout, malformed JSON,
    or a reply with neither usable text nor any valid move. The caller
    (``design_assistant.respond``) falls back to the scripted assistant;
    this function never raises and never returns a partial/hybrid result.
    """
    candidate_refs = {p["ref"] for p in papers if p.get("ref")}
    candidate_refs |= {t["templateId"] for t in templates if t.get("templateId")}
    messages = _messages(text, history, papers, templates, directive)
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
