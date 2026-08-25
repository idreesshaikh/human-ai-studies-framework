"""The design assistant: one researcher turn in, one platform turn out."""

from __future__ import annotations

import difflib
import logging
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import compiler, elicitation, matching
from middleware.db import ConversationTurn, DesignMoveRow
from middleware.template_registry import list_templates

log = logging.getLogger(__name__)

# The accepted/rejected move ledger and compiled draft carry the durable state. Keep
# only a short conversational window so old prose cannot make every reply slower.
_LLM_HISTORY_TURNS = 12

_STATE_MOVE_CAP = 30

# Near-duplicate thresholds (tunable): two moves are the same move when their content
# terms overlap this much (denominator: the smaller term set, so a short prior move
# can't swallow a longer distinct one) or their full texts are this similar.
_DUP_TOKEN_OVERLAP = 0.8
_DUP_SEQ_RATIO = 0.85
_DUP_MIN_TERMS = 3


_DESIGN_INTENT_WORDS = ("design", "statistic", "test", "how many", "template")

_NAMED_DESIGN_SCORE = 2


TURN_ATTEMPTS = 2


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


NO_MODEL = (
    "The design conversation needs a language model, and none is configured. "
    "Set MISTRAL_API_KEY on the middleware and reload. "
    "Everything else on the platform works without one."
)
MODEL_SILENT = (
    "I couldn't reach the model just now, so this turn went unanswered. "
    "Nothing was lost. Your message is still here, and saying it again is "
    "usually enough."
)


class ModelUnavailable(RuntimeError):
    """The design conversation could not reach a language model."""


