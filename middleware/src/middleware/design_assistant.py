"""The design assistant: one researcher turn in, one platform turn out."""

from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import compiler, elicitation, matching
from middleware.db import ConversationTurn, DesignMoveRow
from middleware.template_registry import list_templates

log = logging.getLogger(__name__)

_LLM_HISTORY_TURNS = 20

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
    "Set MISTRAL_API_KEY on the middleware and reload. Everything else on "
    "the platform works without one."
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
    The paper refs a template cites as its design's sources (FR-TPL) — used to ground a
    choose-template move.
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
    """Build grounding from corpus rows only — cite-what-you-retrieved."""
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
        # `history` itself (the `continue` below) — a holding turn carries no
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
            # Bucketed per turn, so only in-turn order matters — seq is the proposal
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
        # turns said it — skip it here the same way an empty turn is skipped
        # below.
        if row.role == "platform" and row.source == "unavailable":
            continue
        moves = moves_by_turn.get(row.id, [])
        content = row.text or ""
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
    shapes they mean. Naming an id is naming a design — an explicit ask must
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
    return {
        "intent": intent,
        "steer": steer if steer in elicitation.STEER_LEVELS else None,
        "profile": declared or elicitation.steer_profile(steer),
        "understanding": elicitation.understanding_summary(understanding),
        "nextQuestion": elicitation.next_question(understanding),
        "namedDesign": named_design,
        # An explicit ask lowers the gate but never removes it; a follow-up question
        # never opens it, because "why did you pick that?" is not "pick one".
        "mayProposeDesign": named_design
        or elicitation.ready_for_design(
            understanding, requested=intent == "design-request"
        ),
        "mayProposeMoves": intent != "followup-question"
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
        complete = (
            "The protocol has every slot it needs. Do not invent more work: "
            "if the researcher is happy, tell them it is ready to compile."
        )
        # Optional, so it never blocks a compile - but a study is far more analysable
        # with tasks than without, and this is the last honest moment to say so.
        return f"{complete}\n\n{advice}" if advice else complete
    fillable = [s for s in outstanding if s["valueType"] != "derived"]
    lines = [
        "PROTOCOL SLOTS STILL OUTSTANDING (the draft cannot compile until "
        "each is filled): " + ", ".join(s["label"] for s in outstanding) + "."
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
            "a session length and present it as theirs. Otherwise ask for the "
            "first one, in your own words: " + fillable[0]["question"]
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

    if stance["intent"] == "followup-question":
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
            + ". Ask about the first of those. One question, in your own "
            "words, informed by what they have already told you. A good "
            "next question is: "
            + (stance["nextQuestion"] or "(none)")
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


def _permitted_moves(
    moves: tuple[ProposedMove, ...], stance: dict
) -> tuple[ProposedMove, ...]:
    """Apply the stance to a script's moves — the enforcement half."""
    kept = []
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
        kept.append(move)
    return tuple(kept)


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
    draft, a rejected one was declined, an undecided one is still on the table —
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
    via :func:`compiler.compile_moves` — no LLM), and the accepted template if any.
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
    filled = [
        sec
        for sec in compiler.SECTIONS
        if sections[sec]
        or (
            sec == "design"
            and (result.template_id is not None or has_merged)
        )
        or (sec == "instruments" and has_instrument)
    ]
    empty = [sec for sec in compiler.SECTIONS if sec not in filled]
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
        "sessionMinutes": session.get("durationMinutes"),
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
) -> dict:
    """One platform turn responding to researcher ``text``."""
    if client is None:
        raise ModelUnavailable(NO_MODEL)
    stance = turn_stance(
        s, text, study_id=study_id, profile=profile, steer=steer
    )
    state = _load_design_state(s, study_id)
    papers, templates, history = _retrieve(s, text, study_id, history)
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
    s: Session, text: str, study_id: str | None, history: list[dict] | None
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    The deterministic retrieval every LLM turn is constrained to cite (papers,
    templates, history) — run *before* the model is asked anything, so the model can
    only select from what was actually retrieved.
    """
    papers = matching.match_papers(s, text, study_id=study_id, limit=8, use_llm=False)
    templates = recommend_templates(text, support=corpus_support(s))
    # An explicit history (the stateless demo passes the visitor's own prior turns)
    # wins; otherwise load it from the study's stored turns.
    if history is None:
        history = _load_history(s, study_id)
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
):
    """:func:`respond`, yielding the reply's prose as the model writes it."""
    if client is None:
        raise ModelUnavailable(NO_MODEL)
    stance = turn_stance(
        s, text, study_id=study_id, profile=profile, steer=steer
    )
    state = _load_design_state(s, study_id)
    papers, templates, history = _retrieve(s, text, study_id, history)
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
    kept = _filter_repeated_moves(turn.moves, state)
    if kept != turn.moves:
        turn = Turn(turn.text, kept, turn.match_query)
    retrieved: set[str] = set()

    moves = []
    for i, sm in enumerate(_permitted_moves(turn.moves, stance)):
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

    # Reuse the retrieval already made for the candidate menu — never a second
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
        "text": turn.text,
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
