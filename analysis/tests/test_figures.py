"""Plots must preserve observation identity when values are incomplete."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from analysis.figures import scatter_fit


def test_scatter_uses_complete_rows_without_repairing_missing_pairs():
    frame = pd.DataFrame(
        {"x": [1, None, "3", 4, np.inf], "y": [None, 20, 30, 40, 50]},
        index=["a", "b", "c", "d", "e"],
    )
    fig = scatter_fit(frame, "x", "y", "participants", "Synthetic observations")
    try:
        ax = fig.axes[0]
        np.testing.assert_array_equal(
            ax.collections[0].get_offsets(), [[3, 30], [4, 40]]
        )
        np.testing.assert_allclose(ax.lines[0].get_ydata(), [30, 40])
        assert "n = 2 participants" in [text.get_text() for text in ax.texts]
    finally:
        plt.close(fig)


@pytest.mark.parametrize(
    ("x", "y", "expected_count"),
    [
        ([1, None], [None, 2], 0),
        ([1, 2, 3], ["missing", 20, -np.inf], 1),
        ([1, 2, 3], [np.inf, np.nan, -np.inf], 0),
    ],
)
def test_scatter_with_too_few_complete_observations_does_not_fit(x, y, expected_count):
    fig = scatter_fit(pd.DataFrame({"x": x, "y": y}), "x", "y", "rows", "Sparse")
    try:
        ax = fig.axes[0]
        assert not ax.lines
        assert sum(len(c.get_offsets()) for c in ax.collections) == expected_count
        assert "too few points for a fit" in [text.get_text() for text in ax.texts]
        assert f"n = {expected_count} rows" in [text.get_text() for text in ax.texts]
    finally:
        plt.close(fig)


def test_scatter_with_constant_predictor_keeps_points_without_an_undefined_fit():
    fig = scatter_fit(
        pd.DataFrame({"x": [0, 0, 0], "y": [10, 20, 30]}),
        "x",
        "y",
        "participants",
        "Constant predictor",
    )
    try:
        ax = fig.axes[0]
        np.testing.assert_array_equal(
            ax.collections[0].get_offsets(), [[0, 10], [0, 20], [0, 30]]
        )
        assert not ax.lines
        assert "constant x; no fit" in [text.get_text() for text in ax.texts]
    finally:
        plt.close(fig)