def recommend_templates(
    text: str, *, support: dict[str, int] | None = None
) -> list[dict[str, Any]]:
    """Recommend design archetype templates matching the researcher's input."""
    q = text.lower()
    templates = list_templates()
    scored: list[tuple[int, dict[str, Any]]] = []

    keywords = {
        "two-group-rct": ["between-subjects", "two group", "independent group",
                          "control group", "random assignment", "rct",
                          "randomized controlled", "randomised controlled",
                          "randomized trial", "randomised trial",
                          "random control", "randomly assign"],
        "within-subjects-crossover": ["within-subjects", "crossover", "paired",
                                      "both conditions", "repeated"],
        "paired-pre-post": ["pre-post", "before after", "pre and post",
                            "intervention", "training effect"],
        "multi-arm-rct": ["multi-arm", "multiple groups", "three group",
                          "several conditions", "multiple treatments"],
        "factorial-2x2": ["factorial", "two factors", "interaction",
                          "2x2", "main effect"],
        "single-group-repeated-measures": ["longitudinal", "over time",
                                            "time point", "repeated measure",
                                            "trend", "trajectory"],
        "two-proportion-mcnemar": ["binary", "pass fail", "proportion",
                                   "success rate", "completion rate"],
        "single-arm-benchmark": ["benchmark", "single arm", "descriptive",
                                 "exploratory", "evaluation", "pilot study"],
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
    """Look up the prescription for a design shape (FR-TPL-6)."""
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
    """Get ranked figure suggestions for a result shape (FR-ANA-7)."""
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


def _template_source_refs(template_id: str | None) -> tuple[str, ...]:
    """
    The paper refs a template cites as its design's sources (FR-TPL)  -  used to ground
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
    Prior turns as ``{"role", "content"}`` dicts, oldest first, capped to
    ``_LLM_HISTORY_TURNS`` (a token-budget cap, not a correctness requirement) - the
    shape an LLM chat-completions call expects.
    """
    if study_id is None:
        return []
    rows = s.execute(
        select(ConversationTurn)
        .where(ConversationTurn.study_id == study_id)
        .order_by(ConversationTurn.seq.desc())
        .limit(_LLM_HISTORY_TURNS)
    ).scalars().all()
    turn_ids = [
        row.id
        for row in rows
        # `source == "unavailable"` is excluded from the id list gathering
        # moves below and, more importantly, from the loop that builds
        # `history` itself (the `continue` below)  -  a holding turn carries no
        # moves regardless, but it must never enter the transcript replayed
        # back to the model: it is not part of the study's design record,
        # and feeding "I couldn't reach the model" back in as a fabricated
        # assistant turn is exactly the contamination this exclusion exists
        # to prevent.
        if row.role == "platform" and row.source != "unavailable"
    ]
    moves_by_turn: dict[str, list[DesignMoveRow]] = {}
    if turn_ids:
        for mv in s.scalars(
            select(DesignMoveRow)
            .where(DesignMoveRow.turn_id.in_(turn_ids))
            # Bucketed per turn, so only in-turn order matters  -  seq is the proposal
            # order (id would put e.g. m10 before m2).
            .order_by(DesignMoveRow.seq)
        ):
            moves_by_turn.setdefault(mv.turn_id, []).append(mv)

    history: list[dict] = []
    for row in reversed(rows):
        # A holding turn ("no model configured", "the provider is down") is
        # persisted now so the UI can show it again after a reload
        # (app.py's ModelUnavailable branches), but it is not a real answer
        # and must never be replayed to the model as if one of its own past
        # turns said it  -  skip it here the same way an empty turn is skipped
        # below.
        if row.role == "platform" and row.source == "unavailable":
            continue
        moves = moves_by_turn.get(row.id, [])
        content = row.text or ""
        # Card decisions are already represented structurally by the move status and
        # the current request's ``decision`` payload. Replaying the synthetic
        # “I accepted …” researcher echo wastes context and encourages the model to
        # echo it back as if it were a new research idea.
        if row.role == "researcher" and content.lower().startswith(
            ("i accepted:", "i rejected the proposed", "i noted the caution")
        ):
            continue
        if moves:
            lines = [
                f"- [{mv.kind}] {mv.proposal}"
                + (
                    f" (grounded in {', '.join(g['ref'] for g in mv.grounding)})"
                    if mv.grounding
                    else " (unsourced)"
                )
                + f" (researcher {mv.status} this)"
                for mv in moves
            ]
            content = (content + "\n\nMoves I proposed in that turn:\n" +
                       "\n".join(lines)).strip()
        if not content:
            continue
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
    return any(
        t.get("templateId") and t["templateId"].lower() in q for t in templates
    )


def turn_stance(
    s: Session,
    text: str,
    *,
    study_id: str | None = None,
    profile: str | None = None,
    steer: str | None = None,
    decision: dict | None = None,
) -> dict:
    """What this turn is, how much is understood, and what may be proposed."""
    prior = researcher_texts(s, study_id)
    understanding = elicitation.assess_understanding([*prior, text])
    intent = elicitation.classify_turn(text)
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
        "intent": intent,
        "steer": steer if steer in elicitation.STEER_LEVELS else None,
        "profile": declared or elicitation.steer_profile(steer),
        "understanding": elicitation.understanding_summary(understanding),
        "nextQuestion": elicitation.next_question(understanding),
        "namedDesign": named_design,
        "decisionAction": decision_action,
        # An explicit ask lowers the gate but never removes it; a follow-up question
        # never opens it, because "why did you pick that?" is not "pick one".
        "mayProposeDesign": named_design
        or elicitation.ready_for_design(
            understanding, requested=intent == "design-request"
        ),
        "mayProposeMoves": not decision_action
        and intent != "followup-question"
        and elicitation.proposals_permitted(steer),
    }


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
    """The stance as this turn's instruction to the model."""
    understanding = stance["understanding"]
    lines = [
        elicitation.profile_guidance(stance["profile"]),
        elicitation.steer_guidance(stance.get("steer")),
    ]

    if stance.get("decisionAction"):
        action = stance["decisionAction"]
        lines.append(
            "THIS IS AN AUTOMATIC FOLLOW-UP TO A CARD DECISION. The researcher "
            f"just {action} the move identified in the design state. Do not "
            "propose any move in this response. Return an empty `moves` array. "
            "For accepted or noted, acknowledge the choice briefly and ask at "
            "most one useful next question only if the researcher has not "
            "redirected or deferred. Do not force the first outstanding decision "
            "or a prescribed order. For rejected, explain what the proposal was "
            "trying to solve in one short sentence, then ask one focused question "
            "only when it will let you offer a better fit. Do "
            "not re-propose or restate the rejected move. The response must be "
            "useful even if the researcher only answers that one question."
        )
        lines.append(_slot_directive(state))
        return "\n\n".join(lines)

    if stance["intent"] == "needs-scaffolding":
        lines.append(
            "THE RESEARCHER IS STUCK. Explain the first missing facet in plain "
            "language with two or three concrete examples tied to this study. "
            "Do not repeat the generic question verbatim. Offer one clear next "
            "choice and, when a safe concrete measure or task can help, propose "
            "one actionable move card for them to accept or reject. Do not invent "
            "a value they have not supplied."
        )
    elif stance["intent"] == "followup-question":
        lines.append(
            "THIS TURN IS A QUESTION ABOUT WHAT YOU ALREADY SAID. Answer it "
            "directly in `text`, naming the specific move you proposed and the "
            "reasoning and papers behind it (they are in the history above). "
            "Return an EMPTY `moves` array unless a `caution` is genuinely "
            "part of the answer. Do not offer new proposals in place of an "
            "answer, and do not change the subject."
        )
    if understanding["missing"]:
        lines.append(
            "STILL UNKNOWN about this study: "
            + ", ".join(understanding["missingLabels"])
            + ". Offer one of these as the next focus only if it is useful. "
            "Ask one question in your own words, informed by what they have "
            "already told you. A good next question is: "
            + (stance["nextQuestion"] or "(none)")
        )
        if stance["intent"] == "followup-question":
            lines.append(
                "Answer the question before doing anything else. Do not attach "
                "a new design move to this explanation."
            )
        elif stance["intent"] == "needs-scaffolding":
            lines.append(
                "Use an explanation plus concrete options, not another open-ended "
                "request for the same missing facet."
            )
        else:
            lines.append(
                "ONE STEP ONLY. Help the researcher with one useful facet, not "
                "necessarily the first missing facet. Reflect their idea briefly, "
                "then ask one question only when needed. If their latest message "
                "contains one concrete task, measure, "
                "research question, or protocol value, record only that safe "
                "fact as one move. Do not propose a design shape yet."
            )
    else:
        lines.append(
            "You now know who takes part, what they do, what is compared, "
            "what is measured, and what is possible. That is enough to design."
        )
    if not stance["mayProposeDesign"]:
        lines.append(
            "DO NOT propose a choose-template or merge-templates move this "
            "turn: too little of the study is understood for a design shape "
            "to be a considered choice rather than a guess, and one would be "
            "discarded before the researcher ever saw it. Keep drawing the "
            "idea out instead. "
            f"({len(understanding['known'])} of {understanding['facetsNeeded']} "
            "needed facets known.)"
        )
    elif stance.get("namedDesign"):
        lines.append(
            "The researcher named a design themselves. Record it rather than "
            "second-guessing them: propose the matching template, and note "
            "any assumption it carries that they may want to correct."
        )
    elif stance["intent"] == "design-request":
        lines.append(
            "The researcher has explicitly asked you to name a design. Do so "
            "State plainly which of your assumptions it rests on, so a "
            "wrong one is easy for them to correct."
        )
    if stance["mayProposeDesign"]:
        lines.append(
            "If no single candidate template fits the study but two or three "
            "together would, propose a `merge-templates` move instead of "
            "forcing the closest single shape."
        )
        lines.append(_slot_directive(state))
    return "\n\n".join(lines)


