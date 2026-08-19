"""code-quality-by-condition (RQ-P2): the 9-metric matrix by condition.

Test choice: static-metric distributions are skewed and per-function /
per-file measurements within one workspace are not independent, so every
metric is compared with the **exact Mann-Whitney U** at measurement level
and reported *primarily through its effect size* - **Cliff's delta** - as
honest statistics demand ("effect sizes, not just p-values"). p-values are
still shown (exact, two-sided) but the table is sorted by |delta|; the
independence caveat is explicit in the methods text.
"""

from __future__ import annotations

import pandas as pd

from analysis import figures, stats
from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.figures import condition_colors
from analysis.recipes._common import two_conditions

#: The 9-metric cognitive-load matrix (metrics/docs/static_code_metrics.md);
#: whichever columns the dataset actually carries are analyzed.
MATRIX = [
    "nesting_penalty",
    "cognitive_complexity",
    "parameter_count",
    "halstead_effort",
    "mean_scope_distance",
    "max_scope_distance",
    "avg_identifier_length",
    "indentation_variance",
    "mean_line_width",
    "max_line_width",
    "comment_ratio",
]

METHODS = (
    "Static metrics are the 9-metric cognitive-load matrix computed over "
    "workspace snapshots (function- and file-level rows). For each metric "
    "present in the dataset, conditions are compared with the exact "
    "two-sided Mann-Whitney U at measurement level, and the primary "
    "reported quantity is Cliff's delta with per-cell n (NFR-8). Caveat "
    "stated with the results: measurements within one participant's "
    "workspace are not independent, so measurement-level p-values are "
    "optimistic; at pilot scale everything is hypothesis-generating."
)


@recipe(
    id="code-quality-by-condition",
    answers=["RQ-P2"],
    requires_metrics=["nesting_penalty"],
    title="Static code metrics by condition (effect sizes first)",
)
def run(dataset: Dataset) -> RecipeResult:
    metrics = dataset.metrics
    available = [m for m in MATRIX if m in dataset.metric_columns]
    conds = two_conditions(metrics, dataset)

    rows = []
    cells_frames = []
    for metric in available:
        vals = metrics[["condition", metric]].copy()
        vals[metric] = pd.to_numeric(vals[metric], errors="coerce")
        vals = vals.dropna(subset=[metric])
        desc = (
            vals.groupby("condition")[metric]
            .agg(n="count", median="median", mean="mean")
            .reset_index()
            .assign(metric=metric)
        )
        cells_frames.append(desc)
        if conds:
            a = vals.loc[vals["condition"] == conds[0], metric].tolist()
            b = vals.loc[vals["condition"] == conds[1], metric].tolist()
            if a and b:
                t = stats.mann_whitney(a, b, labels=conds)
                rows.append({"metric": metric, **t.row()})

    tables: dict[str, pd.DataFrame] = {
        "per_condition_descriptives": pd.concat(cells_frames, ignore_index=True)
    }
    if rows:
        effects = pd.DataFrame(rows).sort_values(
            "effect", key=lambda s: s.abs(), ascending=False
        )
        tables["effects"] = effects
        top = effects.iloc[0]
        sentence = (
            f"Largest effect: {top['metric']} (Cliff's delta "
            f"{top['effect']:+.2f}, exact p={top['p_exact']:.3f}, "
            f"n {conds[0]}={top[f'n_{conds[0]}']:g} / "
            f"{conds[1]}={top[f'n_{conds[1]}']:g}). Measurement-level "
            "comparison - see methods caveat. Small n: hypothesis-generating."
        )
    else:
        sentence = (
            "Only one condition present in the metric rows - descriptives "
            "only, no comparison possible."
        )

    # Small-multiples: one panel per available metric, every point drawn.
    colors = condition_colors(dataset.conditions)
    ncols = min(3, len(available))
    nrows = -(-len(available) // ncols)
    import numpy as np

    fig, axes = figures.plt.subplots(
        nrows, ncols, figsize=(3.4 * ncols, 2.8 * nrows), dpi=150
    )
    fig.patch.set_facecolor(figures.SURFACE)
    rng = np.random.default_rng(0)
    axes_flat = list(axes.flat) if nrows * ncols > 1 else [axes]
    for ax in axes_flat[len(available) :]:
        ax.set_visible(False)
    for ax, metric in zip(axes_flat, available, strict=False):
        ax.set_facecolor(figures.SURFACE)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.grid(axis="y", color=figures.GRID, linewidth=0.7)
        ax.set_axisbelow(True)
        ax.tick_params(colors=figures.MUTED, labelsize=7)
        for i, cond in enumerate(dataset.conditions):
            vals = pd.to_numeric(
                metrics.loc[metrics["condition"] == cond, metric],
                errors="coerce",
            ).dropna()
            x = i + rng.uniform(-0.13, 0.13, len(vals))
            ax.scatter(
                x,
                vals,
                s=16,
                color=colors[cond],
                edgecolors=figures.SURFACE,
                linewidths=0.9,
                zorder=3,
            )
            if len(vals):
                ax.hlines(
                    vals.median(),
                    i - 0.2,
                    i + 0.2,
                    color=colors[cond],
                    linewidth=1.8,
                    zorder=4,
                )
        ax.set_xticks(range(len(dataset.conditions)))
        ax.set_xticklabels(dataset.conditions, fontsize=6.5)
        ax.set_title(metric, fontsize=8, color=figures.INK, loc="left")
        lo, hi = ax.get_ylim()
        ax.set_ylim(min(0, lo), hi)
    for ax in axes_flat[len(available) :]:
        ax.axis("off")
    fig.suptitle(
        "Static code metrics by condition (every measurement drawn)",
        fontsize=10,
        color=figures.INK,
        x=0.02,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    return RecipeResult(
        tables=tables,
        figures={"metrics_by_condition": fig},
        summary=f"Static code quality (RQ-P2). {sentence}",
        methods=METHODS,
    )
