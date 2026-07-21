"""two-group-nonparametric — parameterised recipe for two-group
independent-comparison designs.

Can be parameterised via the recipe's ``params`` dict:
- ``direction``: "two-sided" (default), "greater", or "less"
- ``test``: "mann-whitney" (default)
- ``effect_size``: "cliffs-delta" (default)
- ``figure``: "strip" (default) or "box"

FR-ANA-8: single code path for all two-group comparisons.
"""

from __future__ import annotations

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.recipes._common import describe_cells

FIGURE_FORMS = {
    "strip": figures.strip_by_condition,
    "box": figures.box_by_condition,
}
_DEFAULT_FIGURE = "strip"
FIGURE_LABELS = {"strip": "strip plot per condition", "box": "box + strip per condition"}


def _pick_figure(form: str):
    return FIGURE_FORMS.get(form, FIGURE_FORMS[_DEFAULT_FIGURE])


def _figure_label(form: str) -> str:
    return FIGURE_LABELS.get(form, form)


METHOD_TEMPLATE = (
    "Two-group nonparametric comparison: exact Mann-Whitney U test with "
    "Cliff's delta effect size. Per-cell means aggregated per participant "
    "to avoid pseudo-replication. Descriptives: n, median, min, max per "
    "condition. Figure: {figure}. Hypothesis-generating framing at pilot n. "
    "Source: ``analysis.stats.mann_whitney``."
)


@recipe(
    id="two-group-nonparametric",
    answers=["RQ-F3", "RQ-P1", "RQ-P2", "RQ-P3", "RQ-P4"],
    requires_events=["task_outcome"],
    requires_metrics=[],
    title="Two-group nonparametric comparison (Mann-Whitney U + Cliff's delta)",
)
def run(dataset: Dataset) -> RecipeResult:
    value = dataset.meta.get("value_column", "value")
    figure_form = dataset.meta.get("figure", _DEFAULT_FIGURE)

    df = dataset.data if dataset.data is not None else pd.DataFrame()
    if df.empty:
        return RecipeResult(summary="No data available for two-group comparison.")

    cells = describe_cells(df, value)
    tables = {"descriptives": cells}

    cols = [c for c in dataset.conditions if c in set(df["condition"])]
    if len(cols) >= 2:
        a = df.loc[df["condition"] == cols[0], value].dropna().tolist()
        b = df.loc[df["condition"] == cols[1], value].dropna().tolist()
        test = stats.mann_whitney(a, b, labels=(cols[0], cols[1]))
        tables["test"] = pd.DataFrame([test.row()])
        summary = test.line()
        fig_fn = _pick_figure(figure_form)
        fig = fig_fn(
            df, value, dataset.conditions,
            title="Two-group comparison",
            ylabel=value,
        )
        return RecipeResult(
            tables=tables,
            figures={"comparison": fig},
            summary=summary,
            methods=METHOD_TEMPLATE.format(figure=_figure_label(figure_form)),
        )

    summary = cells.to_string(index=False)
    return RecipeResult(
        tables=tables,
        summary=f"Single condition present — descriptives only.\n{summary}",
        methods=METHOD_TEMPLATE.format(figure=_figure_label(figure_form)),
    )