def _scaffolding_turn(
    stance: dict, papers: list[dict], state: dict | None = None
) -> Turn:
    """Give a stuck researcher a useful explanation and one visible next move.

    This is intentionally deterministic. A low-information reply is the one place
    where asking the model to improvise is least reliable: it can mirror the same
    unanswered question forever. The card remains a proposal, so the researcher is
    still the person who decides what enters the protocol.
    """
    understanding = stance.get("understanding") or {}
    if not understanding.get("known"):
        return Turn(
            text=(
                "Start with the question you want to answer, in plain language. "
                "For example: does AI assistance change how junior developers debug "
                "code? What do you want to find out?"
            ),
            moves=(),
        )
    missing = [
        facet
        for facet in (understanding.get("missing") or [])
        if not _facet_settled_in_state(facet, state)
    ]
    if not missing:
        if state and not state.get("outstandingSlots"):
            if state.get("compileValid") is False:
                return Turn(
                    text=(
                        "The choices are recorded, but the draft still needs a "
                        "compiler correction before it can run."
                    ),
                    moves=(),
                )
            return Turn(
                text=(
                    "The protocol is complete and valid. I will not invent another "
                    "question. Review the draft when you are ready."
                ),
                moves=(),
            )
        if state and state.get("outstandingSlots"):
            next_slot = state["outstandingSlots"][0]["label"]
            return Turn(
                text=(
                    "I already have the decisions you confirmed, so I will not ask "
                    f"you to repeat them. The next open protocol choice is {next_slot}."
                ),
                moves=(),
            )
        return Turn(
            text=(
                "The study is understood enough to make a design choice. "
                "What would you like to settle next?"
            ),
            moves=(),
        )
    facet = missing[0]
    copy: dict[str, tuple[str, ProposedMove | None]] = {
        "population": (
            "A practical starting population is junior engineers who already use AI "
            "coding tools. This records who the study is about without guessing a "
            "sample size.",
            ProposedMove(
                "set-parameter",
                "participants[]",
                "Recruit junior engineers who regularly use AI coding tools.",
                {
                    "section": "participants",
                    "op": "append",
                    "value": "junior engineers who regularly use AI coding tools",
                },
                (),
            ),
        ),
        "task": (
            "A concrete task keeps the study reproducible: have participants complete "
            "a small bug-fixing task on a shared project.",
            ProposedMove(
                "declare-task",
                "tasks[]",
                "Have participants complete a small bug-fixing task on a shared "
                "project.",
                {
                    "title": "Complete a small bug-fixing task on a shared project",
                    "description": (
                        "Participants diagnose and fix the same kind of project issue."
                    ),
                },
                (),
            ),
        ),
        "comparison": (
            "That is okay. A comparison is what you put side by side: for example, "
            "AI-assisted work versus unassisted work, or the same people before and "
            "after using AI. Which comparison matches your aim?",
            None,
        ),
        "outcome": (
            "Measure correctness alongside task time because it "
            "shows whether the completed work is actually right, using passed tests "
            "and substantive defects.",
            ProposedMove(
                "add-measure",
                "measures[]",
                "Measure solution correctness by counting passed test cases and "
                "substantive defects.",
                {
                    "section": "measures",
                    "op": "append",
                    "value": (
                        "solution correctness: passed test cases and "
                        "substantive defects"
                    ),
                },
                tuple(p["ref"] for p in papers[:1] if p.get("ref")),
            ),
        ),
        "constraints": (
            "That is okay. Practical constraints are the limits that make the study "
            "real, such as session length, setting, or data you can access. Which "
            "limit should we plan around first?",
            None,
        ),
    }
    text, move = copy.get(
        facet,
        (
            "That is okay. We can leave that choice open and work on whichever "
            "thread is useful next: who takes part, what they do, what is compared, "
            "or what we measure.",
            None,
        ),
    )
    if move and not _filter_repeated_moves((move,), state):
        # A rejected or still-pending suggestion must not be shown again as if
        # the researcher never answered. Keep the next turn useful by naming
        # the actual choice instead of looping the same example.
        if facet == "task":
            text = (
                "The example task is only a starting point, and I will not repeat it. "
                "What is the actual work: writing code, debugging a defect, or "
                "AI-generated code?"
            )
        elif facet == "population":
            text = (
                "The participant example is only a starting point, and I will not "
                "repeat it. "
                "Who can you realistically recruit, and roughly how many people?"
            )
        elif facet == "outcome":
            text = (
                "The correctness measure is only a starting point, and I will not "
                "repeat it. Which result matters most here: time, correctness, "
                "review quality, or understanding?"
            )
        move = None
    return Turn(text=text, moves=(move,) if move else ())


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
        return "measures" in filled
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

    The model is instructed to make one proposal at a time, but that rule must
    also hold when a provider returns a verbose turn or an older prompt is in
    use. Keep one permitted move, with a grounded caution taking priority over
    an action when both are present. A risk is the decision the researcher
    needs to see before accepting a new protocol choice.
    """
    if stance.get("decisionAction"):
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
        if move.kind in ("choose-template", "merge-templates") and not stance[
            "mayProposeDesign"
        ]:
            log.info(
                "held back %s: the study isn't understood yet", move.kind
            )
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
    chosen = next(
        (move for move in candidates if move.kind == "caution"),
        candidates[0],
    )
    chosen = (chosen,) if chosen is not None else ()
    if len(candidates) > len(chosen):
        log.info(
            "held back %d move(s): the conversation offers one decision at a time",
            len(candidates) - len(chosen),
        )
    return chosen


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


def _is_near_duplicate(a: str, b: str) -> bool:
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
    Drop moves the conversation has already seen (FR-CONV: an accepted move is in the
    draft, a rejected one was declined, an undecided one is still on the table  -
    re-pitching any of them is repetition).
    """
    if state is None:
        return moves
    content = state.get("keyTexts") or []
    advisory = state.get("advisoryTexts") or []
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
            prior = content if sm.patch else [*content, *advisory]
            if any(_is_near_duplicate(key, p) for p in prior):
                continue
        kept.append(sm)
    return tuple(kept)


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
    if not rows:
        return None
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
    result = compiler.compile_moves(moves)
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
        "design": result.draft.get("design")
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
        (key_texts if m["patch"] else advisory_texts).append(key)
        bucket = buckets.get(m["status"])
        if bucket is not None and len(bucket) < _STATE_MOVE_CAP:
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
        **buckets,
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
    stance = turn_stance(
        s,
        text,
        study_id=study_id,
        profile=profile,
        steer=steer,
        decision=decision,
    )
    state = _load_design_state(s, study_id)
    papers, templates, history = _retrieve(
        s, text, study_id, history, decision=decision
    )
    if stance["intent"] == "needs-scaffolding":
        return _assemble(
            s,
            text,
            _scaffolding_turn(stance, papers, state),
            llm_recommendations=papers,
            seq=seq,
            study_id=study_id,
            client=client,
            stance=stance,
            state=state,
        )
    if client is None:
        raise ModelUnavailable(NO_MODEL)
    from middleware import design_llm

    directive = _directive(stance, state)
    turn = None
    for attempt in range(TURN_ATTEMPTS):
        turn = design_llm.propose_turn(
            client, text, history, papers, templates, directive,
            design_state=state,
        )
        if turn is not None:
            break
        log.info(
            "design turn attempt %d/%d produced nothing", attempt + 1, TURN_ATTEMPTS
        )
    if turn is None:
        raise ModelUnavailable(MODEL_SILENT)
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
    # An explicit history (the stateless demo passes the visitor's own prior turns)
    # wins; otherwise load it from the study's stored turns.
    if history is None:
        history = _load_history(s, study_id)
    if decision is not None:
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
    retrieval_parts = list(dict.fromkeys((*anchors, *recent, text)))
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
    templates = recommend_templates(text, support=corpus_support(s))
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
    stance = turn_stance(
        s,
        text,
        study_id=study_id,
        profile=profile,
        steer=steer,
        decision=decision,
    )
    state = _load_design_state(s, study_id)
    papers, templates, history = _retrieve(
        s, text, study_id, history, decision=decision
    )
    if stance["intent"] == "needs-scaffolding":
        turn = _scaffolding_turn(stance, papers, state)
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
        raise ModelUnavailable(NO_MODEL)
    from middleware import design_llm

    directive = _directive(stance, state)
    turn = yield from design_llm.propose_turn_streaming(
        client, text, history, papers, templates, directive,
        design_state=state,
    )
    if turn is None:
        log.info("streamed design turn produced nothing; retrying blocking")
        turn = design_llm.propose_turn(
            client, text, history, papers, templates, directive,
            design_state=state,
        )
    if turn is None:
        raise ModelUnavailable(MODEL_SILENT)
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
) -> dict:
    """
    Turn the model's reply into the platform turn's result dict: grounding resolved
    against retrieved rows, recommendations, and the design recommender's
    prescription/figures.
    """
    had_model_moves = bool(turn.moves)
    kept = _filter_repeated_moves(turn.moves, state)
    if kept != turn.moves:
        turn = Turn(turn.text, kept, turn.match_query)
    permitted = _permitted_moves(kept, stance, state)
    if (
        not permitted
        and not had_model_moves
        and stance.get("mayProposeMoves")
        and stance.get("intent") != "followup-question"
    ):
        # The model's prose is still valuable, but a prose-only turn leaves the
        # researcher with nothing to decide. Use the same constrained
        # scaffolding card as the explicit "what?" path, then run it through
        # the exact same repetition and steer gates as model-authored moves.
        guided = _scaffolding_turn(stance, llm_recommendations or [], state)
        guided_kept = _filter_repeated_moves(guided.moves, state)
        guided_permitted = _permitted_moves(guided_kept, stance, state)
        if guided_permitted:
            turn = Turn(turn.text, guided_kept, turn.match_query)
            kept = guided_kept
            permitted = guided_permitted
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
    recommendations = llm_recommendations or []
    retrieved.update(r["ref"] for r in recommendations)

    template_recommendations = recommend_templates(text, support=corpus_support(s))
    design_shape = None
    for tr in template_recommendations:
        ds = tr.get("designShape")
        if ds:
            design_shape = ds
            break
    prescription = recommend_prescription(design_shape) if design_shape else None
    result_shape = None
    if design_shape == "two-group":
        result_shape = "two-group-comparison"
    elif design_shape == "paired":
        result_shape = "paired-comparison"
    elif design_shape == "proportion":
        result_shape = "proportion"
    elif design_shape == "correlation":
        result_shape = "correlation"
    figure_suggestions = suggest_figures(result_shape) if result_shape else []

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
        "source": "llm",
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
