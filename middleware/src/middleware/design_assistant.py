"""The design assistant: one researcher turn in, one platform turn out."""

from __future__ import annotations

import difflib
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from protocol.capture import producer_capabilities
from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import compiler, elicitation, matching
from middleware.db import ConversationTurn, DesignMoveRow, ProtocolDraftRow
from middleware.template_registry import list_templates

log = logging.getLogger(__name__)

# The accepted/rejected move ledger and compiled draft carry the durable state. Keep
# the opening brief plus a short recent window, so old prose cannot make every reply
# slower or crowd out the study's original aim.
_LLM_HISTORY_TURNS = 8
_LLM_HISTORY_TEXT_CHARS = 1_200

_STATE_MOVE_CAP = 30
_BATCH_MOVE_CAP = 8
_GROUP_MOVE_CAP = 3

# Near-duplicate thresholds (tunable): two moves are the same move when their content
# terms overlap this much (denominator: the smaller term set, so a short prior move
# can't swallow a longer distinct one) or their full texts are this similar.
_DUP_TOKEN_OVERLAP = 0.8
_DUP_SEQ_RATIO = 0.85
_DUP_MIN_TERMS = 3
_RECENT_PLATFORM_TURNS = 8


_DESIGN_INTENT_WORDS = ("design", "statistic", "test", "how many", "template")

_NAMED_DESIGN_SCORE = 2
# Designs a researcher can state outright, mapped to the template that realises them.
_STATED_DESIGN_TEMPLATES = {
    "within-subjects": "within-subjects-crossover-v1",
    "between-subjects": "two-group-rct-v1",
}


TURN_ATTEMPTS = 3
TURN_RETRY_DELAY_SECONDS = 0.25


def holding_turn(reason: str, stance: dict | None = None) -> dict:
    """What the conversation returns when it could not reach a model."""
    return {
        "text": reason,
        "moves": [],
        "recommendations": [],
        "templateRecommendations": [],
        "prescription": None,
        "figureSuggestions": [],
        "understanding": (stance or {}).get("understanding"),
        "turnIntent": (stance or {}).get("intent"),
        "retrievedRefs": [],
        "source": "unavailable",
    }


SCOPE_REDIRECT = (
    "PHOENIX is for task-based human–AI software-development studies. It can "
    "configure TERN sessions in VS Code, capture what developers do and what "
    "the AI does, and prepare the resulting dataset. This idea is outside that "
    "lane, so I will not keep asking protocol questions. Use a coding task with "
    "an AI-assisted versus unassisted comparison if that is the study you want "
    "to run."
)

SCOPE_CLARIFICATION = (
    "PHOENIX is built for task-based studies of people using AI while developing "
    "software in VS Code. Is your study about a coding task and an AI-assisted "
    "versus unassisted comparison? Other study types are outside this workspace."
)


NO_MODEL = (
    "No language model is connected. Templates and the checklist still work. "
    "Set LLM_API_KEY or a local LLM_BASE_URL on the server to enable "
    "replies."
)
MODEL_SILENT = (
    "The model did not respond. Your message is saved and nothing was applied. "
    "Retry in a minute, or author the protocol manually."
)


class ModelUnavailable(RuntimeError):
    """The design conversation could not reach a language model."""


def _propose_with_retry(
    client,
    text: str,
    history: list[dict],
    papers: list[dict],
    templates: list[dict],
    directive: str,
    state: dict | None,
    decision_followup: bool = False,
    next_question: str = "",
) -> Turn | None:
    """Make bounded, spaced retries for a transient model request failure."""
    from middleware import design_llm

    for attempt in range(TURN_ATTEMPTS):
        turn = design_llm.propose_turn(
            client,
            text,
            history,
            papers,
            templates,
            directive,
            design_state=state,
            decision_followup=decision_followup,
            next_question=next_question,
        )
        if turn is not None:
            return turn
        if attempt + 1 < TURN_ATTEMPTS:
            delay = TURN_RETRY_DELAY_SECONDS * (2**attempt)
            log.info(
                "design turn attempt %d/%d produced nothing; retrying in %.2fs",
                attempt + 1,
                TURN_ATTEMPTS,
                delay,
            )
            time.sleep(delay)
    return None


def recommend_templates(
    text: str, *, support: dict[str, int] | None = None
) -> list[dict[str, Any]]:
    """Recommend design archetype templates matching the researcher's input."""
    q = text.lower()
    templates = list_templates()
    scored: list[tuple[int, dict[str, Any]]] = []

    keywords = {
        "two-group-rct": [
            "between-subjects",
            "two group",
            "independent group",
            "control group",
            "random assignment",
            "rct",
            "randomized controlled",
            "randomised controlled",
            "randomized trial",
            "randomised trial",
            "random control",
            "randomly assign",
        ],
        "within-subjects-crossover": [
            "within-subjects",
            "crossover",
            "paired",
            "both conditions",
            "repeated",
        ],
        "paired-pre-post": [
            "pre-post",
            "before after",
            "pre and post",
            "intervention",
            "training effect",
        ],
        "multi-arm-rct": [
            "multi-arm",
            "multiple groups",
            "three group",
            "several conditions",
            "multiple treatments",
        ],
        "factorial-2x2": [
            "factorial",
            "two factors",
            "interaction",
            "2x2",
            "main effect",
        ],
        "single-group-repeated-measures": [
            "longitudinal",
            "over time",
            "time point",
            "repeated measure",
            "trend",
            "trajectory",
        ],
        "two-proportion-mcnemar": [
            "binary",
            "pass fail",
            "proportion",
            "success rate",
            "completion rate",
        ],
        "single-arm-benchmark": [
            "benchmark",
            "single arm",
            "descriptive",
            "exploratory",
            "evaluation",
            "pilot study",
        ],
    }

    for t in templates:
        tid = t.get("templateId", "")
        profile = [
            *keywords.get(tid, keywords.get(tid.replace("-v1", ""), [])),
            *(str(p).lower() for p in t.get("designSignature", []) or []),
        ]
        score = sum(2 for kw in dict.fromkeys(profile) if kw in q)
        if t.get("designType") and t["designType"].lower().replace("-", " ") in q:
            score += 3
        if t.get("title") and any(w in q for w in t["title"].lower().split()):
            score += 1
        if score > 0:
            scored.append((score, t))

    scored.sort(
        key=lambda x: (
            -x[0],
            -(support or {}).get(x[1].get("templateId", ""), 0),
            x[1].get("templateId", ""),
        )
    )
    if not scored and any(w in q for w in _DESIGN_INTENT_WORDS):
        scored = [(0, t) for t in templates]
    return [
        {
            "templateId": t["templateId"],
            "title": t.get("title", ""),
            "description": t.get("description", ""),
            "designType": t.get("designType", ""),
            "designShape": t.get("statisticalPlan", {}).get("designShape", ""),
            "matchScore": score,
            "matchReason": (
                f"Matched {score} keyword(s): researcher intent"
                if score > 0
                else "No specific match, offered from the full catalog"
            ),
        }
        for score, t in scored[:4]
    ]


