"""
End-to-end runner test on a synthetic dataset with known answers (FR-ANA-3): recipes
produce the constructed effect, the report is organized by RQ, and a recipe with missing
data fails at validation naming the missing event type.
"""

import analysis.recipes  # noqa: F401
import pytest
from analysis.dataset import Dataset
from analysis.runner import run_plan
from tests_support import synthetic_rows

PROTOCOL = {
    "study": {"id": "synthetic-study"},
    "researchQuestions": [
        {"id": "RQ-P1", "text": "Does AI assistance change cognitive load?"},
        {"id": "RQ-P4", "text": "How is AI output reviewed?"},
        {"id": "RQ-P5", "text": "How does the agent conversation unfold?"},
    ],
    "analysisPlan": [
        {"rq": "RQ-P1", "recipes": ["fatigue-by-condition", "tlx-debrief"]},
        {"rq": "RQ-P4", "recipes": ["ai-review-behavior", "ziegler-acceptance-rate"]},
        {"rq": "RQ-P5", "recipes": ["agent-interaction-dynamics"]},
    ],
}


@pytest.fixture()
def dataset() -> Dataset:
    return Dataset(rows=synthetic_rows(), study_id="synthetic-study")


def test_run_plan_end_to_end(tmp_path, dataset):
    outcome = run_plan(PROTOCOL, dataset, "synthetic-study", out_root=tmp_path)

    assert set(outcome.executed) == {
        "fatigue-by-condition",
        "tlx-debrief",
        "ai-review-behavior",
        "ziegler-acceptance-rate",
    }
    assert not outcome.errors
    (failed,) = outcome.failed_validation
    assert failed.recipe_id == "agent-interaction-dynamics"
    assert "event type 'agent_turn'" in failed.describe()

    fdir = tmp_path / "synthetic-study" / "fatigue-by-condition"
    assert (fdir / "per_condition.csv").exists()
    assert (fdir / "by_condition.png").exists()
    assert (fdir / "by_condition.svg").exists()
    summary = (fdir / "summary.md").read_text()
    assert "Wilcoxon" in summary
    assert "hypothesis-generating" in summary

    report = (tmp_path / "synthetic-study" / "report.md").read_text()
    assert "## RQ-P1" in report
    assert "### `fatigue-by-condition` (answers RQ-P1)" in report
    assert "### `ziegler-acceptance-rate` (answers RQ-P4)" in report
    assert "Plan validation failures" in report
    assert "event type 'agent_turn'" in report
    assert "**Not run**" in report


def test_fatigue_recipe_recovers_the_constructed_effect(dataset):
    from analysis.core import REGISTRY

    result = REGISTRY["fatigue-by-condition"].run(dataset)
    test_table = result.tables["test"]
    assert test_table.iloc[0]["effect"] == pytest.approx(-1.0)
    assert test_table.iloc[0]["p_exact"] == pytest.approx(0.125)
    assert "hypothesis-generating" in result.summary


def test_ai_review_recipe_compares_latency_by_outcome(dataset):
    from analysis.core import REGISTRY

    result = REGISTRY["ai-review-behavior"].run(dataset)
    t = result.tables["latency_test"].iloc[0]
    assert t["effect"] == pytest.approx(-1.0)
    assert t["n_accepted"] == 4
    assert t["n_not-accepted"] == 4
    assert "schema v3" in result.summary


def test_task_outcome_recipe_on_constructed_verdicts():
    from analysis.core import REGISTRY
    from tests_support import synthetic_rows

    rows = synthetic_rows()
    for session, participant, condition in sorted(
        {(r["sessionId"], r["participantId"], r["condition"]) for r in rows}
    ):
        rows.append(
            {
                "source": "tern",
                "ts": "2026-07-11T11:05:00.000Z",
                "sessionId": session,
                "participantId": participant,
                "condition": condition,
                "type": "task_outcome",
                "seq": 999,
                "flags": [],
                "payload": {
                    "passed": condition == "ai-assisted",
                    "firstGreenMs": 1_800_000,
                },
            }
        )
    result = REGISTRY["task-outcome-by-condition"].run(Dataset(rows=rows))
    rates = result.tables["pass_rates"].set_index("condition")
    assert rates.loc["ai-assisted", "passRate"] == 1.0
    assert rates.loc["unassisted", "passRate"] == 0.0
    assert "Fisher" in result.tables["pass_rate_test"].iloc[0]["test"]
    assert "fatigue_by_outcome" in result.tables


def test_ziegler_recipe_computes_known_acceptance_rate(dataset):
    from analysis.core import REGISTRY

    result = REGISTRY["ziegler-acceptance-rate"].run(dataset)
    per_session = result.tables["per_session"]
    assert (per_session["acceptanceRate"] == 0.5).all()
    assert "Ziegler" in result.methods
    assert "2205.06537" in result.methods
