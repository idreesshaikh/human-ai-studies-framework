"""Shared recipe plumbing: graceful degradation to descriptives.

The pilot replays and dry runs often contain a single condition; every
comparison recipe must still produce an honest result then - descriptives
plus an explicit "no comparison possible" note - rather than crashing or
faking a test.
"""

from __future__ import annotations

import pandas as pd

from analysis import stats
from analysis.dataset import Dataset


def two_conditions(df: pd.DataFrame, dataset: Dataset) -> tuple[str, str] | None:
    """The two conditions to compare, protocol/dataset order, or None."""
    present = [c for c in dataset.conditions if (df["condition"] == c).any()]
    return (present[0], present[1]) if len(present) >= 2 else None


def describe_cells(df: pd.DataFrame, value: str) -> pd.DataFrame:
    """Per-condition descriptives: n, min, median, mean, max (always
    reported next to any test - NFR-8)."""
    vals = df.assign(_v=pd.to_numeric(df[value], errors="coerce")).dropna(subset=["_v"])
    return (
        vals.groupby("condition")["_v"]
        .agg(n="count", min="min", median="median", mean="mean", max="max")
        .reset_index()
        .rename(columns={"_v": value})
    )


def compare_or_describe(
    df: pd.DataFrame, value: str, dataset: Dataset
) -> tuple[stats.TestResult | None, pd.DataFrame, str]:
    """Standard two-condition comparison with honest degradation.

    Returns (test result or None, per-cell descriptives, summary sentence).
    """
    cells = describe_cells(df, value)
    conds = two_conditions(df, dataset)
    if conds is None:
        note = (
            "Only one condition present in the data - descriptives only, "
            "no comparison possible."
        )
        return None, cells, note
    test = stats.compare_by_condition(df, value, conds)
    return test, cells, test.line()