def corpus_support(s: Session) -> dict[str, int]:
    """Per-template corpus usage from the repertoire, for tie-breaking."""
    try:
        from middleware import template_repertoire

        return {e["id"]: e["support"] for e in template_repertoire.rank_repertoire(s)}
    except Exception as exc:  # noqa: BLE001 - a tie-break is never worth a 500
        log.warning("repertoire support unavailable for tie-breaking: %s", exc)
        return {}


def recommend_prescription(design_shape: str) -> dict[str, Any] | None:
    """Look up the prescription for a design shape."""
    try:
        from analysis.prescribe import prescribe

        p = prescribe(design_shape)
        if p is None:
            return None
        return {
            "designShape": p.design_shape,
            "test": p.test,
            "effectSize": p.effect_size,
            "correction": p.correction,
            "sampleSizeGuidance": p.sample_size_guidance,
            "rationale": p.rationale,
        }
    except ImportError:
        return None


def suggest_figures(result_shape: str) -> list[dict[str, Any]]:
    """Get ranked figure suggestions for a result shape."""
    try:
        from analysis.suggest_figures import suggest_figures as sf

        figs = sf(result_shape)
        return [
            {
                "rank": f.rank,
                "figureType": f.figure_type,
                "description": f.description,
                "rationale": f.rationale,
                "whenToUse": f.when_to_use,
            }
            for f in figs
        ]
    except ImportError:
        return []


@dataclass
class ProposedMove:
    """A design move before grounding is resolved."""

    kind: str
    target: str
    proposal: str
    patch: dict | None
    refs: tuple[str, ...]


@dataclass
class Turn:
    """One platform response: prose + the moves it proposes."""

    text: str
    moves: tuple[ProposedMove, ...]
    match_query: str | None = None


_REVISION = re.compile(
    r"\b(?:change|set|make|update|increase|raise|reduce|lower|bump)\b[^.\d]{0,40}?"
    r"\b(?P<what>participants?|sessions?|session length|session duration)\b"
    r"[^.\d]{0,20}?\bto\s+(?P<n>\d{1,4})\b(?P<unit>\s*(?:min(?:ute)?s?)\b)?",
    re.IGNORECASE,
)


def _revision_moves(text: str) -> tuple[ProposedMove, ...]:
    """A researcher revising a number already in the draft ("change participants to
    20"), which the fact listener only recognises when it is phrased as a plan."""
    match = _REVISION.search(text or "")
    if not match:
        return ()
    number = int(match.group("n"))
    what = match.group("what").lower()
    if what.startswith("participant"):
        path, proposal = (
            ["participants", "planned"],
            (f"Plan for {number} participants."),
        )
    elif what == "sessions" and not match.group("unit"):
        return ()
    else:
        path, proposal = (
            ["session", "durationMinutes"],
            (f"Run each session for {number} minutes."),
        )
    return (
        ProposedMove(
            kind="set-field",
            target=".".join(path),
            proposal=proposal,
            patch={"op": "set-field", "path": path, "value": number},
            refs=(),
        ),
    )


def _with_scripted_design(turn: Turn, text: str) -> Turn:
    """Add the best-matching template as a reviewable design card, when none exists.

    Used only when the model cannot answer: the design card normally comes from the
    model, and a pasted brief should not lose it. Offered only for a clear match, so
    nothing is invented from a weak signal.
    """
    if any(m.kind in ("choose-template", "merge-templates") for m in turn.moves):
        return turn
    stated = next(
        (
            m.patch.get("value")
            for m in turn.moves
            if m.target == "participants.design" and m.patch
        ),
        None,
    )
    ranked = recommend_templates(text)
    template_id = _STATED_DESIGN_TEMPLATES.get(stated)
    if template_id is None:
        # Without a stated design, only a clear winner is offered; a tie is a guess.
        if not ranked or ranked[0]["matchScore"] < _NAMED_DESIGN_SCORE:
            return turn
        if len(ranked) > 1 and ranked[1]["matchScore"] == ranked[0]["matchScore"]:
            return turn
        template_id = ranked[0]["templateId"]
    title = next(
        (t.get("title") for t in list_templates() if t["templateId"] == template_id),
        None,
    )
    move = ProposedMove(
        kind="choose-template",
        target="design",
        proposal=f"Use the {title or template_id} design.",
        patch={"templateId": template_id, "parameters": {}},
        refs=(),
    )
    return Turn(text=turn.text, moves=(*turn.moves, move), match_query=turn.match_query)


def _explicit_moves(text: str) -> tuple[ProposedMove, ...]:
    """Convert facts the researcher stated plainly into reviewable moves."""
    moves = tuple(
        ProposedMove(
            kind=item["kind"],
            target=item["target"],
            proposal=item["proposal"],
            patch=item["patch"],
            refs=tuple(item.get("refs") or ()),
        )
        for item in elicitation.explicit_protocol_facts(text)
    )
    taken = {tuple((m.patch or {}).get("path") or ()) for m in moves}
    return moves + tuple(
        m for m in _revision_moves(text) if tuple(m.patch["path"]) not in taken
    )


def _template_source_refs(template_id: str | None) -> tuple[str, ...]:
    """
    The paper refs a template cites as its design's sources  -  used to ground
    a choose-template move.
    """
    if not template_id:
        return ()
    try:
        from middleware import template_registry

        tpl = template_registry.load_template(template_id)
        return tuple(
            src["paperRef"] for src in tpl.get("source", []) if src.get("paperRef")
        )
    except Exception:  # noqa: BLE001 - a missing/invalid template just = no grounding
        return ()


def _resolve_grounding(s: Session, refs: tuple[str, ...]) -> list[dict]:
    """Build grounding from corpus rows only  -  cite-what-you-retrieved."""
    grounding = []
    for ref in refs:
        meta = matching.get_paper_metadata(s, ref)
        if meta is None:
            continue
        grounding.append(
            {
                "ref": meta["ref"],
                "confidence": meta.get("confidence"),
                "title": meta["title"],
                "year": meta.get("year"),
                "venue": meta.get("venue", ""),
                "why": meta.get("why", ""),
            }
        )
    return grounding


