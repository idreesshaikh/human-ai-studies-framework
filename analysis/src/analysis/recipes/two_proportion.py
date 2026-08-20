"""
two-proportion — parameterised recipe for comparing binary outcomes across two
conditions (2x2 contingency table).
"""

from __future__ import annotations

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset

FIGURE_FORMS = {
    "grouped-bar": figures.grouped_bar_proportion,
}
_DEFAULT_FIGURE = "grouped-bar"
FIGURE_LABELS = {"grouped-bar": "grouped bar per condition"}


def _figure_label(form: str) -> str:
    return FIGURE_LABELS.get(form, form)


METHOD_TEMPLATE = (
    "Binary-outcome comparison across two conditions: Fisher's exact test "
    "(two-sided) on the 2x2 pass/fail contingency table with the odds "
    "ratio as effect size. Fisher's exact test is valid at any cell count "
    "and does not assume minimum expected frequencies. Per-cell n always "
    "reported. Figure: {figure}. Source: "
    "``analysis.stats.fisher_2x2``."
)


@recipe(
    id="two-proportion",
    answers=["RQ-F3", "RQ-P1", "RQ-P2", "RQ-P3", "RQ-P4"],
    requires_events=["task_outcome"],
    requires_metrics=[],
    title="Two-proportion comparison (Fisher's exact + odds ratio)",
)
def run(dataset: Dataset) -> RecipeResult:
    outcome_col = dataset.meta.get("outcome_column", "passed")
    figure_form = dataset.meta.get("figure", _DEFAULT_FIGURE)
    conds = dataset.conditions[:2] if len(dataset.conditions) >= 2 else []

    df = dataset.data if dataset.data is not None else pd.DataFrame()
    if df.empty:
        return RecipeResult(summary="No data available for proportion comparison.")

    if outcome_col not in df.columns:
        return RecipeResult(
            summary=f"Outcome column '{outcome_col}' not found in data."
        )

    rate = (
        df.groupby("condition")[outcome_col]
        .agg(n="count", passed="sum")
        .reset_index()
    )
    rate["proportion"] = rate["passed"] / rate["n"]
    tables = {"proportions": rate}
    summary_parts = []

    if len(conds) >= 2:
        cell = rate.set_index("condition")
        table = [
            [int(cell.loc[c, "passed"]), int(cell.loc[c, "n"] - cell.loc[c, "passed"])]
            for c in conds[:2]
        ]
        test = stats.fisher_2x2(
            table,
            cells={c: int(cell.loc[c, "n"]) for c in conds[:2]},
            note="rows: condition; columns: passed/failed",
        )
        tables["test"] = pd.DataFrame([test.row()])
        summary_parts.append(test.line())

        fig_fn = FIGURE_FORMS.get(figure_form)
        if fig_fn:
            fig = fig_fn(
                df, outcome_col, conds,
                title="Proportion comparison",
                ylabel="proportion",
            )
            return RecipeResult(
                tables=tables,
                figures={"comparison": fig},
                summary="\n".join(summary_parts),
                methods=METHOD_TEMPLATE.format(figure=_figure_label(figure_form)),
            )
    else:
        summary_parts.append("Single condition — proportions only.")

    summary_parts.append(
        "; ".join(f"{r.condition}: {int(r.passed)}/{int(r.n)} ({r.proportion:.0%})"
                   for r in rate.itertuples())
    )

    return RecipeResult(
        tables=tables,
        summary="\n".join(summary_parts),
        methods=METHOD_TEMPLATE.format(figure=_figure_label(figure_form)),
    )
