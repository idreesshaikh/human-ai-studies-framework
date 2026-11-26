"""The design assistant: one researcher turn in, one platform turn out.

Every turn that reaches a model goes through :mod:`middleware.study_plan`: the
model talks with the researcher and may propose plan cards. The assistant's
part is the frame around that call: the supported-scope check, literature
retrieval for the turn, the state of the plan, and grounding each card's
citations in the corpus. Without a model, or when the provider cannot be
reached, a turn says so and proposes nothing; templates and the checklist still
work.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import compiler, elicitation, matching, study_plan
from middleware.db import ConversationTurn, DesignMoveRow
from middleware.route_helpers import draft_base_yaml

log = logging.getLogger(__name__)

# Retrieval reads the study's opening messages as an anchor and a recent window,
# so a long conversation stays on topic without the query growing forever.
_RETRIEVAL_ANCHORS = 2
_RETRIEVAL_RECENT = 6
_RETRIEVAL_CHARS = 6000
_PAPERS_PER_TURN = 8


def holding_turn(reason: str, stance: dict | None = None) -> dict:
    """A turn that proposes nothing: a notice, a status or a redirect."""
    return {
        "text": reason,
        "moves": [],
        "questions": [],
        "withdrawn": [],
        "recommendations": [],
        "understanding": (stance or {}).get("understanding"),
        "turnIntent": "",
        "retrievedRefs": [],
        "source": "unavailable",
    }


SCOPE_REDIRECT = (
    "StudyLoop is for task-based human–AI software-development studies. It can "
    "configure TERN sessions in VS Code, capture what developers do and what "
    "the AI does, and prepare the resulting dataset. This idea is outside that "
    "lane, so I will not keep asking protocol questions. Use a coding task with "
    "an AI-assisted versus unassisted comparison if that is the study you want "
    "to run."
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
MODEL_UNUSABLE = (
    "The model’s answer could not be read, so nothing was proposed. Your "
    "message is saved. Send it again, or put it another way."
)
MODEL_REJECTED = (
    "The model provider rejected the server's API key, so no reply was generated. "
    "Your message is saved and nothing was applied. Set a valid LLM_API_KEY and "
    "restart the server."
)
MODEL_BILLING = (
    "The model provider refused the request because the account has no API "
    "budget or subscription, so no reply was generated. Your message is saved "
    "and nothing was applied. Check the provider's billing settings, or connect "
    "another model."
)
MODEL_LIMITED = (
    "The model provider is rate-limiting this server right now. Your message is "
    "saved and nothing was applied. Wait a few seconds and send it again."
)
DRAFT_READY = (
    "The draft now has every required decision and validates. Open Review draft "
    "to check it and apply it to the protocol, or tell me what to change."
)


class ModelUnavailable(RuntimeError):
    """The design conversation could not reach a language model."""


def recommend_prescription(design_shape: str) -> dict[str, Any] | None:
    """Look up the prescription for a design shape."""
    try:
        from analysis.prescribe import prescribe

        p = prescribe(design_shape)
        if p is None:
            return None
        return prescription_dict(p)
    except ImportError:
        return None


def prescription_dict(p: Any) -> dict[str, Any]:
    """A prescription as the API returns it."""
    return {
        "designShape": p.design_shape,
        "test": p.test,
        "effectSize": p.effect_size,
        "correction": p.correction,
        "sampleSizeGuidance": p.sample_size_guidance,
        "rationale": p.rationale,
    }


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


def _turns(s: Session, study_id: str | None) -> list[dict]:
    """The stored conversation, oldest first, as :func:`study_plan.converse`
    reads it."""
    if study_id is None:
        return []
    return [
        {
            "role": row.role,
            "text": "" if row.redacted else row.text,
            "source": row.source,
            "questions": row.questions or [],
        }
        for row in s.scalars(
            select(ConversationTurn)
            .where(ConversationTurn.study_id == study_id)
            .order_by(ConversationTurn.seq)
        )
    ]


def _moves(s: Session, study_id: str) -> list[dict]:
    return [
        {
            "moveId": row.id,
            "kind": row.kind,
            "target": row.target,
            "proposal": row.proposal,
            "patch": row.patch,
            "status": row.status,
        }
        for row in s.scalars(
            select(DesignMoveRow)
            .join(ConversationTurn, DesignMoveRow.turn_id == ConversationTurn.id)
            .where(DesignMoveRow.study_id == study_id)
            .order_by(ConversationTurn.seq, DesignMoveRow.seq)
        )
    ]


def turn_stance(
    s: Session,
    text: str,
    *,
    study_id: str | None = None,
    steer: str | None = None,
) -> dict:
    """What this turn is: in scope or not, which style, how much is understood."""
    prior = researcher_texts(s, study_id)
    return {
        "scope": elicitation.classify_scope([*prior, text]),
        "steer": steer if steer in elicitation.STEER_LEVELS else None,
        "understanding": elicitation.understanding_summary(
            elicitation.assess_understanding([*prior, text])
        ),
    }


def _decision_turn(s: Session, study_id: str | None, stance: dict) -> dict:
    """A card decision needs a status, not prose, and no model call."""
    if study_id is None:
        return {**holding_turn("Recorded.", stance), "source": "scripted"}
    moves = _moves(s, study_id)
    pending = sum(m["status"] == "proposed" for m in moves)
    built = compiler.compile_moves(moves, base_yaml=draft_base_yaml(s, study_id))
    if pending:
        text = (
            f"Recorded. {pending} "
            + ("proposal is" if pending == 1 else "proposals are")
            + " still waiting for your decision."
        )
    elif built.valid:
        text = DRAFT_READY
    elif built.unresolved:
        text = (
            "Recorded. Still open: "
            + ", ".join(built.unresolved[:4])
            + ". Tell me how you would like to settle them."
        )
    else:
        text = "Recorded."
    return {**holding_turn(text, stance), "source": "scripted"}


def _retrieve(s: Session, text: str, study_id: str | None) -> list[dict]:
    """The literature this turn may cite, retrieved before the model is asked
    anything, so it can only cite what was actually retrieved."""
    said = researcher_texts(s, study_id)
    parts = dict.fromkeys(
        (*said[:_RETRIEVAL_ANCHORS], *said[-_RETRIEVAL_RECENT:], text)
    )
    query = " ".join(parts).strip()[:_RETRIEVAL_CHARS]
    # A query the local corpus answers weakly also asks Semantic Scholar,
    # within a short time budget; what it finds joins the corpus.
    return matching.match_papers(
        s, query, study_id=study_id, limit=_PAPERS_PER_TURN, live=True
    )


def _open(
    s: Session,
    text: str,
    *,
    study_id: str | None,
    client,
    steer: str | None,
    decision: dict | None,
) -> tuple[dict, dict | None, study_plan.PlanState | None, list[dict]]:
    """(stance, a finished turn that needs no model, plan state, papers)."""
    stance = turn_stance(s, text, study_id=study_id, steer=steer)
    if stance["scope"] == "out-of-scope":
        return (
            stance,
            {**holding_turn(SCOPE_REDIRECT, stance), "source": "scope"},
            None,
            [],
        )
    if decision:
        return stance, _decision_turn(s, study_id, stance), None, []
    if client is None:
        raise ModelUnavailable(NO_MODEL)
    state = (
        study_plan.plan_state(_moves(s, study_id), draft_base_yaml(s, study_id))
        if study_id
        else study_plan.PlanState(accepted=study_plan.plan_of(None))
    )
    if study_plan.low_information(text):
        # Nothing to search for or reason about; no model call is spent on it.
        unclear = study_plan.unclear_reply(state, _turns(s, study_id))
        return stance, {**holding_turn(unclear, stance), "source": "scripted"}, None, []
    return stance, None, state, _retrieve(s, text, study_id)


def _unavailable(down: study_plan.Unreachable) -> ModelUnavailable:
    return ModelUnavailable(
        {
            "rejected": MODEL_REJECTED,
            "billing": MODEL_BILLING,
            "limited": MODEL_LIMITED,
        }.get(down.reason, MODEL_SILENT)
    )


def _close(
    s: Session, turn: dict | None, *, seq: int, stance: dict, papers: list[dict]
) -> dict:
    """The model's turn with each card's citations grounded in the corpus."""
    if turn is None:
        raise ModelUnavailable(MODEL_UNUSABLE)
    moves = []
    retrieved = {paper["ref"] for paper in papers}
    for i, spec in enumerate(turn["moves"]):
        cited = tuple(dict.fromkeys(spec.pop("cites", None) or ()))
        grounding = _resolve_grounding(s, cited)
        retrieved.update(g["ref"] for g in grounding)
        moves.append(
            {
                "moveId": f"t{seq}-m{i + 1}",
                **spec,
                "grounding": grounding,
                "status": "proposed",
            }
        )
    return {
        **holding_turn(turn["text"], stance),
        "moves": moves,
        "questions": turn["questions"],
        "withdrawn": turn["withdrawn"],
        "recommendations": papers,
        "retrievedRefs": sorted(retrieved),
        "source": "llm",
    }


def respond(
    s: Session,
    text: str,
    *,
    seq: int,
    study_id: str | None = None,
    client=None,
    steer: str | None = None,
    decision: dict | None = None,
) -> dict:
    """One platform turn responding to researcher ``text``."""
    stance, done, state, papers = _open(
        s, text, study_id=study_id, client=client, steer=steer, decision=decision
    )
    if done is not None:
        return done
    try:
        turn = study_plan.converse(
            client,
            text,
            study_id or "study",
            state=state,
            turns=_turns(s, study_id),
            papers=papers,
            answers_only=not elicitation.proposals_permitted(stance["steer"]),
        )
    except study_plan.Unreachable as down:
        raise _unavailable(down) from down
    return _close(s, turn, seq=seq, stance=stance, papers=papers)


def respond_streaming(
    s: Session,
    text: str,
    *,
    seq: int,
    study_id: str | None = None,
    client=None,
    steer: str | None = None,
    decision: dict | None = None,
):
    """:func:`respond`, yielding the reply's prose as the model writes it."""
    stance, done, state, papers = _open(
        s, text, study_id=study_id, client=client, steer=steer, decision=decision
    )
    if done is not None:
        if done["text"]:
            yield done["text"]
        return done
    try:
        turn = yield from study_plan.converse_streaming(
            client,
            text,
            study_id or "study",
            state=state,
            turns=_turns(s, study_id),
            papers=papers,
            answers_only=not elicitation.proposals_permitted(stance["steer"]),
        )
    except study_plan.Unreachable as down:
        raise _unavailable(down) from down
    return _close(s, turn, seq=seq, stance=stance, papers=papers)
