"""tlx-debrief (RQ-P1): end-of-session NASA-TLX-style subscales."""

from __future__ import annotations

import pandas as pd

from analysis import figures
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.figures import condition_colors, new_axes
from analysis.recipes._common import compare_or_describe

METHODS = (
    "The end survey (`end_survey_response`) records TLX-style subscales under "
    "its `responses` object (e.g. mental demand, effort, frustration), one "
    "response per session; a dismissed survey (`end_survey_skipped`) is a "
    "non-response, counted but not rated. Each "
    "subscale is compared independently across conditions with the exact "
    "two-sided Wilcoxon signed-rank on participants observed in both "
    "conditions (rank-biserial correlation), else the exact Mann-Whitney U "
    "with Cliff's delta; per-cell n reported per subscale. No omnibus or "
    "multiple-comparison correction is applied at pilot n - results are "
    "hypothesis-generating, stated as such."
)


@recipe(
    id="tlx-debrief",
    answers=["RQ-P1"],
    requires_events=["end_survey_response"],
    title="TLX debrief subscales by condition",
)
def run(dataset: Dataset) -> RecipeResult:
    surveys = dataset.of_type("end_survey_response")
    # The per-item ratings live in the nested ``responses`` object; ``comments`` and
    # ``msToComplete`` share the payload but are not ratings. Select the
    # ``responses.*`` columns explicitly rather than "any numeric column", so free-text
    # and timing never leak in as a subscale, and strip the prefix for display.
    prefix = "responses."
    subscale_cols = {
        c: c[len(prefix) :]
        for c in surveys.columns
        if c.startswith(prefix)
        and pd.to_numeric(surveys[c], errors="coerce").notna().any()
    }
    surveys = surveys.rename(columns=subscale_cols)
    subscales = list(subscale_cols.values())
    # A dismissed survey counts as a non-response, never as a rating (#67).
    n_responded = len(surveys)
    n_skipped = len(dataset.of_type("end_survey_skipped"))

    rows = []
    cells = []
    sentences = []
    for sub in subscales:
        df = surveys[["participantId", "condition", sub]].copy()
        df[sub] = pd.to_numeric(df[sub], errors="coerce")
        # Condition-specific items have no ratings in the other arm.
        # Compare observed cells rather than testing against an empty sample.
        df = df.dropna(subset=[sub])
        test, desc, sentence = compare_or_describe(df, sub, dataset)
        cells.append(desc.assign(subscale=sub))
        sentences.append(f"{sub}: {sentence}")
        if test:
            rows.append({"subscale": sub, **test.row()})

    colors = condition_colors(dataset.conditions)
    fig, ax = new_axes(
        "TLX debrief subscales by condition",
        "subscale",
        "rating",
        figsize=(7.2, 4.2),
    )
    import numpy as np

    rng = np.random.default_rng(0)
    width = 0.36
    for i, sub in enumerate(subscales):
        for j, cond in enumerate(dataset.conditions):
            vals = pd.to_numeric(
                surveys.loc[surveys["condition"] == cond, sub], errors="coerce"
            ).dropna()
            x = i + (j - (len(dataset.conditions) - 1) / 2) * width
            ax.scatter(
                x + rng.uniform(-0.05, 0.05, len(vals)),
                vals,
                s=28,
                color=colors[cond],
                edgecolors=figures.SURFACE,
                linewidths=1.2,
                zorder=3,
                label=cond if i == 0 else None,
            )
    ax.set_xticks(range(len(subscales)))
    ax.set_xticklabels(subscales, fontsize=8)
    ax.legend(fontsize=8, frameon=False, labelcolor=figures.SECONDARY)
    lo, hi = ax.get_ylim()
    ax.set_ylim(min(0, lo), hi)
    fig.tight_layout()

    tables: dict[str, pd.DataFrame] = {
        "per_condition": pd.concat(cells, ignore_index=True)
        if cells
        else pd.DataFrame(),
        "responses": surveys,
    }
    if rows:
        tables["tests"] = pd.DataFrame(rows)

    return RecipeResult(
        tables=tables,
        figures={"subscales": fig},
        summary=(
            f"TLX debrief (RQ-P1); {n_responded} responded, {n_skipped} skipped. "
            + " ".join(sentences)
        ),
        methods=METHODS,
    )
