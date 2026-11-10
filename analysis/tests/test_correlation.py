"""Association estimates and plots use the same complete observation pairs."""

import matplotlib.pyplot as plt
import numpy as np
import pytest
from analysis.dataset import Dataset
from analysis.recipes.correlation import run


def _dataset(pairs):
    return Dataset(
        rows=[
            {
                "source": "task-harness",
                "ts": "2026-11-10T10:00:00Z",
                "sessionId": f"session-{i}",
                "participantId": f"P{i}",
                "condition": "control",
                "type": "task_outcome",
                "seq": 0,
                "flags": [],
                "payload": {"x": x, "y": y},
            }
            for i, (x, y) in enumerate(pairs)
        ]
    )


def test_correlation_never_pairs_values_from_different_observations():
    result = run(_dataset([(100, None), (None, 100), (1, 30), (2, 20), (3, 10)]))
    try:
        row = result.tables["test"].iloc[0]
        assert row["n_variables"] == 3
        assert row["effect"] == pytest.approx(-1)
        offsets = result.figures["comparison"].axes[0].collections[0].get_offsets()
        np.testing.assert_array_equal(offsets, [[1, 30], [2, 20], [3, 10]])
        assert "independent observations" in result.methods
    finally:
        for fig in result.figures.values():
            plt.close(fig)


def test_correlation_excludes_nonfinite_pairs_before_statistics_and_plotting():
    result = run(_dataset([(1, 10), (2, 20), (3, 30), (np.inf, 40), (4, -np.inf)]))
    try:
        row = result.tables["test"].iloc[0]
        assert row["n_variables"] == 3
        assert row["effect"] == pytest.approx(1)
        assert np.isfinite(row["statistic"])
    finally:
        for fig in result.figures.values():
            plt.close(fig)


def test_correlation_refuses_when_no_observation_has_both_values():
    result = run(_dataset([(1, None), (None, 2), (3, None), (None, 4)]))
    assert result.tables == {} and result.figures == {}
    assert "Too few observations" in result.summary
