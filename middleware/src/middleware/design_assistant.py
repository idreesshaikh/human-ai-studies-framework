"""The design assistant.

The server-side counterpart of the client stub (``platform/src/lib/
designStub.ts``): it turns researcher input into a platform turn — prose plus
individually-decidable design moves and grounded paper recommendations
(FR-CONV-1.3). It is the **no-LLM degradation path** made real, not throwaway
mock data: with no ``MISTRAL_API_KEY`` the platform is fully usable, just not
conversational (FR-CONV §5, NFR-4). When a key is present, the Mistral seam
(:func:`respond`'s ``client`` hook) swaps in behind the same return shape.

**Cite-what-you-retrieved (FR-CONV-2.2 / FR-ETH-4).** A move's grounding is
built *only* from corpus rows the tools returned in this exchange — every
citation is resolved against the paper store via
:func:`matching.get_paper_metadata`, so a move can never carry a source the
platform doesn't hold. A ref that doesn't resolve is dropped and the move is
labeled unsourced; the grep-the-output test (F2.1) asserts exactly this.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import elicitation, matching
from middleware.db import ConversationTurn, DesignMoveRow
from middleware.template_registry import list_templates

log = logging.getLogger(__name__)

#: How many prior turns to feed the LLM as history (token-budget cap;
#: FR-CONV-1.4). A generous-enough window for a design conversation
#: without unbounded growth per turn.
_LLM_HISTORY_TURNS = 20


#: Design-intent signal shared with :func:`_pick_script`'s scripted-fallback
#: routing: a message carrying one of these words is asking about design at
#: all, even when it names none of a specific template's jargon (e.g.
#: "help me with design" matches no template's own keyword profile below).
_DESIGN_INTENT_WORDS = ("design", "statistic", "test", "how many", "template")


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
            "matchReason": (
                f"Matched {score} keyword(s): researcher intent"
                if score > 0
                else "No specific match — offered from the full catalog"
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
class ScriptedMove:
    """A design move before grounding is resolved. ``refs`` are corpus paper
    references the move *wants* to cite; only those that resolve survive."""

    kind: str
    target: str
    proposal: str
    patch: dict | None
    refs: tuple[str, ...]


@dataclass
class Script:
    """One scripted platform response: prose + moves + which query (if any)
    to run for real paper recommendations."""

    text: str
    moves: tuple[ScriptedMove, ...]
    match_query: str | None = None


# The opening prompt shown before the researcher types (mirrors the client).
OPENING = (
    "What do you want to find out? Try: “Junior developers over-trust "
    "AI-generated code.”"
)


def _over_trust_script() -> Script:
    return Script(
        text=(
            "Good starting point. “Over-trust” is a claim about how "
            "developers review AI code before accepting it — measurable, not "
            "just felt. Here are moves that turn it into a study, each "
            "grounded. Two papers in the corpus match closely."
        ),
        moves=(
            ScriptedMove(
                "add-rq",
                "researchQuestions[]",
                "RQ: Do junior developers accept AI-generated code with less "
                "review than seniors?",
                {
                    "section": "researchQuestions",
                    "op": "append",
                    "value": "Do junior developers accept AI-generated code "
                    "with less review than seniors?",
                },
                ("corpus:trust-in-ai-code-generation",),
            ),
            ScriptedMove(
                "add-measure",
                "measures[]",
                "Measure: review latency — time an AI suggestion is visible "
                "before accept/reject.",
                {
                    "section": "measures",
                    "op": "append",
                    "value": "Review latency (suggestion-visible-to-decision time)",
                },
                ("corpus:trust-in-ai-code-generation",),
            ),
            ScriptedMove(
                "add-measure",
                "measures[]",
                "Measure: code-correctness outcome — acceptance tests on the "
                "delivered code.",
                {
                    "section": "measures",
                    "op": "append",
                    "value": "Code-correctness outcome (acceptance-test pass rate)",
                },
                ("corpus:insecure-code-with-ai-assistants",),
            ),
            ScriptedMove(
                "set-parameter",
                "conditions[]",
                "Between-groups factor: experience level (junior / senior).",
                {
                    "section": "conditions",
                    "op": "append",
                    "value": "Experience level: junior vs. senior",
                },
                (),  # the researcher's own scoping decision — unsourced
            ),
        ),
        match_query="junior developers over-trust AI-generated code review",
    )


def _self_report_script() -> Script:
    return Script(
        text=(
            "I'd challenge measuring productivity by self-report alone. The "
            "corpus has direct evidence against it."
        ),
        moves=(
            ScriptedMove(
                "caution",
                "measures",
                "Caution: self-reported speed diverges from measured speed. "
                "Pair it with an objective task-time measure.",
                None,  # a caution makes no draft change
                ("corpus:metr-early-2025-dev-productivity",),
            ),
            ScriptedMove(
                "add-measure",
                "measures[]",
                "Measure: task completion time (objective), alongside the "
                "perception item.",
                {
                    "section": "measures",
                    "op": "append",
                    "value": "Task completion time (objective)",
                },
                ("corpus:metr-early-2025-dev-productivity",),
            ),
        ),
    )


def _design_script() -> Script:
    return Script(
        text=(
            "For a small-N developer study, the corpus points to a "
            "within-subjects RCT with task counterbalancing and a paired "
            "non-parametric test. The METR template encodes exactly this and "
            "prescribes its statistics — accepting it compiles a complete, "
            "validating protocol draft."
        ),
        moves=(
            ScriptedMove(
                "choose-template",
                "design",
                "Adopt the METR within-subjects RCT template (task time + "
                "perception + correctness), prescribing Wilcoxon signed-rank "
                "with matched-pairs rank-biserial.",
                {"templateId": "metr-rct-v1", "parameters": {}},
                (
                    "corpus:metr-early-2025-dev-productivity",
                    "corpus:guidelines-empirical-llm-se",
                ),
            ),
        ),
    )


def _benchmark_script() -> Script:
    return Script(
        text=(
            "Benchmark score isn't human utility. If you use a benchmark, "
            "pair it with a real-task outcome."
        ),
        moves=(
            ScriptedMove(
                "caution",
                "measures",
                "Caution: a benchmark measures the model, not your "
                "participants' outcomes.",
                None,
                ("corpus:realhumaneval",),
            ),
        ),
    )


def _add_instrument_script() -> Script:
    """Adding a capture stream mid-study — the Slice D amendment path. A new
    instrument is a new data stream (consent-relevant by rule, F4.1); the
    platform says so plainly rather than letting the drift be silent."""
    return Script(
        text=(
            "Adding the agent-capture leg means a new data stream — the "
            "agent's tool calls and consent-matched conversation content. "
            "That's consent-relevant: once the study has ethics approval this "
            "becomes a version-visible amendment that pauses new sessions "
            "until you re-upload approval. Running sessions are untouched."
        ),
        moves=(
            ScriptedMove(
                "add-instrument",
                "instruments.agentCapture",
                "Add the agent-capture instrument (Claude Code adapter, "
                "metadata-only content policy).",
                {
                    "section": "instruments",
                    "op": "add-instrument",
                    "name": "agentCapture",
                    "config": {
                        "adapter": "claude-code",
                        "contentPolicy": "metadata-only",
                    },
                },
                ("corpus:guidelines-empirical-llm-se",),
            ),
        ),
    )


def _threshold_script() -> Script:
    """A pure instrument-config tweak — the F4.2 path. Not consent-relevant:
    it changes no data stream or policy, so it applies from the next session
    with no re-approval, and never mutates an in-flight session."""
    return Script(
        text=(
            "Loosening the stuck-detector threshold is an instrument tuning "
            "change, not a consent change. It applies from the next session; "
            "any session already running keeps the settings it started with."
        ),
        moves=(
            ScriptedMove(
                "reconfigure-instrument",
                "instruments.tern.stuck.thresholdSeconds",
                "Raise the stuck-detector threshold from 90s to 120s.",
                {
                    "section": "instruments",
                    "op": "reconfigure",
                    "name": "tern",
                    "path": ["stuck", "thresholdSeconds"],
                    "value": 120,
                },
                (),  # a tuning decision — the researcher's, unsourced
            ),
        ),
    )


_FOLLOWUP = Script(
    text=(
        "Tell me more so I can ground a move. What's the population, and is "
        "this live-instrumented or curated data? Right now these slots are "
        "still empty: participants, conditions, ethics posture."
    ),
    moves=(),
)


def _elicit_script(stance: dict) -> Script:
    """The no-LLM elicitation turn: ask the next real question and say what
    is still unknown, instead of the old fixed "tell me more".

    Names the facet rather than the protocol slot, because a researcher who
    hasn't said what they measure needs to be asked that, not told that
    ``statisticalPlan`` is empty.
    """
    understanding = stance["understanding"]
    missing = understanding["missingLabels"]
    parts = [stance["nextQuestion"] or "Tell me more about the study."]
    if missing:
        parts.append(
            "I'm still missing " + ", ".join(missing) + " — one thing at a time is "
            "fine, and I'll hold off on suggesting a design until the shape of "
            "the study actually follows from what you've told me."
        )
    return Script(text=" ".join(parts), moves=())


def _explain_script() -> Script:
    """The no-LLM answer to "why did you propose that?".

    With no model configured the platform cannot discuss its reasoning in
    prose — so it says exactly that, and points at the evidence it does hold,
    rather than answering a question with unrelated new proposals.
    """
    return Script(
        text=(
            "Fair question. Without a language model configured I can't talk "
            "through my reasoning freely — but nothing I proposed is "
            "unexplained: every move carries the paper it came from, so open "
            "its grounding to see the source and why it applies, and reject "
            "anything the source doesn't convince you of. Configure a model "
            "key and I can discuss the trade-offs properly."
        ),
        moves=(),
    )


def _pick_script(text: str, stance: dict | None = None) -> Script:
    """Deterministic input → script routing (mirrors the client stub).

    The stance leads: a question gets an answer, and an idea that isn't yet
    understood gets a question — so the no-LLM path behaves like the LLM path
    rather than jumping to a design from a single sentence (FR-CONV-10).
    """
    if stance is not None and stance["intent"] == "followup-question":
        return _explain_script()
    script = _topical_script(text)
    if stance is None or stance["mayProposeDesign"]:
        return script
    # Not enough is understood to name a design — but withholding the *shape*
    # is not a reason to withhold everything. Whatever this script says that
    # isn't a design shape (a caution, a measure the researcher named) still
    # stands, with the next real question added to it. Only when nothing but
    # the design is left does the turn become purely a question.
    safe = tuple(m for m in script.moves if m.kind != "choose-template")
    if not safe:
        return _elicit_script(stance)
    question = stance["nextQuestion"]
    return Script(
        text=" ".join(p for p in (script.text, question) if p),
        moves=safe,
        match_query=script.match_query,
    )


def _topical_script(text: str) -> Script:
    """Deterministic keyword routing to the scripted reply for this input."""
    q = text.lower()
    # Instrument evolution: checked first so "add the agent-capture
    # instrument" routes here, not into an over-trust/design match.
    if any(w in q for w in ("threshold", "stuck detector", "loosen", "tune")):
        return _threshold_script()
    if "instrument" in q or (
        "agent" in q and any(w in q for w in ("add", "capture", "leg", "stream"))
    ):
        return _add_instrument_script()
    if any(w in q for w in ("trust", "over-trust", "junior")):
        return _over_trust_script()
    if any(w in q for w in ("productiv", "faster", "speed")) and any(
        w in q for w in ("self-report", "survey", "ask", "perceiv")
    ):
        return _self_report_script()
    if any(w in q for w in _DESIGN_INTENT_WORDS):
        return _design_script()
    if any(w in q for w in ("benchmark", "humaneval", "pass@")):
        return _benchmark_script()
    return _FOLLOWUP


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
            .order_by(DesignMoveRow.id)
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
                + f" — researcher {mv.status} this"
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
    return {
        "intent": intent,
        "profile": profile if profile in elicitation.PROFILES else None,
        "understanding": elicitation.understanding_summary(understanding),
        "nextQuestion": elicitation.next_question(understanding),
        # An explicit ask lowers the gate but never removes it; a follow-up
        # question never opens it, because "why did you pick that?" is not
        # "pick one".
        "mayProposeDesign": elicitation.ready_for_design(
            understanding, requested=intent == "design-request"
        ),
        "mayProposeMoves": intent != "followup-question",
    }


def _directive(stance: dict) -> str:
    """The stance as this turn's instruction to the model."""
    understanding = stance["understanding"]
    lines = [elicitation.profile_guidance(stance["profile"])]

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
            + ". Ask about the first of those — one question, in your own "
            "words, informed by what they have already told you. A good "
            "next question is: "
            + (stance["nextQuestion"] or "(none)")
        )
    else:
        lines.append(
            "You now know who takes part, what they do, what is compared, "
            "what is measured, and what is possible — enough to design."
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
    elif stance["intent"] == "design-request":
        lines.append(
            "The researcher has explicitly asked you to name a design. Do so "
            "— and state plainly which of your assumptions it rests on, so a "
            "wrong one is easy for them to correct."
        )
    return "\n\n".join(lines)


def _permitted_moves(
    moves: tuple[ScriptedMove, ...], stance: dict
) -> tuple[ScriptedMove, ...]:
    """Apply the stance to a script's moves — the enforcement half.

    A prompt can be ignored; this cannot. A question turn keeps only
    cautions, and a design shape cannot slip through before the study is
    understood. Dropped moves are logged, never silently vanished.
    """
    kept = []
    for move in moves:
        if not stance["mayProposeMoves"] and move.kind != "caution":
            log.info("dropped %s move: this turn is a question, not a brief", move.kind)
            continue
        if move.kind == "choose-template" and not stance["mayProposeDesign"]:
            log.info("held back choose-template: the study isn't understood yet")
            continue
        kept.append(move)
    return tuple(kept)


def respond(
    s: Session,
    text: str,
    *,
    seq: int,
    study_id: str | None = None,
    client=None,
    history: list[dict] | None = None,
    profile: str | None = None,
) -> dict:
    """One platform turn responding to researcher ``text``.

    Returns ``{text, moves, recommendations, retrievedRefs, source}``.
    ``moves`` are ``proposed`` (the researcher accepts/rejects each).
    ``retrievedRefs`` is every corpus ref the tools returned this exchange —
    persisted on the turn so the grep-the-output grounding test can verify
    no move cites outside it (F2.1). ``source`` is ``"llm"`` or
    ``"scripted"`` (FR-CONV-1.4): with ``client`` configured, retrieval runs
    first (unconditional, deterministic) and the LLM only rephrases/selects
    against what was actually retrieved; any failure — no key, timeout,
    malformed reply — falls back to the scripted assistant (NFR-4/5).
    """
    stance = turn_stance(s, text, study_id=study_id, profile=profile)
    script = None
    source = "scripted"
    llm_recommendations: list[dict] | None = None
    if client is not None:
        papers, templates, history = _retrieve(s, text, study_id, history)
        from middleware import design_llm  # deferred: breaks the import cycle

        script = design_llm.propose_turn(
            client, text, history, papers, templates, _directive(stance)
        )
        if script is not None:
            source = "llm"
            llm_recommendations = papers
    if script is None:
        script = _pick_script(text, stance)
    return _assemble(
        s,
        text,
        script,
        source=source,
        llm_recommendations=llm_recommendations,
        seq=seq,
        study_id=study_id,
        client=client,
        stance=stance,
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
):
    """:func:`respond`, yielding the reply's prose as the model writes it.

    A generator whose ``return`` value is the identical result dict, so the
    streamed turn and the blocking turn are the same turn — the stream is a
    live view of the prose, never a second, differently-worded answer. With
    no client (or a provider without a stream seam) it yields nothing and
    returns the scripted result, exactly as :func:`respond` would.
    """
    stance = turn_stance(s, text, study_id=study_id, profile=profile)
    script = None
    source = "scripted"
    llm_recommendations: list[dict] | None = None
    if client is not None:
        papers, templates, history = _retrieve(s, text, study_id, history)
        from middleware import design_llm  # deferred: breaks the import cycle

        script = yield from design_llm.propose_turn_streaming(
            client, text, history, papers, templates, _directive(stance)
        )
        if script is not None:
            source = "llm"
            llm_recommendations = papers
    if script is None:
        script = _pick_script(text, stance)
    return _assemble(
        s,
        text,
        script,
        source=source,
        llm_recommendations=llm_recommendations,
        seq=seq,
        study_id=study_id,
        client=client,
        stance=stance,
    )


def _assemble(
    s: Session,
    text: str,
    script: Script,
    *,
    source: str,
    llm_recommendations: list[dict] | None,
    seq: int,
    study_id: str | None,
    client,
    stance: dict,
) -> dict:
    """Turn a script (LLM or scripted) into the platform turn's result dict:
    grounding resolved against retrieved rows, recommendations, and the
    design recommender's prescription/figures. The stance is applied here, so
    it holds for the scripted path and the LLM path alike."""
    retrieved: set[str] = set()

    moves = []
    for i, sm in enumerate(_permitted_moves(script.moves, stance)):
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

    if llm_recommendations is not None:
        # Reuse the same retrieval already made for the candidate menu —
        # never a second match_papers call for the same turn.
        recommendations = llm_recommendations
        retrieved.update(r["ref"] for r in recommendations)
    else:
        recommendations = []
        if script.match_query and study_id is not None:
            recommendations = matching.match_papers(
                s,
                script.match_query,
                study_id=study_id,
                limit=5,
                use_llm=client is not None,
            )
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
        "text": script.text,
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
        "source": source,
    }
