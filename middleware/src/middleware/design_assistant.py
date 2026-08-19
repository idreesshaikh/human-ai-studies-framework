"""The design assistant: one researcher turn in, one platform turn out.

Prose plus individually-decidable design moves and grounded paper
recommendations (FR-CONV-1.3), produced by a language model working inside
constraints this module computes and *enforces*:

- **Retrieval happens first.** Papers and templates are matched before the
  model is asked anything, so what it may cite is bounded before it speaks.
- **The stance is enforced, not requested.** A question gets an answer rather
  than a fresh batch of proposals; a design shape is withheld until the study
  is understood. Both are checked in code after the model replies
  (:func:`_permitted_moves`), because a prompt can be ignored.
- **Repetition is filtered.** A move already accepted, rejected, or awaiting
  a decision never comes back, however often the model re-proposes it.

There was once a keyword-routed fallback here that answered when no model was
configured. It read as a conversation without being one, so it is gone; see
:class:`ModelUnavailable`.

**Cite-what-you-retrieved (FR-CONV-2.2 / FR-ETH-4).** A move's grounding is
built *only* from corpus rows the tools returned in this exchange — every
citation is resolved against the paper store via
:func:`matching.get_paper_metadata`, so a move can never carry a source the
platform doesn't hold. A ref that doesn't resolve is dropped and the move is
labeled unsourced; the grep-the-output test (F2.1) asserts exactly this.
"""

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

#: How many prior turns to feed the LLM as history (token-budget cap;
#: FR-CONV-1.4). A generous-enough window for a design conversation
#: without unbounded growth per turn.
_LLM_HISTORY_TURNS = 20

#: How many moves per status bucket the design state carries into the LLM
#: prompt (token budget — dedup still sees every move via ``keyTexts``).
_STATE_MOVE_CAP = 30

#: Near-duplicate thresholds (tunable): two moves are the same move when
#: their content terms overlap this much (denominator: the smaller term
#: set, so a short prior move can't swallow a longer distinct one) or
#: their full texts are this similar. The term-overlap test only fires
#: with enough terms to be meaningful; short texts rely on the ratio.
_DUP_TOKEN_OVERLAP = 0.8
_DUP_SEQ_RATIO = 0.85
_DUP_MIN_TERMS = 3


#: A message carrying one of these words is asking about design at all, even
#: when it names none of a specific template's jargon ("help me with design"
#: matches no template's own keyword profile below). Used to widen the
#: candidate menu rather than leave the model with nothing to choose from.
_DESIGN_INTENT_WORDS = ("design", "statistic", "test", "how many", "template")

#: Template-match strength that counts as the researcher naming a design
#: themselves (FR-CONV-10). A template's own keyword scores 2 and its design
#: type 3, while a bare title word scores 1 — and "design" is a title word of
#: nearly every template, so 1 would make "what design should I use?" look
#: like an answer to itself.
_NAMED_DESIGN_SCORE = 2


#: How many times one design turn is attempted before the conversation gives
#: up on it. A provider blip - a 429, a 5xx, a truncated JSON body - is the
#: common failure and it is usually gone by the next call, so retrying costs
#: one round-trip and saves the turn.
TURN_ATTEMPTS = 2


def holding_turn(reason: str, stance: dict | None = None) -> dict:
    """What the conversation returns when it could not reach a model.

    Deliberately *not* an answer. It proposes nothing, cites nothing, and
    changes no draft - so it cannot be mistaken for the design conversation
    the way the old keyword assistant could. All it does is say what happened
    and leave the researcher somewhere they can act from, which is the one
    thing a bare 503 failed to do: the message they had just typed came back
    as an error banner with no thread to return to.

    It is not persisted either. An outage is not part of the study's design
    record, and a stored "I couldn't reach the model" would be fed back to
    that model as history the next time round.
    """
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