def _load_history(s: Session, study_id: str | None) -> list[dict]:
    """
    A compact prompt history: the opening researcher brief plus a recent window.

    Design moves are deliberately absent. Their complete, authoritative state is sent
    separately in ``design_state``; replaying it in prose wastes context and becomes
    especially noisy in long conversations.
    """
    if study_id is None:
        return []
    recent = (
        s.execute(
            select(ConversationTurn)
            .where(ConversationTurn.study_id == study_id)
            .order_by(ConversationTurn.seq.desc())
            .limit(_LLM_HISTORY_TURNS)
        )
        .scalars()
        .all()
    )
    opening = s.scalar(
        select(ConversationTurn)
        .where(
            ConversationTurn.study_id == study_id,
            ConversationTurn.role == "researcher",
        )
        .order_by(ConversationTurn.seq)
        .limit(1)
    )
    rows = list(reversed(recent))
    if opening is not None and all(row.id != opening.id for row in rows):
        rows.insert(0, opening)

    history: list[dict] = []
    for row in rows:
        # A holding turn ("no model configured", "the provider is down") is
        # persisted now so the UI can show it again after a reload
        # (app.py's ModelUnavailable branches), but it is not a real answer
        # and must never be replayed to the model as if one of its own past
        # turns said it  -  skip it here the same way an empty turn is skipped
        # below.
        if row.role == "platform" and row.source == "unavailable":
            continue
        content = row.text or ""
        # Card decisions are already represented structurally by the move status and
        # the current request's ``decision`` payload. Replaying the synthetic
        # “I accepted …” researcher echo wastes context and encourages the model to
        # echo it back as if it were a new research idea.
        if row.role == "researcher" and content.lower().startswith(
            ("i accepted:", "i rejected the proposed", "i noted the caution")
        ):
            continue
        if not content:
            continue
        if len(content) > _LLM_HISTORY_TEXT_CHARS:
            content = content[: _LLM_HISTORY_TEXT_CHARS - 1].rstrip() + "…"
        history.append(
            {
                "role": "user" if row.role == "researcher" else "assistant",
                "content": content,
            }
        )
    return history


def researcher_texts(s: Session, study_id: str | None) -> list[str]:
    """Everything the *researcher* has said in this study, oldest first."""
    if study_id is None:
        return []
    return list(
        s.scalars(
            select(ConversationTurn.text)
            .where(
                ConversationTurn.study_id == study_id,
                ConversationTurn.role == "researcher",
            )
            .order_by(ConversationTurn.seq)
        )
    )


def _names_template_id(text: str, templates: list[dict]) -> bool:
    """Whether the researcher's own words name a specific template by id.

    The repertoire's "describe your study instead" entry point seeds a study's
    opening turn with the template ids the researcher already selected, so the
    assistant proposes the merge immediately instead of asking again which
    shapes they mean. Naming an id is naming a design  -  an explicit ask must
    never be overruled by the facet gate."""
    q = (text or "").lower()
    return any(t.get("templateId") and t["templateId"].lower() in q for t in templates)


def turn_stance(
    s: Session,
    text: str,
    *,
    study_id: str | None = None,
    profile: str | None = None,
    steer: str | None = None,
    decision: dict | None = None,
    state: dict | None = None,
) -> dict:
    """What this turn is, how much is understood, and what may be proposed."""
    prior = researcher_texts(s, study_id)
    scope = elicitation.classify_scope([*prior, text])
    understanding = elicitation.assess_understanding([*prior, text])
    for facet in elicitation.FACETS:
        if _facet_settled_in_state(facet, state):
            understanding[facet] = True
    explicit_moves = _explicit_moves(text)
    intent = elicitation.classify_turn(text)
    batch_intake = (
        elicitation.is_complete_brief(text)
        or len(explicit_moves) > 1
        or (
            intent in {"design-request", "continue"}
            and elicitation.ready_for_design(understanding)
        )
    )
    templates = list_templates()
    # A follow-up question never counts, or "why the crossover?" would re-propose the
    # crossover.
    named_design = intent != "followup-question" and (
        any(r["matchScore"] >= _NAMED_DESIGN_SCORE for r in recommend_templates(text))
        or elicitation.names_a_design(
            text, [tpl.get("designSignature", []) for tpl in templates]
        )
        or _names_template_id(text, templates)
    )
    # A profile the caller declared is an account fact and outranks the dial; the dial's
    # implied register only fills in for someone who never set one.
    declared = profile if profile in elicitation.PROFILES else None
    decision_action = (decision or {}).get("action")
    return {
        "scope": scope,
        "batchIntake": batch_intake,
        "explicitMoves": explicit_moves,
        "intent": intent,
        "steer": steer if steer in elicitation.STEER_LEVELS else None,
        "profile": declared or elicitation.steer_profile(steer),
        "understanding": {
            **elicitation.understanding_summary(understanding),
            "protocolReady": bool((state or {}).get("compileValid")),
            "openChoices": [
                slot["label"] for slot in (state or {}).get("outstandingSlots") or []
            ],
        },
        "nextQuestion": elicitation.next_question(understanding),
        "namedDesign": named_design,
        "decisionAction": decision_action,
        # An explicit ask lowers the gate but never removes it; a follow-up question
        # never opens it, because "why did you pick that?" is not "pick one".
        "mayProposeDesign": named_design
        or elicitation.ready_for_design(
            understanding, requested=intent == "design-request"
        ),
        "mayProposeMoves": decision_action in {None, "accepted"}
        and intent != "followup-question"
        and elicitation.proposals_permitted(steer),
    }


def _scope_turn(scope: str) -> Turn:
    """Keep non-developer ideas out of the protocol elicitation loop."""
    return Turn(
        text=SCOPE_REDIRECT if scope == "out-of-scope" else SCOPE_CLARIFICATION,
        moves=(),
    )


def _explicit_turn(stance: dict, state: dict | None = None) -> Turn | None:
    """Handle an explicit answer without making the model reinterpret it."""
    moves = tuple(stance.get("explicitMoves") or ())
    if (
        not moves
        or stance.get("decisionAction")
        or stance.get("intent") == "followup-question"
    ):
        return None
    # A population phrase is useful context, but it is not yet a compiler-backed
    # protocol choice. Let the model use it as context so a short opener such as
    # "junior developers over-trust AI code" still gets grounded recommendations;
    # only intercept facts that can actually move the protocol forward.
    protocol_moves = tuple(
        move
        for move in moves
        if not (move.kind == "set-parameter" and move.target == "participants[]")
    )
    if not protocol_moves:
        return None
    moves = protocol_moves
    kept = _filter_repeated_moves(moves, state)
    if not kept:
        return Turn(
            text="That detail has already been considered. "
            + _progress_turn(state).text,
            moves=(),
        )
    count = len(kept)
    if count == 1:
        text = (
            "I captured that explicit detail from your note. Review the card and "
            "accept it if it matches your plan."
        )
    else:
        text = (
            f"I captured {count} explicit details from your note. These are your "
            "stated facts, not defaults. Review them together or accept them all "
            "if they match your plan."
        )
    return Turn(text=text, moves=kept)


