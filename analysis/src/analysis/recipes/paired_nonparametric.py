"""paired-nonparametric — parameterised recipe for paired/within-subjects
comparison designs.

Can be parameterised via the recipe's ``params`` dict:
- ``figure``: "paired-dots" (default) or "strip"

FR-ANA-8: single code path for all paired comparisons.
"""

from __future__ import annotations

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.recipes._common import describe_cells

FIGURE_FORMS = {
    "paired-dots": figures.paired_dots,
    "strip": figures.strip_by_condition,
}
_DEFAULT_FIGURE = "paired-dots"
FIGURE_LABELS = {
    "paired-dots": "paired dots per participant",
    "strip": "strip plot per condition",
}


def _pick_figure(form: str):
    return FIGURE_FORMS.get(form, FIGURE_FORMS[_DEFAULT_FIGURE])


def _figure_label(form: str) -> str:
    return FIGURE_LABELS.get(form, form)


METHOD_TEMPLATE = (
    "Paired (within-subjects) nonparametric comparison: exact Wilcoxon "
    "signed-rank test with matched-pairs rank-biserial correlation as "
    "effect size. Zero differences excluded following Siegel & Castellan. "
    "Per-participant means computed before pairing. Descriptives: n, "
    "median, min, max per condition. Figure: {figure}. Source: "
    "``analysis.stats.wilcoxon_paired``."
)


@recipe(
    id="paired-nonparametric",
    answers=["RQ-F3", "RQ-P1", "RQ-P2", "RQ-P3", "RQ-P4"],
    requires_events=["task_outcome"],
    requires_metrics=[],
    title="Paired nonparametric comparison (Wilcoxon + rank-biserial r)",
)
def run(dataset: Dataset) -> RecipeResult:
    value = dataset.meta.get("value_column", "value")
    figure_form = dataset.meta.get("figure", _DEFAULT_FIGURE)
    conds = dataset.conditions[:2] if len(dataset.conditions) >= 2 else []

    df = dataset.data if dataset.data is not None else pd.DataFrame()
    if df.empty:
        return RecipeResult(summary="No data available for paired comparison.")

    cells = describe_cells(df, value)
    tables = {"descriptives": cells}

    if len(conds) >= 2:
        per = df.groupby(["participantId", "condition"])[value].mean().reset_index()
        wide = per.pivot(index="participantId", columns="condition", values=value)
        for c in conds:
            if c not in wide.columns:
                wide[c] = float("nan")
        paired = wide.dropna(subset=list(conds))
        if len(paired) >= 2:
            a = paired[conds[0]].tolist()
            b = paired[conds[1]].tolist()
            test = stats.wilcoxon_paired(a, b, labels=(conds[0], conds[1]))
            tables["test"] = pd.DataFrame([test.row()])
            summary = test.line()
            fig_fn = _pick_figure(figure_form)
            if figure_form == "paired-dots":
                fig_wide = wide.dropna(subset=list(conds))
                fig = figures.paired_dots(
                    fig_wide, (conds[0], conds[1]),
                    title="Paired comparison",
                    ylabel=value,
                )
            else:
                fig = fig_fn(
                    df, value, conds,
                    title="Paired comparison",
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
        summary=f"Paired comparison not possible — descriptives only.\n{summary}",
        methods=METHOD_TEMPLATE.format(figure=_figure_label(figure_form)),
    )