#: What the researcher is told, by cause. Both name the next thing they can do.
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
    """The design conversation could not reach a language model.

    The platform used to answer anyway, from a keyword-routed script: type
    "trust" and get the over-trust reply, type "design" and get a template.
    It read as a conversation and was not one - it could not follow an
    unusual study, could not answer a question it had no branch for, and
    proposed the same handful of moves to everyone. A design conversation
    that cannot actually converse is worse than an honest refusal, because
    the researcher only discovers the difference after acting on it.

    So the conversation requires a model, and says so plainly when it has
    none. Everything else on the platform still works without one.
    """


def recommend_templates(
    text: str, *, support: dict[str, int] | None = None
) -> list[dict[str, Any]]:
    """Recommend design archetype templates matching the researcher's input.

    Keyword-based matching over template metadata, ranked by match strength.
    Each template's own curated ``designSignature`` (the phrases the
    repertoire counts corpus usage by, FR-TPL) is part of its keyword
    profile, so a design's vocabulary is declared in one place rather than
    duplicated here.

    ``support`` is the repertoire's corpus-usage count per template id; when
    given it breaks ties, so an equally-matching *common* design is offered
    before a rare one. Absent, matching is unchanged.

    A message with clear design intent but no template-specific jargon
    (score 0 on every template) still gets the full catalog as candidates -
    an empty list would silently block the LLM (constrained to cite only
    what this function retrieves, ``design_llm.propose_turn``) from ever
    proposing a template for exactly the open-ended asks researchers
    actually type. Only a message with *no* design intent at all falls
    through to an empty list.
    """
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

    # Equal match strength → the design the corpus actually uses more often
    # wins (common before rare); template id last so ordering is stable.
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
            # The raw strength, not just its prose: 2+ means the researcher
            # used this design's own vocabulary, while 1 is only a title word
            # (the word "design" matches almost every template's title).
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
    """Per-template corpus usage from the repertoire, for tie-breaking.

    Memoized by the repertoire itself, and degrading: if the ranking is
    unavailable for any reason the conversation just loses the common-first
    tie-break, never the recommendation (NFR-4 posture).
    """
    try:
        from middleware import template_repertoire

        return {e["id"]: e["support"] for e in template_repertoire.rank_repertoire(s)}
    except Exception as exc:  # noqa: BLE001 - a tie-break is never worth a 500
        log.warning("repertoire support unavailable for tie-breaking: %s", exc)
        return {}


def recommend_prescription(design_shape: str) -> dict[str, Any] | None:
    """Look up the prescription for a design shape (FR-TPL-6).

    Returns a dict with the prescription row, or None if unknown.
    """
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
    """A design move before grounding is resolved. ``refs`` are corpus paper
    references the move *wants* to cite; only those that resolve survive."""

    kind: str
    target: str
    proposal: str
    patch: dict | None
    refs: tuple[str, ...]


@dataclass
class Turn:
    """One platform response: prose + the moves it proposes.

    The model produces these; everything downstream - grounding resolution,
    repetition filtering, stance enforcement - operates on this shape and is
    indifferent to which model wrote it.
    """

    text: str
    moves: tuple[ProposedMove, ...]
    match_query: str | None = None