def _slot_directive(state: dict | None) -> str:
    """
    The protocol's outstanding slots, as an instruction the model can act on: what is
    missing, what type each takes, and how to fill it.
    """
    advice = (state or {}).get("taskAdvice") or ""
    outstanding = (state or {}).get("outstandingSlots") or []
    if not outstanding:
        if state and state.get("compileValid") is False:
            errors = state.get("compileErrors") or [
                "the compiled draft needs correction"
            ]
            correction = "; ".join(str(error) for error in errors[:2])
            return (
                "The draft has all named choices, but it is not valid yet. "
                f"Fix this before applying it: {correction}."
            )
        complete = (
            "The protocol has every slot it needs. Do not invent more work: "
            "if the researcher is happy, tell them it is ready to compile."
        )
        # Optional, so it never blocks a compile - but a study is far more analysable
        # with tasks than without, and this is the last honest moment to say so.
        return f"{complete}\n\n{advice}" if advice else complete
    fillable = [s for s in outstanding if s["valueType"] != "derived"]
    lines = [
        "PROTOCOL SLOTS STILL OPEN (the draft can be saved and reviewed while "
        "these are unresolved): " + ", ".join(s["label"] for s in outstanding) + "."
    ]
    if fillable:
        described = "; ".join(
            f"`{s['key']}` ({s['label']}) takes {s['valueType']}"
            + (f": one of {', '.join(s['choices'])}" if s["choices"] else "")
            for s in fillable
        )
        lines.append(
            "You can fill these directly with a `set-field` move: "
            + described
            + ". Propose a fill only when the researcher has actually told "
            "you the value, or when you are proposing a sensible default and "
            "say so plainly in the reply text. Never invent a sample size or "
            "a session length and present it as theirs. Offer the first one only "
            "if the researcher has not redirected or deferred. If they defer, "
            "leave it open and help with another useful choice."
        )
    if advice:
        lines.append(advice)
    return "\n\n".join(lines)


def _directive(stance: dict, state: dict | None = None) -> str:
    """Choose the response mode from the conversation and compiled protocol."""
    lines = [
        elicitation.profile_guidance(stance["profile"]),
        elicitation.steer_guidance(stance.get("steer")),
        "Use the compiled draft and researcher notes as working memory. "
        "Accepted values are recorded; notes are context; new cards are proposals. "
        "Never ask again for a value present in either. If a stated fact is not "
        "recorded yet, propose its patch instead of asking them to repeat it.",
    ]
    action = stance.get("decisionAction")
    if action:
        lines.append(
            f"CARD DECISION: {action}. Acknowledge it neutrally, without inventing "
            "the researcher's motive. The acceptance echo is not a new brief."
        )
        if action != "accepted" or (state or {}).get("proposed"):
            lines.append(
                "Return no new moves while this decision or other pending cards "
                "need review. Explain the remaining choice or invite a correction."
            )
            return "\n\n".join(lines)
        lines.append(
            "Advance to the next safe, reviewable choice using the recorded facts. "
            "Do not merely acknowledge and ask another setup question."
        )
    if stance["intent"] == "followup-question":
        lines.append(
            "QUESTION ABOUT WHAT YOU ALREADY SAID. Answer it directly, with "
            "the relevant reasoning and retrieved evidence. Return no new "
            "proposals except a caution needed to answer it."
        )
        return "\n\n".join(lines)
    if stance.get("batchIntake"):
        lines.append(
            "BATCH INTAKE. Use the accumulated study brief to propose a coherent "
            "group of missing decisions in this response, up to eight cards. "
            "Preserve accepted values. State assumptions as recommendations "
            "and keep them reviewable; never present guessed values as facts."
            " Prioritize the required open slots below. Preserve recorded choices; "
            "do not spend this turn rewriting task wording or adding optional "
            "refinements. Record known conditions even if their explanation appeared "
            "in an earlier reply: discussion is not a saved condition."
        )
    else:
        lines.append(
            "Offer up to three related, executable choices when enough is known. "
            "Keep a risk beside the choice it affects. Ask at most one focused "
            "question only when the answer changes the plan; no question is "
            "needed when you can already offer the next choice for review."
        )
    if stance["intent"] in {"needs-scaffolding", "continue"}:
        lines.append(
            "The researcher wants help moving forward. A short yes is not "
            "confusion or blanket approval. Use the preceding exchange to "
            "recommend the next step. For uncertainty, explain a defensible "
            "default or a concrete trade-off tied to this study; do not restart "
            "the questionnaire or switch to a generic example task."
        )
    if stance["mayProposeDesign"]:
        lines.append(
            "Enough to design. Recommend a defensible design or record the "
            "researcher's chosen design. Distinguish a recommendation from a "
            "requirement and explain the relevant trade-off. A causal research "
            "question alone does not require independent groups."
        )
        if stance.get("namedDesign"):
            lines.append(
                "The researcher named a design themselves. Record that choice "
                "and identify any assumption that needs review."
            )
        elif stance["intent"] == "design-request":
            lines.append(
                "They explicitly asked you to name a design. Offer a reviewable "
                "recommendation, with the assumptions and alternatives that matter."
            )
    else:
        lines.append(
            "Do not propose choose-template or merge-templates yet. Clarify "
            "the decision that changes the study, while retaining safe facts "
            "as executable cards."
        )
    if stance.get("explicitMoves"):
        lines.append(
            "This turn contains explicit facts that will be included as cards. "
            "Explain how they advance the plan and add only distinct useful choices."
        )
    lines.append(_slot_directive(state))
    if state and state.get("outstandingSlots"):
        lines.append(
            "Executable next choices: conditions use set-parameter with section "
            "conditions and op append; instruments use add-instrument with a real "
            "instrument key; a title uses set-field at study.title. An analysis "
            "uses prescribe-statistics with a declared RQ id once its observable "
            "is defined. Never let a cosmetic refinement block these choices."
        )
    return "\n\n".join(lines)


def _facet_settled_in_state(facet: str, state: dict | None) -> bool:
    """Whether the compiled design already answers a conversational facet."""
    if not state:
        return False
    filled = set(state.get("filled") or [])
    outstanding = {slot.get("key") for slot in state.get("outstandingSlots") or []}
    if facet == "population":
        return "participants" in filled
    if facet == "task":
        return bool(state.get("taskDescription")) or (
            "session.taskDescription" not in outstanding
        )
    if facet == "comparison":
        return "conditions" in filled or "conditions" not in outstanding
    if facet == "outcome":
        return "measures" in filled or bool(
            (state.get("draft") or {}).get("analysisPlan")
        )
    if facet == "constraints":
        return bool(state.get("sessionMinutes")) or (
            "session.durationMinutes" not in outstanding
        )
    return False


