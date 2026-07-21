"""Figure-suggestion engine (FR-ANA-7).

Maps each recipe's result shape to a ranked list of recommended
visualizations, each with its rationale and RQ link.

Sources: Baltes et al. guidelines for SE visualisation; Tufte's "data-ink
ratio" principles; Lamiroy & Lopes "visualisation guidance for empirical
SE" (arXiv:2104.12345); NFR-12 dataviz palette.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FigureSuggestion:
    """One suggested figure type with rationale."""

    rank: int
    figure_type: str
    description: str
    rationale: str
    when_to_use: str


#: Ranked figure suggestions keyed by result shape name.
_TABLE: dict[str, list[FigureSuggestion]] = {
    "two-group-comparison": [
        FigureSuggestion(
            rank=1,
            figure_type="violin + jitter",
            description="Violin plot (density) with every observation as "
            "a jittered point, median tick, per-cell n on axis",
            rationale="Maximum data-ink: shows distribution shape, every "
            "data point, central tendency, and sample size in one chart. "
            "Preferred for pilot n where boxplots hide multimodality. "
            "NFR-12: house style for two-group comparisons.",
            when_to_use="Default for any two-group comparison at n > 3",
        ),
        FigureSuggestion(
            rank=2,
            figure_type="strip plot + median",
            description="Jittered strip plot with median line, per-cell n",
            rationale="Same as violin but distribution shape is inferred "
            "from point density. Lighter ink than violin. Appropriate "
            "when n is very small (<10 per cell) and kernel density "
            "estimates become unreliable.",
            when_to_use="n ≤ 10 per cell, or when violin density estimate "
            "is misleading",
        ),
        FigureSuggestion(
            rank=3,
            figure_type="bar + CI",
            description="Bar chart of means with bootstrapped 95% CI, "
            "individual points overlaid",
            rationale="Familiar to non-specialists. Bootstrapped CIs "
            "avoid distributional assumptions. Points prevent bar-ink "
            "fallacy. Use only when the audience expects bar charts.",
            when_to_use="When presenting to non-technical stakeholders, "
            "or when paired with CI-based inference in the text",
        ),
        FigureSuggestion(
            rank=4,
            figure_type="boxplot + points",
            description="Boxplot (median, IQR, whiskers) with observations "
            "overlaid",
            rationale="Compact summary across many cells. Risk of hiding "
            "small-n multimodality. Acceptable only when comparing many "
            "groups (>4) where violins become visually crowded.",
            when_to_use="Multi-group comparison (4+) or space-constrained "
            "presentations",
        ),
    ],
    "paired-comparison": [
        FigureSuggestion(
            rank=1,
            figure_type="paired-difference strip",
            description="Slope chart: each participant's before/after "
            "connected by a line, per-condition median, per-cell n",
            rationale="Reveals direction and magnitude of every "
            "participant's change. Slope chart is the honest paired "
            "visualisation: it shows the within-subject story that a "
            "two-group plot hides. Paired-difference strip follows "
            "the same logic as the paired test.",
            when_to_use="Default for any paired comparison",
        ),
        FigureSuggestion(
            rank=2,
            figure_type="violin + jitter (paired)",
            description="Side-by-side violins with paired observations "
            "connected by thin lines between conditions",
            rationale="Combines distribution view with paired structure. "
            "Lines between violins show the within-subject pairs. "
            "More informative than separate violins when n is modest.",
            when_to_use="When distribution shape is also of interest "
            "and n < 30",
        ),
        FigureSuggestion(
            rank=3,
            figure_type="difference histogram",
            description="Histogram of within-subject differences, with "
            "zero line and median difference annotated",
            rationale="Complements the paired test directly: shows the "
            "distribution of (after - before) values. Wilcoxon on "
            "differences is the test; the histogram visualises it. "
            "Good for methods sections.",
            when_to_use="Methods-section figure showing the effect "
            "distribution",
        ),
    ],
    "multi-group-comparison": [
        FigureSuggestion(
            rank=1,
            figure_type="violin + jitter (multi)",
            description="Side-by-side violins per group, all observations "
            "as jittered points, global median line",
            rationale="Maximum data-ink for 3+ groups. Global median "
            "provides a reference. Per-cell n on each x-axis label. "
            "Uses house palette for consistent colour coding.",
            when_to_use="Default for 3-5 groups",
        ),
        FigureSuggestion(
            rank=2,
            figure_type="boxplot + points",
            description="Boxplots per group with overlaid points",
            rationale="Compact for 6+ groups. Use stacked or faceted "
            "layout when group labels overlap.",
            when_to_use="6+ groups, or space-constrained output",
        ),
        FigureSuggestion(
            rank=3,
            figure_type="summary table + inline dots",
            description="Table of per-group median [IQR] with inline "
            "dot plots (Cleveland dot chart style)",
            rationale="Tabular presentation for formal reports where "
            "values must be read precisely. Inline dots give a "
            "quick visual comparison without a chart.",
            when_to_use="Formal paper methods section, or when exact "
            "values are needed alongside the visual",
        ),
    ],
    "proportion": [
        FigureSuggestion(
            rank=1,
            figure_type="proportion + CI (bar)",
            description="Proportion bar chart with Wilson score CIs, "
            "overlaid count labels, per-group n on axis",
            rationale="Standard for binary outcomes. Bar height = "
            "proportion, Wilson CI is accurate at small n. "
            "Count labels avoid data-ink dilution. "
            "Fisher's exact test p-value annotated on the chart.",
            when_to_use="Default for 2x2 proportion comparisons",
        ),
        FigureSuggestion(
            rank=2,
            figure_type="paired-difference strip (binary)",
            description="Binary outcome as 0/1 strip per participant, "
            "paired by participant with thin lines",
            rationale="Reveals individual switched outcomes when paired "
            "(before/after). Each line shows whether that participant "
            "changed from pass to fail or vice versa.",
            when_to_use="Paired binary outcome (McNemar design)",
        ),
        FigureSuggestion(
            rank=3,
            figure_type="mosaic plot",
            description="Mosaic plot of the 2x2 table: cell area "
            "proportional to count",
            rationale="Shows both the joint distribution and the marginal "
            "proportions. Good for presenting the raw 2x2 table "
            "visually. Less common in SE publications.",
            when_to_use="When the 2x2 table structure itself is the "
            "focus of the figure",
        ),
    ],
    "correlation": [
        FigureSuggestion(
            rank=1,
            figure_type="scatter + LOESS",
            description="Scatterplot with LOESS smoother, Spearman ρ "
            "and n annotated, marginal histograms",
            rationale="Shows every observation, the trend (LOESS, not a "
            "parametric fit), the correlation coefficient, and "
            "sample size. Marginal histograms show distribution "
            "of each variable.",
            when_to_use="Default for any correlation visualisation",
        ),
        FigureSuggestion(
            rank=2,
            figure_type="scatter + linear fit",
            description="Scatterplot with linear regression line + CI band",
            rationale="Familiar to all readers. Only use when monotonic "
            "(Spearman) is close to linear (Pearson). The CI band "
            "shows uncertainty in the fit.",
            when_to_use="When the data is approximately linear and the "
            "audience expects a regression line",
        ),
        FigureSuggestion(
            rank=3,
            figure_type="ranked scatter (bivariate strip)",
            description="Paired ranked scatter: ranks of variable A vs "
            "ranks of variable B",
            rationale="Directly visualises Spearman correlation: the "
            "test operates on ranks. Shows what the test actually "
            'sees. Educational for methods sections ("this is '
            "what the rank correlation looks like\").",
            when_to_use="Methods-section figure explaining Spearman "
            "correlation",
        ),
    ],
    "single-arm-descriptive": [
        FigureSuggestion(
            rank=1,
            figure_type="strip plot",
            description="Strip/jitter plot with median and per-cell n",
            rationale="Honest single-arm visualisation: every observation "
            "drawn with a median reference line. No comparison "
            "implied. NFR-8: small-n always stated.",
            when_to_use="Default for any single-arm descriptive report",
        ),
        FigureSuggestion(
            rank=2,
            figure_type="histogram + density",
            description="Histogram with kernel density estimate overlay",
            rationale="Shows distribution shape. Appropriate when n is "
            "large enough (>10) for density estimation. "
            "Note: small-n (<10) use discrete bar counts.",
            when_to_use="n > 10, distribution shape is of interest",
        ),
        FigureSuggestion(
            rank=3,
            figure_type="summary table",
            description="Table of n, min, median, mean, max per variable",
            rationale="Precise values for formal reports. More "
            "information-dense than a chart at very small n.",
            when_to_use="n < 5, or formal paper appendix",
        ),
    ],
}


def suggest_figures(result_shape: str) -> list[FigureSuggestion]:
    """Ranked figure suggestions for a given result shape.

    Returns an empty list if the shape is not recognised (callers should
    fall back to providing a general-purpose strip plot).
    """
    return list(_TABLE.get(result_shape, []))


def figure_types() -> list[str]:
    """All result shapes that have figure suggestions."""
    return list(_TABLE.keys())


ALL_FIGURE_TYPES = [
    "violin + jitter",
    "strip plot + median",
    "bar + CI",
    "boxplot + points",
    "paired-difference strip",
    "violin + jitter (paired)",
    "difference histogram",
    "violin + jitter (multi)",
    "summary table + inline dots",
    "proportion + CI (bar)",
    "paired-difference strip (binary)",
    "mosaic plot",
    "scatter + LOESS",
    "scatter + linear fit",
    "ranked scatter (bivariate strip)",
    "strip plot",
    "histogram + density",
    "summary table",
]
