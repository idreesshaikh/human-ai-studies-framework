"""Contract + honest-stats tests (FR-ANA-1/2, NFR-8)."""

import analysis.recipes  # noqa: F401 - populate the registry
import pytest
from analysis.core import REGISTRY, Requires, recipe, validate_plan
from analysis.dataset import Dataset

from analysis import stats


def event(
    seq,
    type_,
    payload,
    session="S1",
    participant="P01",
    condition="ai-assisted",
    minute=0.0,
):
    h, m = divmod(int(minute), 60)
    sec = round((minute % 1) * 60, 3)
    return {
        "source": "cognitive-overlay",
        "ts": f"2026-07-11T{10 + h:02d}:{m:02d}:{sec:06.3f}Z",
        "sessionId": session,
        "participantId": participant,
        "condition": condition,
        "type": type_,
        "seq": seq,
        "flags": [],
        "payload": payload,
    }


def metric_row(payload, session="S1", participant="P01", condition="ai-assisted"):
    return {
        "source": "metrics",
        "ts": "2026-07-11T11:00:00+00:00",
        "sessionId": session,
        "participantId": participant,
        "condition": condition,
        "type": "function_metrics",
        "seq": None,
        "flags": [],
        "payload": payload,
    }


# ------------------------------------------------------------- the contract


def test_every_builtin_recipe_declares_the_full_contract():
    assert len(REGISTRY) >= 9
    for rec in REGISTRY.values():
        assert rec.id and rec.id == rec.id.lower()
        assert rec.answers, f"{rec.id} answers no RQ"
        assert all(a.startswith("RQ-") for a in rec.answers)
        assert rec.requires.events or rec.requires.metrics, (
            f"{rec.id} declares no data requirements"
        )
        assert callable(rec.run)


def test_duplicate_recipe_ids_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        recipe(id="fatigue-by-condition", answers=["RQ-P1"])(lambda d: None)


def test_requires_missing_names_the_missing_element():
    ds = Dataset(rows=[event(0, "fatigue_response", {"score": 3})])
    req = Requires(
        events=frozenset({"task_outcome"}),
        metrics=frozenset({"nesting_penalty"}),
    )
    missing = req.missing(ds)
    assert "event type 'task_outcome'" in missing
    assert "metric column 'nesting_penalty'" in missing


def test_validate_plan_fails_loudly_naming_missing_event_type():
    ds = Dataset(rows=[event(0, "fatigue_response", {"score": 3})])
    plan = [
        {"rq": "RQ-P1", "recipes": ["fatigue-by-condition"]},
        {"rq": "RQ-P5", "recipes": ["task-outcome-by-condition", "nonexistent"]},
    ]
    checks = {c.recipe_id: c for c in validate_plan(plan, ds)}
    assert checks["fatigue-by-condition"].ok
    failed = checks["task-outcome-by-condition"]
    assert not failed.ok
    assert "event type 'task_outcome'" in failed.describe()
    assert not checks["nonexistent"].known
    assert "UNKNOWN RECIPE" in checks["nonexistent"].describe()


# ------------------------------------------------------------- honest stats


def test_cliffs_delta_known_answers():
    assert stats.cliffs_delta([5, 6], [1, 2]) == 1.0
    assert stats.cliffs_delta([1, 2], [5, 6]) == -1.0
    assert stats.cliffs_delta([1, 2], [1, 2]) == 0.0


def test_wilcoxon_paired_known_answer_and_honest_line():
    # 4 pairs, all differences negative: exact two-sided p = 2/16 = 0.125,
    # rank-biserial r = -1.
    res = stats.wilcoxon_paired([2, 2, 2, 2], [4, 5, 3, 6], labels=("a", "b"))
    assert res.p == pytest.approx(0.125)
    assert res.effect == pytest.approx(-1.0)
    line = res.line()
    assert "exact p=0.125" in line
    assert "rank-biserial r=-1.00" in line
    assert "a n=4, b n=4" in line
    assert "hypothesis-generating" in line  # NFR-8: small n framed as such


def test_mann_whitney_reports_effect_size_and_cells():
    res = stats.mann_whitney([5, 6, 7], [1, 2, 3], labels=("x", "y"))
    assert res.effect == 1.0
    assert res.n == {"x": 3, "y": 3}
    assert "Cliff's delta" in res.line()


def test_compare_by_condition_pairs_within_subjects():
    import pandas as pd

    df = pd.DataFrame(
        [
            {"participantId": f"P{i:02d}", "condition": cond, "v": v}
            for i, (a, b) in enumerate([(2, 4), (3, 5), (1, 4), (2, 3)], start=1)
            for cond, v in [("ai-assisted", a), ("unassisted", b)]
        ]
    )
    res = stats.compare_by_condition(df, "v", ("ai-assisted", "unassisted"))
    assert res.test.startswith("Wilcoxon signed-rank")
    assert "paired on 4 participant(s)" in res.note
    assert res.effect == pytest.approx(-1.0)


# ------------------------------------------------------------------ dataset


def test_dataset_separates_legs_and_discovers_requirements():
    ds = Dataset(
        rows=[
            event(0, "fatigue_response", {"score": 2}),
            metric_row({"file": "a.py", "function": "f", "nesting_penalty": 4}),
        ]
    )
    assert ds.event_types == {"fatigue_response"}
    assert "nesting_penalty" in ds.metric_columns
    assert "file" not in ds.metric_columns  # identifiers are not metrics
    assert ds.conditions == ["ai-assisted"]
    assert len(ds.session_spans) == 1
