import pytest
from analysis.dataset import Dataset
from analysis.recipes.mean_comparison import run
from scipy import stats


def protocol(design):
    return {
        "protocolVersion": 6,
        "conditions": ["a", "b"],
        "participants": {"design": design},
        "measures": [
            {
                "id": "time",
                "instrument": "taskHarness",
                "fields": ["task_outcome.firstGreenMs"],
                "analysisRecipe": "mean-comparison",
            }
        ],
    }


def rows(a, b, paired):
    result = []
    for c, values in [("a", a), ("b", b)]:
        for i, value in enumerate(values):
            pid = f"P{i}" if paired else f"{c}{i}"
            result.append(
                {
                    "sessionId": f"{c}-{pid}",
                    "participantId": pid,
                    "condition": c,
                    "type": "task_outcome",
                    "payload": {"firstGreenMs": value},
                }
            )
    return result


@pytest.mark.parametrize("paired", [True, False])
def test_fixed_mean_recipe_matches_the_test_the_planner_names(paired):
    a = [10, 12, 9, 14, 13, 11]
    b = [17, 14, 16, 19, 15, 20]
    design = "within-subjects" if paired else "between-subjects"
    result = run(Dataset(rows(a, b, paired), meta={"protocol": protocol(design)}))
    record = result.tables["tests"].iloc[0]
    expected = (
        stats.ttest_rel(a, b) if paired else stats.ttest_ind(a, b, equal_var=True)
    )
    assert record["p"] == pytest.approx(expected.pvalue)
    assert record["statistic"] == pytest.approx(expected.statistic)
    assert record["test"] == ("paired-t" if paired else "two-sample-t")


def test_researcher_exclusion_removes_whole_sessions_from_mean_analysis():
    events = rows([10, 12, 9], [17, 14, 16], False)
    events[0]["pilot"] = True
    events[-1]["inclusionDecision"] = "exclude"
    result = run(Dataset(events, meta={"protocol": protocol("between-subjects")}))
    assert result.tables["tests"].iloc[0]["n"] == 4
