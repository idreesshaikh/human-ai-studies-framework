import copy
import json
from pathlib import Path

import pytest
from middleware.evaluation import (
    Benchmark,
    Case,
    Prediction,
    reviewer_agreement,
    rules_predictions,
    score,
)
from middleware.evidence_mapping import EvidenceContext, digest


@pytest.fixture
def evidence():
    return json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "protocol/examples/evidence-workflow-demo.json"
        ).read_text()
    )


@pytest.fixture
def benchmark(evidence):
    return Benchmark(
        version="fixture-1",
        map_digest=digest(evidence),
        label_provenance="synthetic",
        reviewers=[],
        review_notes="Synthetic only",
        cases=[
            Case(
                id="fixture",
                scenario_family="debugging",
                split="test",
                study_ids=["synthetic-between"],
                context=EvidenceContext(
                    producers=["task-harness"], instruments=["task-harness"]
                ),
                expected={"synthetic-between": "insufficient-evidence"},
            )
        ],
    )


def test_synthetic_labels_never_become_research_by_default(benchmark, evidence):
    with pytest.raises(ValueError, match="human-adjudicated"):
        benchmark.verify(evidence)
    benchmark.verify(evidence, allow_synthetic=True)
    benchmark.label_provenance = "human-adjudicated"
    with pytest.raises(ValueError, match="two independent"):
        benchmark.verify(evidence)


def test_evidence_and_benchmark_digests_are_frozen(benchmark, evidence):
    before = benchmark.digest()
    assert before == benchmark.digest()
    benchmark.cases[0].context.population = "Changed"
    assert benchmark.digest() != before
    evidence["description"] = "Changed"
    with pytest.raises(ValueError, match="snapshot digest"):
        benchmark.verify(evidence, allow_synthetic=True)


@pytest.mark.parametrize("related", [False, True])
def test_reports_and_paraphrases_cannot_cross_splits(benchmark, evidence, related):
    case = copy.deepcopy(benchmark.cases[0])
    case.id = "paraphrase"
    case.split = "train"
    if related:
        case.scenario_family = "renamed scenario"
        case.study_ids = ["synthetic-within"]
        case.expected = {"synthetic-within": "conditional"}
    benchmark.cases.append(case)
    with pytest.raises(ValueError, match="Split leakage"):
        benchmark.verify(evidence, allow_synthetic=True)


def test_abstention_and_unknown_cost_not_scored_as_success(benchmark):
    row = Prediction(
        case_id="fixture",
        candidate_id="synthetic-between",
        status=None,
        latency_ms=12,
        error="timeout",
    )
    result = score(benchmark, [row])
    assert result["automatedCoverage"] == 0
    assert result["errorAmongAutomated"] is None
    assert result["providerFailures"] == 1
    assert result["costUsd"] is None
    with pytest.raises(ValueError, match="exactly once"):
        score(benchmark, [])
    with pytest.raises(ValueError, match="exactly once"):
        score(benchmark, [row, row])


def test_unsafe_recommendations_are_distinct_from_abstention(benchmark):
    row = Prediction(
        case_id="fixture",
        candidate_id="synthetic-between",
        status="compatible",
        confidence=0.9,
        latency_ms=5,
        cost_usd=0.01,
    )
    result = score(benchmark, [row])
    assert result["unsupportedRecommendations"] == 1
    assert result["brierCorrectness"] == pytest.approx(0.81)
    assert result["costUsd"] == 0.01


def test_rules_use_the_same_frozen_cases(benchmark, evidence):
    rows = rules_predictions(benchmark, evidence)
    assert len(rows) == 1
    assert score(benchmark, rows)["errorAmongAutomated"] == 0


def test_actual_reviewer_agreement_and_degenerate_kappa():
    assert (
        reviewer_agreement({"a": "compatible"}, {"a": "compatible"})["cohenKappa"]
        is None
    )
    result = reviewer_agreement(
        {
            "a": "compatible",
            "b": "compatible",
            "c": "incompatible",
            "d": "incompatible",
        },
        {
            "a": "compatible",
            "b": "incompatible",
            "c": "compatible",
            "d": "incompatible",
        },
    )
    assert result["agreement"] == 0.5
    assert result["cohenKappa"] == 0
    assert result["disagreements"] == ["b", "c"]
    with pytest.raises(ValueError):
        reviewer_agreement({"a": "compatible"}, {"b": "compatible"})


def test_staged_adapter_does_not_receive_reference_labels(benchmark, evidence):
    from middleware.evaluation import model_predictions

    calls = []

    def request(prompt):
        calls.append(prompt)
        assert '"expected"' not in prompt
        return {"decisions": [{"candidate_id": "synthetic-between", "status": None}]}

    rows = model_predictions(benchmark, evidence, request, stages=2)
    assert len(calls) == 2
    assert rows[0].status is None
    assert rows[0].cost_usd is None
    assert score(benchmark, rows)["automatedCoverage"] == 0


def test_invalid_model_outputs_abstain_not_silently_succeed(benchmark, evidence):
    from middleware.evaluation import model_predictions

    rows = model_predictions(benchmark, evidence, lambda _prompt: {"decisions": []})
    assert rows[0].status is None
    assert rows[0].error == "ValueError"
    assert score(benchmark, rows)["providerFailures"] == 1