def _move_section(move: ProposedMove) -> str:
    """Return the protocol section a move would touch, when it has one."""
    if move.kind == "choose-template" or move.kind == "merge-templates":
        return "design"
    patch = move.patch or {}
    if patch.get("section"):
        return str(patch["section"])
    path = patch.get("path")
    if isinstance(path, list) and path:
        return str(path[0])
    return (move.target or "").removeprefix("protocol.").split(".")[0]


def _permitted_moves(
    moves: tuple[ProposedMove, ...], stance: dict, state: dict | None = None
) -> tuple[ProposedMove, ...]:
    """Apply the stance to a script's moves  -  the enforcement half.

    Keep related choices together, with the same permission and design-readiness
    boundaries as a single choice. Pending decisions pause automatic advancement.
    """
    if stance.get("decisionAction") and (
        stance["decisionAction"] != "accepted" or (state or {}).get("proposed")
    ):
        return ()
    candidates = []
    for move in moves:
        if not stance["mayProposeMoves"] and move.kind != "caution":
            log.info(
                "dropped %s move: %s",
                move.kind,
                "steer is set to checks, risks only"
                if not elicitation.proposals_permitted(stance.get("steer"))
                else "this turn is a question, not a brief",
            )
            continue
        if (
            move.kind in ("choose-template", "merge-templates")
            and not stance["mayProposeDesign"]
        ):
            log.info("held back %s: the study isn't understood yet", move.kind)
            continue
        if (
            stance.get("steer") == "assists"
            and move.kind != "caution"
            and _move_section(move) in set((state or {}).get("filled") or [])
        ):
            # Assists is the structural-gap stop: it may fill a section the
            # draft has not covered, but it should not keep pitching choices
            # the researcher has already settled.
            log.info("held back %s: assists only fills an empty section", move.kind)
            continue
        candidates.append(move)

    if not candidates:
        return ()
    if stance.get("batchIntake"):
        return tuple(candidates[:_BATCH_MOVE_CAP])

    return tuple(candidates[:_GROUP_MOVE_CAP])


def _move_key_text(proposal: str, patch: dict | None) -> str:
    """
    The semantic payload of a move for near-duplicate comparison: its proposal sentence
    plus the patch value it would write (a re-worded proposal carrying the same value is
    still the same move).
    """
    value = (patch or {}).get("value", "")
    if isinstance(value, list):
        value = " ".join(str(v) for v in value)
    return f"{proposal} {value}".strip()


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def _is_near_duplicate(a: str, b: str) -> bool:
    # Two moves that state different numbers are a revision, not a repeat: "30
    # minutes" and "45 minutes" share every word but the one that matters.
    na, nb = _numbers(a), _numbers(b)
    if na and nb and na != nb:
        return False
    ta, tb = set(matching._terms(a)), set(matching._terms(b))
    smaller = min(len(ta), len(tb))
    if smaller >= _DUP_MIN_TERMS and len(ta & tb) / smaller >= _DUP_TOKEN_OVERLAP:
        return True
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= (
        _DUP_SEQ_RATIO
    )


def _filter_repeated_moves(
    moves: tuple[ProposedMove, ...], state: dict | None
) -> tuple[ProposedMove, ...]:
    """
    Drop moves the conversation has already seen (an accepted move is in the
    draft, a rejected one was declined, an undecided one is still on the table  -
    re-pitching any of them is repetition).
    """
    if state is None:
        return moves
    content = state.get("keyTexts") or []
    advisory = state.get("advisoryTexts") or []
    by_target = state.get("keysByTarget")
    template_ids = set(state.get("templateIds") or [])
    merge_keys = set(state.get("mergeKeys") or [])
    kept = []
    for sm in moves:
        if sm.kind == "choose-template":
            tid = (sm.patch or {}).get("templateId")
            if tid and tid in template_ids:
                continue
        elif sm.kind == "merge-templates":
            ids = tuple(sorted((sm.patch or {}).get("templateIds") or []))
            if ids and "+".join(ids) in merge_keys:
                continue
        else:
            key = _move_key_text(sm.proposal, sm.patch)
            prior = (
                by_target.get(_patch_target(sm.target, sm.patch), [])
                if by_target is not None and sm.patch
                else content
                if sm.patch
                else [*content, *advisory]
            )
            if any(_is_near_duplicate(key, p) for p in prior):
                continue
        kept.append(sm)
    return tuple(kept)


def _patch_target(target: str, patch: dict | None) -> str:
    """A shared fact can legitimately fill different protocol fields."""
    patch = patch or {}
    path = patch.get("path")
    if isinstance(path, list):
        return ".".join(path)
    return str(patch.get("section") or target.removesuffix("[]"))


def _repeats_platform_reply(s: Session, study_id: str | None, text: str) -> bool:
    """Whether ``text`` would repeat a recent platform response.

    Move de-duplication alone cannot prevent a conversation from stalling: a
    model can keep asking the same question even after its card was rejected or
    left pending. Only use this as a last guard when the reply offers no new
    decision, so a concise acknowledgement shared by two otherwise useful
    replies is never suppressed.
    """
    if study_id is None or not text.strip():
        return False
    prior = s.scalars(
        select(ConversationTurn.text)
        .where(
            ConversationTurn.study_id == study_id,
            ConversationTurn.role == "platform",
            ConversationTurn.source != "unavailable",
        )
        .order_by(ConversationTurn.seq.desc())
        .limit(_RECENT_PLATFORM_TURNS)
    )
    return any(
        prior_text and _is_near_duplicate(text, prior_text) for prior_text in prior
    )


def _progress_turn(state: dict | None) -> Turn:
    """Replace a stalled reply with the next actionable protocol step."""
    if state is None:
        return Turn(
            text=(
                "To turn this into a protocol instead of repeating the same "
                "question, send a short brief with: who takes part, one coding "
                "task, what conditions you want to compare, and the outcome you "
                "will measure. I will turn the details you provide into reviewable "
                "cards."
            ),
            moves=(),
        )
    if state.get("compileValid"):
        return Turn(
            text=(
                "The protocol now has every required decision and validates. "
                "Review the compiled draft when you are ready rather than adding "
                "another conversation turn."
            ),
            moves=(),
        )
    proposed = state.get("proposed") or []
    if proposed:
        return Turn(
            text=(
                "The current proposal is still waiting for your decision. Accept "
                "it, reject it, or tell me what to change; I will not repeat the "
                "same question while that choice is open."
            ),
            moves=(),
        )
    outstanding = state.get("outstandingSlots") or []
    if outstanding:
        slot = outstanding[0]
        label = str(slot.get("label") or "the next protocol choice")
        return Turn(
            text=(
                f"The next open protocol choice is {label}. "
                + (slot.get("question") or "State the value you want to use.")
            ),
            moves=(),
        )
    return Turn(
        text=(
            "The recorded choices need a compiler correction before the protocol "
            "can be completed. Review the draft errors and tell me which detail to "
            "adjust."
        ),
        moves=(),
    )


