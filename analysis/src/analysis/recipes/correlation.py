"""correlation — parameterised recipe for assessing monotonic association
between two variables.

Can be parameterised via the recipe's ``params`` dict:
- ``figure``: "scatter" (default) or omit

FR-ANA-8: single code path for all correlation analyses.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset

FIGURE_FORMS = {
    "scatter": figures.scatter_fit,
}
_DEFAULT_FIGURE = "scatter"
FIGURE_LABELS = {"scatter": "scatter with OLS fit"}


def _figure_label(form: str) -> str:
    return FIGURE_LABELS.get(form, form)


METHOD_TEMPLATE = (
    "Monotonic association assessed via Spearman's rank correlation "
    "coefficient (\u03c1). Spearman's \u03c1 is identical to Pearson's correlation "
    "on the ranks, making it robust to outliers and distributional "
    "assumptions. The test statistic and effect size are the same value. "
    "Per-variable n always reported. Figure: {figure}. Source: "
    "``analysis.stats.spearman``."
)


@recipe(
    id="correlation",
    answers=["RQ-F3", "RQ-P1", "RQ-P2", "RQ-P3", "RQ-P4"],
    requires_events=["task_outcome"],
    requires_metrics=[],
    title="Correlation (Spearman's \u03c1)",
)
def run(dataset: Dataset) -> RecipeResult:
    x_col = dataset.meta.get("x_column", "x")
    y_col = dataset.meta.get("y_column", "y")
    figure_form = dataset.meta.get("figure", _DEFAULT_FIGURE)
    label = dataset.meta.get("label", "variables")

    df = dataset.data if dataset.data is not None else pd.DataFrame()
    if df.empty:
        return RecipeResult(summary="No data available for correlation analysis.")

    if x_col not in df.columns or y_col not in df.columns:
        return RecipeResult(
            summary=f"Required columns '{x_col}' and/or '{y_col}' not found in data."
        )

    x = pd.to_numeric(df[x_col], errors="coerce").dropna().tolist()
    y = pd.to_numeric(df[y_col], errors="coerce").dropna().tolist()
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]

    if n < 2:
        return RecipeResult(summary="Too few observations for correlation analysis.")

    test = stats.spearman(x, y, label)
    tables = {"test": pd.DataFrame([test.row()])}
    summary = test.line()

    fig_fn = FIGURE_FORMS.get(figure_form)
    fig = None
    if fig_fn:
        fig = fig_fn(
            pd.DataFrame({x_col: x, y_col: y}),
            x_col, y_col, label,
            title="Correlation",
            xlabel=x_col, ylabel=y_col,
        )

    return RecipeResult(
        tables=tables,
        figures={"comparison": fig} if fig else {},
        summary=summary,
        methods=METHOD_TEMPLATE.format(figure=_figure_label(figure_form)),
    )
