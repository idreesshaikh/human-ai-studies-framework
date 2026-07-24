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

import difflib
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware import compiler, matching
from middleware.db import ConversationTurn, DesignMoveRow
from middleware.template_registry import list_templates

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


#: Design-intent signal shared with :func:`_pick_script`'s scripted-fallback
#: routing: a message carrying one of these words is asking about design at
#: all, even when it names none of a specific template's jargon (e.g.
#: "help me with design" matches no template's own keyword profile below).
_DESIGN_INTENT_WORDS = ("design", "statistic", "test", "how many", "template")


def recommend_templates(text: str) -> list[dict[str, Any]]:
    """Recommend design archetype templates matching the researcher's input.

    Keyword-based matching over template metadata, ranked by match strength.
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
        profile = keywords.get(
            tid,
            keywords.get(tid.replace("-v1", ""), []),
        )
        score = sum(2 for kw in profile if kw in q)
        if t.get("designType") and t["designType"].lower().replace("-", " ") in q:
            score += 3
        if t.get("title") and any(w in q for w in t["title"].lower().split()):
            score += 1
        if score > 0:
            scored.append((score, t))

    scored.sort(key=lambda x: -x[0])
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


def _followup_script(empty: list[str] | None = None) -> Script:
    """The no-move follow-up: ask for more, naming the draft's actual empty
    sections when known (``None`` = no design state, keep the generic
    wording; ``[]`` = everything is covered, say so instead of inventing
    gaps)."""
    if empty is None:
        slot_line = (
            "Right now these slots are still empty: participants, "
            "conditions, ethics posture."
        )
    elif empty:
        slot_line = f"Right now these slots are still empty: {', '.join(empty)}."
    else:
        slot_line = (
            "Every mandatory section is covered — review the draft, or tell "
            "me what to refine."
        )
    return Script(
        text=(
            "Tell me more so I can ground a move. What's the population, and "
            f"is this live-instrumented or curated data? {slot_line}"
        ),
        moves=(),
    )


def _pick_script(text: str) -> Script:
    """Deterministic input → script routing (mirrors the client stub)."""
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
    return _followup_script()


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
    """Prior platform-conversation turns as ``{"role", "content"}`` dicts,
    oldest first, capped to ``_LLM_HISTORY_TURNS`` (a token-budget cap, not
    a correctness requirement) - the shape an LLM chat-completions call
    expects. Empty when there's no study or no history yet."""
    if study_id is None:
        return []
    rows = s.execute(
        select(ConversationTurn)
        .where(ConversationTurn.study_id == study_id)
        .order_by(ConversationTurn.seq.desc())
        .limit(_LLM_HISTORY_TURNS)
    ).scalars().all()
    return [
        {
            "role": "user" if row.role == "researcher" else "assistant",
            "content": row.text,
        }
        for row in reversed(rows)
        if row.text
    ]


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
    if smaller >= _DUP_MIN_TERMS:
        if len(ta & tb) / smaller >= _DUP_TOKEN_OVERLAP:
            return True
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() >= (
        _DUP_SEQ_RATIO
    )


def _filter_repeated_moves(
    moves: tuple[ScriptedMove, ...], state: dict | None
) -> tuple[ScriptedMove, ...]:
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
        .where(DesignMoveRow.study_id == study_id)
        .order_by(DesignMoveRow.id)
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
            section = patch.get("section") or (m["target"] or "").split(".")[0]
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
    return {
        **buckets,
        "filled": filled,
        "empty": empty,
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
    script = None
    source = "scripted"
    llm_recommendations: list[dict] | None = None
    state = _load_design_state(s, study_id)
    if client is not None:
        papers = matching.match_papers(
            s, text, study_id=study_id, limit=8, use_llm=False
        )
        templates = recommend_templates(text)
        # An explicit history (the stateless demo passes the visitor's own
        # prior turns) wins; otherwise load it from the study's stored turns.
        if history is None:
            history = _load_history(s, study_id)
        from middleware import design_llm  # deferred: breaks the import cycle

        script = design_llm.propose_turn(
            client, text, history, papers, templates, design_state=state
        )
        if script is not None:
            source = "llm"
            llm_recommendations = papers
    if script is None:
        script = _pick_script(text)
    kept = _filter_repeated_moves(script.moves, state)
    if kept != script.moves:
        if not kept and source == "scripted":
            # The whole scripted reply was a repeat — steer at the actual
            # gaps instead of re-running the same script verbatim.
            script = _followup_script(state["empty"] if state else None)
        else:
            script = Script(script.text, kept, script.match_query)
    retrieved: set[str] = set()

    moves = []
    for i, sm in enumerate(script.moves):
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
    template_recommendations = recommend_templates(text)
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
        "retrievedRefs": sorted(retrieved),
        "source": source,
    }