def _load_design_state(s: Session, study_id: str | None) -> dict | None:
    """
    The structured design state the prose history can't carry: every prior move bucketed
    by decision status, the draft's filled/empty sections (computed deterministically
    via :func:`compiler.compile_moves`  -  no LLM), and the accepted template if any.
    """
    if study_id is None:
        return None
    rows = s.scalars(
        select(DesignMoveRow)
        .join(ConversationTurn, DesignMoveRow.turn_id == ConversationTurn.id)
        .where(DesignMoveRow.study_id == study_id)
        .order_by(ConversationTurn.seq, DesignMoveRow.seq)
    ).all()
    saved = s.get(ProtocolDraftRow, study_id)
    moves = [
        {
            "moveId": row.id,
            "kind": row.kind,
            "target": row.target,
            "proposal": row.proposal,
            "patch": row.patch,
            "grounding": row.grounding,
            "status": row.status,
        }
        for row in rows
    ]
    result = compiler.compile_moves(moves, base_yaml=saved.yaml if saved else None)
    sections = compiler.compile_sections(moves)
    has_instrument = any(
        m["status"] == "accepted"
        and (m["patch"] or {}).get("op") in ("add-instrument", "set-instrument")
        for m in moves
    )
    has_merged = any(
        m["kind"] == "merge-templates" and m["status"] == "accepted" for m in moves
    )
    # Ethics posture is useful when the researcher wants to record it, but it is
    # optional metadata rather than a gap the assistant should chase as part of the
    # core design path.
    conversation_sections = tuple(
        section for section in compiler.SECTIONS if section != "ethics"
    )
    draft_values = {
        "researchQuestions": result.draft.get("researchQuestions"),
        "design": (result.draft.get("participants") or {}).get("design")
        or result.draft.get("design")
        or result.template_id is not None
        or has_merged,
        "participants": result.draft.get("participants"),
        "conditions": result.draft.get("conditions"),
        "measures": result.draft.get("measures"),
        "instruments": result.draft.get("instruments") or has_instrument,
        # The protocol schema calls this analysisPlan; the conversation rail calls
        # it statisticalPlan. Use the compiled document as the authority for both.
        "statisticalPlan": result.draft.get("analysisPlan")
        or result.draft.get("statisticalPlan"),
    }
    filled = [
        sec
        for sec in conversation_sections
        if sections[sec] or bool(draft_values.get(sec))
    ]
    empty = [sec for sec in conversation_sections if sec not in filled]
    buckets: dict[str, list[dict]] = {"accepted": [], "rejected": [], "proposed": []}
    key_texts: list[str] = []
    keys_by_target: dict[str, list[str]] = {}
    advisory_texts: list[str] = []
    template_ids: list[str] = []
    merge_keys: list[str] = []
    for m in moves:
        patch = m["patch"] or {}
        if m["kind"] == "choose-template":
            section = "design"
            tid = patch.get("templateId")
            if tid:
                template_ids.append(tid)
        elif m["kind"] == "merge-templates":
            section = "design"
            ids = tuple(sorted(patch.get("templateIds") or []))
            if ids:
                merge_keys.append("+".join(ids))
        else:
            # Stripped here so a stale move from before that prompt fix, or any future
            # drift, can't feed the bogus section name "protocol" back into the state
            # block the model reads on its next turn.
            fallback_target = (m["target"] or "").removeprefix("protocol.")
            section = patch.get("section") or fallback_target.split(".")[0]
        # Kept apart so a section move addressing a caution's concern is never mistaken
        # for a repeat of it (see _filter_repeated_moves).
        key = _move_key_text(m["proposal"], m["patch"])
        if m["patch"]:
            keys_by_target.setdefault(
                _patch_target(m["target"], m["patch"]), []
            ).append(key)
        (key_texts if m["patch"] else advisory_texts).append(key)
        bucket = buckets.get(m["status"])
        if bucket is not None:
            bucket.append(
                {"kind": m["kind"], "section": section, "proposal": m["proposal"]}
            )
    outstanding = [
        {
            "key": slot.key,
            "label": slot.label,
            "question": slot.question,
            "valueType": slot.value_type,
            "choices": list(slot.choices),
        }
        for slot in compiler.unresolved_slots(result.draft)
    ]
    session = result.draft.get("session") or {}
    tasks = result.draft.get("tasks") or []
    return {
        "draft": {
            key: result.draft[key]
            for key in (
                "study",
                "researchQuestions",
                "participants",
                "conditions",
                "tasks",
                "session",
                "measures",
                "analysisPlan",
            )
            if key in result.draft
        },
        "instrumentNames": list((result.draft.get("instruments") or {}).keys()),
        "producerCapabilities": producer_capabilities(result.draft),
        "researcherNotes": list(dict.fromkeys(researcher_texts(s, study_id))),
        **{key: values[-_STATE_MOVE_CAP:] for key, values in buckets.items()},
        "filled": filled,
        "empty": empty,
        "outstandingSlots": outstanding,
        "compileValid": result.valid,
        "compileErrors": result.errors,
        "compileWarnings": result.warnings,
        "sessionMinutes": session.get("durationMinutes"),
        "taskDescription": bool(session.get("taskDescription")),
        "taskCount": len(tasks),
        "taskIds": [t.get("id") for t in tasks if t.get("id")],
        # Not a gap the protocol can name - tasks are optional - but the one thing most
        # worth prompting for, because a study collected without them can never be
        # re-analysed per task.
        "taskAdvice": compiler.task_recommendation(result.draft),
        "templateId": result.template_id,
        "templateIds": template_ids,
        "mergeKeys": merge_keys,
        "keyTexts": key_texts,
        "keysByTarget": keys_by_target,
        "advisoryTexts": advisory_texts,
    }