def _template_source_refs(template_id: str | None) -> tuple[str, ...]:
    """The paper refs a template cites as its design's sources (FR-TPL) — used
    to ground a choose-template move. Empty on any lookup failure (degrade)."""
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
    """Build grounding from corpus rows only — cite-what-you-retrieved. A ref
    that doesn't resolve is silently dropped (the move degrades to unsourced),
    never fabricated (FR-CONV-2.2)."""
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
    """Prior turns as ``{"role", "content"}`` dicts, oldest first, capped to
    ``_LLM_HISTORY_TURNS`` (a token-budget cap, not a correctness
    requirement) - the shape an LLM chat-completions call expects.

    A platform turn's content includes **the moves it proposed and what the
    researcher did with them**, not just its prose. The proposals live in
    ``design_moves``, so a text-only history left the model unable to see
    what it had itself put on the table: asked "why did you propose that?",
    it had nothing to explain and could only invent something new — the
    failure that reads as "it forgot what we were talking about". Decisions
    are included too, so an already-rejected idea is not re-offered.
    """
    if study_id is None:
        return []
    rows = s.execute(
        select(ConversationTurn)
        .where(ConversationTurn.study_id == study_id)
        .order_by(ConversationTurn.seq.desc())
        .limit(_LLM_HISTORY_TURNS)
    ).scalars().all()
    turn_ids = [row.id for row in rows if row.role == "platform"]
    moves_by_turn: dict[str, list[DesignMoveRow]] = {}
    if turn_ids:
        for mv in s.scalars(
            select(DesignMoveRow)
            .where(DesignMoveRow.turn_id.in_(turn_ids))
            # Bucketed per turn, so only in-turn order matters — seq is the
            # proposal order (id would put e.g. m10 before m2).
            .order_by(DesignMoveRow.seq)
        ):
            moves_by_turn.setdefault(mv.turn_id, []).append(mv)

    history: list[dict] = []
    for row in reversed(rows):
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
    """Everything the *researcher* has said in this study, oldest first.

    The understanding model reads only these: the platform mentioning
    "conditions" in a question it asked cannot make the platform better
    informed (FR-CONV-10).
    """
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


def turn_stance(
    s: Session,
    text: str,
    *,
    study_id: str | None = None,
    profile: str | None = None,
    steer: str | None = None,
) -> dict:
    """What this turn is, how much is understood, and what may be proposed.

    Computed deterministically (FR-CONV-9/10) so the conversation behaves the
    same with or without an LLM, and so the two rules that matter are
    *enforced* rather than merely requested of a model:

    - a follow-up question gets an answer, not a fresh batch of proposals;
    - a design shape is not named until the idea is understood, unless the
      researcher explicitly asks for one anyway (their study, their call).
    """
    prior = researcher_texts(s, study_id)
    understanding = elicitation.assess_understanding([*prior, text])
    intent = elicitation.classify_turn(text)
    # A researcher who names a design themselves has not been boxed into
    # anything — recording their choice is the platform's job, so the gate
    # opens. A follow-up question never counts, or "why the crossover?" would
    # re-propose the crossover.
    named_design = intent != "followup-question" and (
        # The recommender already exists to map researcher phrasing onto a
        # design ("a paired RCT", "pre/post"); a positive keyword match there
        # *is* the researcher naming one. The corpus-facing signatures are
        # checked too, since abstract vocabulary ("crossover",
        # "counterbalanced") is also how researchers speak.
        any(r["matchScore"] >= _NAMED_DESIGN_SCORE for r in recommend_templates(text))
        or elicitation.names_a_design(
            text, [tpl.get("designSignature", []) for tpl in list_templates()]
        )
    )
    # A profile the caller declared is an account fact and outranks the dial;
    # the dial's implied register only fills in for someone who never set one.
    declared = profile if profile in elicitation.PROFILES else None
    return {
        "intent": intent,
        "steer": steer if steer in elicitation.STEER_LEVELS else None,
        "profile": declared or elicitation.steer_profile(steer),
        "understanding": elicitation.understanding_summary(understanding),
        "nextQuestion": elicitation.next_question(understanding),
        "namedDesign": named_design,
        # An explicit ask lowers the gate but never removes it; a follow-up
        # question never opens it, because "why did you pick that?" is not
        # "pick one".
        "mayProposeDesign": named_design
        or elicitation.ready_for_design(
            understanding, requested=intent == "design-request"
        ),
        # Two gates, both hard: a follow-up question gets an answer rather
        # than a fresh batch, and an steer level of "checks" proposes
        # nothing at all. Either one closing is enough to close it.
        "mayProposeMoves": intent != "followup-question"
        and elicitation.proposals_permitted(steer),
    }


