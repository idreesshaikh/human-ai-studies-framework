"""The design assistant (MP-15 slice 4; FR-CONV-1/2).

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

from dataclasses import dataclass

from sqlalchemy.orm import Session

from middleware import matching


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
    "Tell me what you want to find out. I'll ask the questions a "
    "methodologist would, propose design moves grounded in the corpus, and "
    "compile the ones you accept into a protocol draft. Try: “I think "
    "junior developers over-trust AI-generated code.”"
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
                    "value": "Review latency (suggestion-visible-to-decision "
                    "time)",
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
                    "value": "Code-correctness outcome (acceptance-test pass "
                    "rate)",
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


_FOLLOWUP = Script(
    text=(
        "Tell me more so I can ground a move. What's the population, and is "
        "this live-instrumented or curated data? Right now these slots are "
        "still empty: participants, conditions, ethics posture."
    ),
    moves=(),
)


def _pick_script(text: str) -> Script:
    """Deterministic input → script routing (mirrors the client stub)."""
    q = text.lower()
    if any(w in q for w in ("trust", "over-trust", "junior")):
        return _over_trust_script()
    if any(w in q for w in ("productiv", "faster", "speed")) and any(
        w in q for w in ("self-report", "survey", "ask", "perceiv")
    ):
        return _self_report_script()
    if any(w in q for w in ("design", "statistic", "test", "how many", "template")):
        return _design_script()
    if any(w in q for w in ("benchmark", "humaneval", "pass@")):
        return _benchmark_script()
    return _FOLLOWUP


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
                "tier": meta["tier"],
                "title": meta["title"],
                "year": meta.get("year"),
                "venue": meta.get("venue", ""),
                "why": meta.get("why", ""),
            }
        )
    return grounding


def respond(
    s: Session,
    text: str,
    *,
    seq: int,
    study_id: str | None = None,
    client=None,
) -> dict:
    """One platform turn responding to researcher ``text``.

    Returns ``{text, moves, recommendations, retrievedRefs}``. ``moves`` are
    ``proposed`` (the researcher accepts/rejects each). ``retrievedRefs`` is
    every corpus ref the tools returned this exchange — persisted on the turn
    so the grep-the-output grounding test can verify no move cites outside it
    (F2.1). ``client`` is the optional LLM provider seam; unused by the
    deterministic path.
    """
    script = _pick_script(text)
    retrieved: set[str] = set()

    moves = []
    for i, sm in enumerate(script.moves):
        grounding = _resolve_grounding(s, sm.refs)
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

    return {
        "text": script.text,
        "moves": moves,
        "recommendations": recommendations,
        "retrievedRefs": sorted(retrieved),
    }