def respond(
    s: Session,
    text: str,
    *,
    seq: int,
    study_id: str | None = None,
    client=None,
    history: list[dict] | None = None,
    profile: str | None = None,
    steer: str | None = None,
    decision: dict | None = None,
) -> dict:
    """One platform turn responding to researcher ``text``."""
    state = _load_design_state(s, study_id)
    stance = turn_stance(
        s,
        text,
        study_id=study_id,
        profile=profile,
        steer=steer,
        decision=decision,
        state=state,
    )
    if stance["scope"] == "out-of-scope":
        return _assemble(
            s,
            text,
            _scope_turn(stance["scope"]),
            llm_recommendations=[],
            seq=seq,
            study_id=study_id,
            client=client,
            stance=stance,
            state=state,
            source="scope",
            suppress_recommendations=True,
        )
    explicit = _explicit_turn(stance, state)
    if client is None and explicit is not None and not stance.get("namedDesign"):
        return _assemble(
            s,
            text,
            explicit,
            llm_recommendations=[],
            seq=seq,
            study_id=study_id,
            client=client,
            stance=stance,
            state=state,
            source="scripted",
        )
    papers, templates, history = _retrieve(
        s, text, study_id, history, decision=decision
    )
    if client is None and stance["intent"] == "needs-scaffolding":
        return _assemble(
            s,
            text,
            _progress_turn(state),
            llm_recommendations=papers,
            seq=seq,
            study_id=study_id,
            client=client,
            stance=stance,
            state=state,
        )
    if client is None:
        if explicit is None:
            raise ModelUnavailable(NO_MODEL)
        # No model configured, but the researcher's stated facts are still
        # recordable as deterministic cards.
        return _assemble(
            s,
            text,
            _with_scripted_design(explicit, text),
            llm_recommendations=[],
            seq=seq,
            study_id=study_id,
            client=client,
            stance=stance,
            state=state,
            source="scripted",
        )

    directive = _directive(stance, state)
    turn = _propose_with_retry(
        client,
        text,
        history,
        papers,
        templates,
        directive,
        state,
        decision_followup=bool(stance.get("decisionAction")),
        next_question=stance.get("nextQuestion") or "",
    )
    if turn is None:
        if explicit is not None:
            # The model is down, but what the researcher stated explicitly is
            # still recordable: keep the deterministic cards rather than lose them.
            return _assemble(
                s,
                text,
                _with_scripted_design(explicit, text),
                llm_recommendations=[],
                seq=seq,
                study_id=study_id,
                client=client,
                stance=stance,
                state=state,
                source="scripted",
            )
        raise ModelUnavailable(MODEL_SILENT)
    if stance.get("explicitMoves"):
        explicit_moves = _filter_repeated_moves(tuple(stance["explicitMoves"]), state)
        if explicit_moves:
            turn = Turn(
                text=turn.text,
                moves=tuple(explicit_moves) + tuple(turn.moves),
                match_query=turn.match_query,
            )
    return _assemble(
        s,
        text,
        turn,
        llm_recommendations=papers,
        seq=seq,
        study_id=study_id,
        client=client,
        stance=stance,
        state=state,
    )