def _slot_directive(state: dict | None) -> str:
    """The protocol's outstanding slots, as an instruction the model can act
    on: what is missing, what type each takes, and how to fill it.

    Without this the model has no way to know a protocol is incomplete - the
    conversation would happily talk on past a missing sample size, because
    nothing in the prompt ever mentioned one was needed.
    """
    advice = (state or {}).get("taskAdvice") or ""
    outstanding = (state or {}).get("outstandingSlots") or []
    if not outstanding:
        complete = (
            "The protocol has every slot it needs. Do not invent more work: "
            "if the researcher is happy, tell them it is ready to compile."
        )
        # Optional, so it never blocks a compile - but a study is far more
        # analysable with tasks than without, and this is the last honest
        # moment to say so.
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
    # Register first, then how much to drive: the two levers the steer dial
    # moves together (elicitation.STEER_LEVELS).
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
            "DO NOT propose a choose-template move this turn: too little of "
            "the study is understood for a design shape to be a considered "
            "choice rather than a guess, and one would be discarded before "
            "the researcher ever saw it. Keep drawing the idea out instead. "
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
    # Only once the study is understood: naming missing protocol slots to
    # someone who has said one sentence about their idea turns a conversation
    # into a form.
    if stance["mayProposeDesign"]:
        lines.append(_slot_directive(state))
    return "\n\n".join(lines)


def _permitted_moves(
    moves: tuple[ProposedMove, ...], stance: dict
) -> tuple[ProposedMove, ...]:
    """Apply the stance to a script's moves — the enforcement half.

    A prompt can be ignored; this cannot. A question turn keeps only
    cautions, and a design shape cannot slip through before the study is
    understood. Dropped moves are logged, never silently vanished.
    """
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
        if move.kind == "choose-template" and not stance["mayProposeDesign"]:
            log.info("held back choose-template: the study isn't understood yet")
            continue
        kept.append(move)
    return tuple(kept)


def _move_key_text(proposal: str, patch: dict | None) -> str:
    """The semantic payload of a move for near-duplicate comparison: its
    proposal sentence plus the patch value it would write (a re-worded
    proposal carrying the same value is still the same move)."""
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
    """Drop moves the conversation has already seen (FR-CONV: an accepted
    move is in the draft, a rejected one was declined, an undecided one is
    still on the table — re-pitching any of them is repetition). The guard
    runs regardless of source, so repetition is suppressed even when the
    LLM ignores its instructions. ``state is None`` (stateless demo, no
    study) is a no-op.

    A content move (one carrying a patch) is compared only against prior
    *content* moves — never against patch-less cautions. A caution fills
    no section, and the section move that addresses a caution's concern
    naturally restates its wording; treating that as repetition would
    permanently block the section (an accepted ethics caution must not
    stop the ethics posture from ever being proposed). A new caution is
    compared against both pools — echoing either an existing caution or
    existing draft content is still repetition."""
    if state is None:
        return moves
    content = state.get("keyTexts") or []
    advisory = state.get("advisoryTexts") or []
    template_ids = set(state.get("templateIds") or [])
    kept = []
    for sm in moves:
        if sm.kind == "choose-template":
            tid = (sm.patch or {}).get("templateId")
            if tid and tid in template_ids:
                continue
        else:
            key = _move_key_text(sm.proposal, sm.patch)
            prior = content if sm.patch else [*content, *advisory]
            if any(_is_near_duplicate(key, p) for p in prior):
                continue
        kept.append(sm)
    return tuple(kept)