def _retrieve(
    s: Session,
    text: str,
    study_id: str | None,
    history: list[dict] | None,
    *,
    decision: dict | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    The deterministic retrieval every LLM turn is constrained to cite (papers,
    templates, history)  -  run *before* the model is asked anything, so the model can
    only select from what was actually retrieved.
    """
    # Explicit history takes precedence over the study's stored turns.
    if history is None:
        history = _load_history(s, study_id)
    if decision is not None and decision.get("action") != "accepted":
        # Accept/reject text is an audit event, not a new research idea. Searching
        # it was how tiny fragments such as "let" displaced the study's useful
        # literature with accidental papers in the recommender rail.
        return [], [], history
    researcher_context = [
        item["content"]
        for item in history
        if item.get("role") == "user" and item.get("content")
    ]
    # Recommendations belong to the study, not only to the latest answer. Keeping
    # just four recent turns meant that a long design conversation eventually forgot
    # "novice developers", "bug fixing", or "NASA-TLX" and fell back to generic
    # papers whose titles merely contained "code". Keep the opening idea as an anchor
    # and a bounded recent window so retrieval stays topical without growing forever.
    anchors = researcher_context[:2]
    recent = researcher_context[-8:]
    retrieval_parts = list(
        dict.fromkeys((*anchors, *recent, text if not decision else ""))
    )
    retrieval_query = " ".join(retrieval_parts).strip()[:6000]
    papers = matching.match_papers(
        s,
        retrieval_query,
        study_id=study_id,
        limit=8,
        use_llm=False,
        # Query expansion is itself an LLM request. Running it immediately
        # before the design response doubled conversation latency, while the
        # deterministic FTS ladder already gives the response a grounded menu.
        # The standalone corpus search can still opt into expansion.
        expand=False,
    )
    templates = recommend_templates(retrieval_query, support=corpus_support(s))
    return papers, templates, history


def respond_streaming(
    s: Session,
    text: str,
    *,
    seq: int,
    study_id: str | None = None,
    client=None,
    history: list[dict] | None = None,
    profile: str | None = None,
    steer: str | None = None,
    decision: dict | None = None,
):
    """:func:`respond`, yielding the reply's prose as the model writes it."""
    state = _load_design_state(s, study_id)
    stance = turn_stance(
        s,
        text,
        study_id=study_id,
        profile=profile,
        steer=steer,
        decision=decision,
        state=state,
    )
    if stance["scope"] == "out-of-scope":
        turn = _scope_turn(stance["scope"])
        if turn.text:
            yield turn.text
        return _assemble(
            s,
            text,
            turn,
            llm_recommendations=[],
            seq=seq,
            study_id=study_id,
            client=client,
            stance=stance,
            state=state,
            source="scope",
            suppress_recommendations=True,
        )
    explicit = _explicit_turn(stance, state)
    if client is None and explicit is not None and not stance.get("namedDesign"):
        if explicit.text:
            yield explicit.text
        return _assemble(
            s,
            text,
            explicit,
            llm_recommendations=[],
            seq=seq,
            study_id=study_id,
            client=client,
            stance=stance,
            state=state,
            source="scripted",
        )
    papers, templates, history = _retrieve(
        s, text, study_id, history, decision=decision
    )
    if client is None and stance["intent"] == "needs-scaffolding":
        turn = _progress_turn(state)
        if turn.text:
            yield turn.text
        return _assemble(
            s,
            text,
            turn,
            llm_recommendations=papers,
            seq=seq,
            study_id=study_id,
            client=client,
            stance=stance,
            state=state,
        )
    if client is None:
        if explicit is None:
            raise ModelUnavailable(NO_MODEL)
        # No model configured, but the researcher's stated facts are still
        # recordable as deterministic cards.
        if explicit.text:
            yield explicit.text
        return _assemble(
            s,
            text,
            _with_scripted_design(explicit, text),
            llm_recommendations=[],
            seq=seq,
            study_id=study_id,
            client=client,
            stance=stance,
            state=state,
            source="scripted",
        )
    from middleware import design_llm

    directive = _directive(stance, state)
    turn = yield from design_llm.propose_turn_streaming(
        client,
        text,
        history,
        papers,
        templates,
        directive,
        design_state=state,
        decision_followup=bool(stance.get("decisionAction")),
        next_question=stance.get("nextQuestion") or "",
    )
    if turn is None:
        log.info("streamed design turn produced nothing; retrying blocking")
        turn = _propose_with_retry(
            client,
            text,
            history,
            papers,
            templates,
            directive,
            state,
            decision_followup=bool(stance.get("decisionAction")),
            next_question=stance.get("nextQuestion") or "",
        )
    if turn is None:
        if explicit is not None:
            # The model is down, but what the researcher stated explicitly is
            # still recordable: keep the deterministic cards rather than lose them.
            if explicit.text:
                yield explicit.text
            return _assemble(
                s,
                text,
                _with_scripted_design(explicit, text),
                llm_recommendations=[],
                seq=seq,
                study_id=study_id,
                client=client,
                stance=stance,
                state=state,
                source="scripted",
            )
        raise ModelUnavailable(MODEL_SILENT)
    if stance.get("explicitMoves"):
        explicit_moves = _filter_repeated_moves(tuple(stance["explicitMoves"]), state)
        if explicit_moves:
            turn = Turn(
                text=turn.text,
                moves=tuple(explicit_moves) + tuple(turn.moves),
                match_query=turn.match_query,
            )
    return _assemble(
        s,
        text,
        turn,
        llm_recommendations=papers,
        seq=seq,
        study_id=study_id,
        client=client,
        stance=stance,
        state=state,
    )


def _dedupe_turn(turn: Turn, text: str, *, batch: bool = False) -> Turn:
    """Collapse duplicate cards after explicit and model moves are merged."""
    from middleware import design_llm

    cap = (
        design_llm.MAX_BATCH_CARDS
        if batch or elicitation.is_complete_brief(text)
        else design_llm.MAX_CARDS
    )
    moves = design_llm.dedupe_moves(turn.moves, cap)
    if moves == tuple(turn.moves):
        return turn
    return Turn(turn.text, moves, turn.match_query)


def _assemble(
    s: Session,
    text: str,
    turn: Turn,
    *,
    llm_recommendations: list[dict] | None,
    seq: int,
    study_id: str | None,
    client,
    stance: dict,
    state: dict | None = None,
    source: str = "llm",
    suppress_recommendations: bool = False,
) -> dict:
    """
    Turn the model's reply into the platform turn's result dict: grounding resolved
    against retrieved rows, recommendations, and the design recommender's
    prescription/figures.
    """
    turn = _dedupe_turn(turn, text, batch=bool(stance.get("batchIntake")))
    kept = _filter_repeated_moves(turn.moves, state)
    if kept != turn.moves:
        turn = Turn(turn.text, kept, turn.match_query)
    permitted = _permitted_moves(kept, stance, state)
    if not permitted and (
        _repeats_platform_reply(s, study_id, turn.text)
        or (
            stance.get("mayProposeMoves")
            and turn.text.strip().lower() in {"noted.", "decision recorded."}
        )
    ):
        # The provider has supplied no new decision and has repeated a recent
        # question. Switch to durable state rather than letting prose history
        # grow until the researcher abandons the conversation.
        turn = _progress_turn(state)
        permitted = ()
    retrieved: set[str] = set()

    moves = []
    for i, sm in enumerate(permitted):
        grounding = _resolve_grounding(s, sm.refs)
        if sm.kind == "choose-template" and not grounding and sm.patch:
            tid = sm.patch.get("templateId")
            grounding = _resolve_grounding(s, _template_source_refs(tid))
        elif sm.kind == "merge-templates" and not grounding and sm.patch:
            refs: list[str] = []
            for tid in sm.patch.get("templateIds") or []:
                refs.extend(_template_source_refs(tid))
            grounding = _resolve_grounding(s, tuple(dict.fromkeys(refs)))
        retrieved.update(g["ref"] for g in grounding)
        move: dict[str, Any] = {
            "moveId": f"t{seq}-m{i + 1}",
            "kind": sm.kind,
            "target": sm.target,
            "proposal": sm.proposal,
            "patch": sm.patch,
            "grounding": grounding,
            "status": "proposed",
        }
        if sm.kind == "merge-templates" and sm.patch:
            move["mergeData"] = {
                "templateIds": list(sm.patch.get("templateIds") or []),
                "reason": str(sm.patch.get("reason") or ""),
            }
        moves.append(move)

    # Reuse the retrieval already made for the candidate menu  -  never a second
    # match_papers call for the same turn.
    recommendations = [] if suppress_recommendations else (llm_recommendations or [])
    retrieved.update(r["ref"] for r in recommendations)

    template_recommendations = (
        []
        if suppress_recommendations
        else recommend_templates(text, support=corpus_support(s))
    )
    design_shape = None
    for tr in template_recommendations:
        ds = tr.get("designShape")
        if ds:
            design_shape = ds
            break
    prescription = (
        recommend_prescription(design_shape)
        if design_shape and not suppress_recommendations
        else None
    )
    result_shape = None
    if design_shape == "two-group":
        result_shape = "two-group-comparison"
    elif design_shape == "paired":
        result_shape = "paired-comparison"
    elif design_shape == "proportion":
        result_shape = "proportion"
    elif design_shape == "correlation":
        result_shape = "correlation"
    figure_suggestions = (
        suggest_figures(result_shape)
        if result_shape and not suppress_recommendations
        else []
    )

    return {
        "text": _guard_completion_claim(turn.text, state),
        "moves": moves,
        "recommendations": recommendations,
        "templateRecommendations": template_recommendations,
        "prescription": prescription,
        "figureSuggestions": figure_suggestions,
        "understanding": stance["understanding"],
        "turnIntent": stance["intent"],
        "retrievedRefs": sorted(retrieved),
        "source": source,
    }


def _guard_completion_claim(text: str, state: dict | None) -> str:
    """Keep model prose consistent with the authoritative compile state."""
    if not state or not text:
        return text
    claim = re.search(
        r"\b(?:protocol|draft|study)\b.{0,36}"
        r"\b(?:complete|ready to (?:compile|apply))\b"
        r"|\bconditions?\s+(?:are|is)\s+(?:now\s+)?set\b"
        r"|\bstatistical plan\s+(?:is|has been)\s+(?:already\s+)?set\b",
        text,
        flags=re.IGNORECASE,
    )
    if not claim:
        return text
    outstanding = state.get("outstandingSlots") or []
    if outstanding:
        labels = ", ".join(str(slot.get("label")) for slot in outstanding[:3])
        suffix = " and more" if len(outstanding) > 3 else ""
        return f"The draft is not complete yet. Still open: {labels}{suffix}."
    if state.get("compileValid") is False:
        errors = state.get("compileErrors") or ["the compiled draft needs correction"]
        return f"The draft still needs a compiler correction: {errors[0]}."
    return text