def _load_design_state(s: Session, study_id: str | None) -> dict | None:
    """The structured design state the prose history can't carry: every
    prior move bucketed by decision status, the draft's filled/empty
    sections (computed deterministically via :func:`compiler.compile_moves`
    — no LLM), and the accepted template if any. ``None`` when there's no
    study or no moves yet — the stateless demo path stays stateless."""
    if study_id is None:
        return None
    rows = s.scalars(
        select(DesignMoveRow)
        .join(ConversationTurn, DesignMoveRow.turn_id == ConversationTurn.id)
        .where(DesignMoveRow.study_id == study_id)
        # Conversation order — ordering by id would sort turns by their
        # random hex prefix, compiling moves out of sequence.
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
    # Coverage mirrors the researcher-visible slot meter (the client draft
    # model, ``platform/src/lib/compiler.ts``): a template fills only the
    # ``design`` slot, an add/set-instrument move fills ``instruments``,
    # every other section needs its own accepted append/set move. NOT
    # ``result.unresolved`` — that reports ``[]`` once a template
    # instantiates, which would tell the model every slot is filled while
    # the researcher still sees empty ones.
    sections = compiler.compile_sections(moves)
    has_instrument = any(
        m["status"] == "accepted"
        and (m["patch"] or {}).get("op") in ("add-instrument", "set-instrument")
        for m in moves
    )
    filled = [
        sec
        for sec in compiler.SECTIONS
        if sections[sec]
        or (sec == "design" and result.template_id is not None)
        or (sec == "instruments" and has_instrument)
    ]
    empty = [sec for sec in compiler.SECTIONS if sec not in filled]
    buckets: dict[str, list[dict]] = {"accepted": [], "rejected": [], "proposed": []}
    key_texts: list[str] = []
    advisory_texts: list[str] = []
    template_ids: list[str] = []
    for m in moves:
        patch = m["patch"] or {}
        if m["kind"] == "choose-template":
            section = "design"
            tid = patch.get("templateId")
            if tid:
                template_ids.append(tid)
        else:
            # `target` is model-authored free text (design_llm's own JSON
            # contract), not a validated enum like `patch.section` — an
            # earlier prompt literally showed "protocol.path" as its example
            # value, which the model echoed as a literal "protocol." prefix
            # ("protocol.design", "protocol.researchQuestions") rather than as
            # a placeholder to fill in. Stripped here so a stale move from
            # before that prompt fix, or any future drift, can't feed the
            # bogus section name "protocol" back into the state block the
            # model reads on its next turn.
            fallback_target = (m["target"] or "").removeprefix("protocol.")
            section = patch.get("section") or fallback_target.split(".")[0]
        # Two dedup pools: content moves (carry a patch — they fill draft
        # sections) vs advisory ones (patch-less cautions). Kept apart so a
        # section move addressing a caution's concern is never mistaken for
        # a repeat of it (see _filter_repeated_moves).
        key = _move_key_text(m["proposal"], m["patch"])
        (key_texts if m["patch"] else advisory_texts).append(key)
        bucket = buckets.get(m["status"])
        if bucket is not None and len(bucket) < _STATE_MOVE_CAP:
            bucket.append(
                {"kind": m["kind"], "section": section, "proposal": m["proposal"]}
            )
    # What the *protocol* still lacks, as opposed to which of the eight
    # conversation sections are bare. The two are different questions and the
    # second was standing in for the first: a researcher could fill every
    # section, be told nothing was outstanding, and still not have a protocol.
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
        # Not a gap the protocol can name - tasks are optional - but the one
        # thing most worth prompting for, because a study collected without
        # them can never be re-analysed per task.
        "taskAdvice": compiler.task_recommendation(result.draft),
        "templateId": result.template_id,
        "templateIds": template_ids,
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
    """One platform turn responding to researcher ``text``.

    Returns ``{text, moves, recommendations, retrievedRefs, source}``.
    ``moves`` are ``proposed`` (the researcher accepts/rejects each).
    ``retrievedRefs`` is every corpus ref the tools returned this exchange —
    persisted on the turn so the grep-the-output grounding test can verify
    no move cites outside it (F2.1).

    Retrieval runs first — unconditional and deterministic — and the model
    only selects and phrases against what was actually retrieved, so what it
    may cite is bounded before it is asked anything. Raises
    :class:`ModelUnavailable` when there is no model, or when the one
    configured fails: an unanswerable turn is reported, never faked.
    """
    if client is None:
        raise ModelUnavailable(NO_MODEL)
    stance = turn_stance(
        s, text, study_id=study_id, profile=profile, steer=steer
    )
    state = _load_design_state(s, study_id)
    papers, templates, history = _retrieve(s, text, study_id, history)
    from middleware import design_llm  # deferred: breaks the import cycle

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
    """The deterministic retrieval every LLM turn is constrained to cite
    (papers, templates, history) — run *before* the model is asked anything,
    so the model can only select from what was actually retrieved."""
    papers = matching.match_papers(s, text, study_id=study_id, limit=8, use_llm=False)
    templates = recommend_templates(text, support=corpus_support(s))
    # An explicit history (the stateless demo passes the visitor's own
    # prior turns) wins; otherwise load it from the study's stored turns.
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
    """:func:`respond`, yielding the reply's prose as the model writes it.

    A generator whose ``return`` value is the identical result dict, so the
    streamed turn and the blocking turn are the same turn — the stream is a
    live view of the prose, never a second, differently-worded answer. A
    provider without a stream seam simply yields nothing and returns the
    same result. Raises :class:`ModelUnavailable` on the same terms as
    :func:`respond`.
    """
    if client is None:
        raise ModelUnavailable(NO_MODEL)
    stance = turn_stance(
        s, text, study_id=study_id, profile=profile, steer=steer
    )
    # The streamed turn sees exactly what the blocking turn sees — the same
    # design state and the same stance — or the two paths would diverge.
    state = _load_design_state(s, study_id)
    papers, templates, history = _retrieve(s, text, study_id, history)
    from middleware import design_llm  # deferred: breaks the import cycle

    directive = _directive(stance, state)
    turn = yield from design_llm.propose_turn_streaming(
        client, text, history, papers, templates, directive,
        design_state=state,
    )
    if turn is None:
        # The stream produced nothing usable. Retry once without it: a
        # half-delivered stream is the most common way a turn is lost, and
        # the blocking call often succeeds on exactly the same request.
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
    """Turn the model's reply into the platform turn's result dict: grounding
    resolved against retrieved rows, recommendations, and the design
    recommender's prescription/figures.

    Two independent filters apply, and both are *enforcement* rather than
    instruction — a prompt can be ignored, this cannot:

    1. **Repetition** — a move already accepted, rejected, or awaiting a
       decision is dropped, however many times the model re-proposes it.
    2. **Stance** (FR-CONV-9/10) — a question turn keeps only cautions, and
       a design shape is withheld until the study is understood.
    """
    kept = _filter_repeated_moves(turn.moves, state)
    if kept != turn.moves:
        turn = Turn(turn.text, kept, turn.match_query)
    retrieved: set[str] = set()

    moves = []
    for i, sm in enumerate(_permitted_moves(turn.moves, stance)):
        grounding = _resolve_grounding(s, sm.refs)
        # A choose-template move is grounded by the papers that established its
        # design — attach them so a template choice is never "unsourced" (the
        # template encodes those papers' design; they are its references).
        if sm.kind == "choose-template" and not grounding and sm.patch:
            tid = sm.patch.get("templateId")
            grounding = _resolve_grounding(s, _template_source_refs(tid))
        retrieved.update(g["ref"] for g in grounding)
        moves.append(
            {
                "moveId": f"t{seq}-m{i + 1}",
                "kind": sm.kind,
                "target": sm.target,
                "proposal": sm.proposal,
                "patch": sm.patch,
                "grounding": grounding,
                "status": "proposed",
            }
        )

    # Reuse the retrieval already made for the candidate menu — never a
    # second match_papers call for the same turn.
    recommendations = llm_recommendations or []
    retrieved.update(r["ref"] for r in recommendations)

    # Design recommender (Phase 22): template matches, prescription, figures.
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
        # What the platform understands about the study so far, and what it is
        # therefore willing to propose — surfaced rather than hidden, so the
        # researcher can see why a design hasn't been named yet (FR-CONV-10).
        "understanding": stance["understanding"],
        "turnIntent": stance["intent"],
        "retrievedRefs": sorted(retrieved),
        "source": "llm",
    }
