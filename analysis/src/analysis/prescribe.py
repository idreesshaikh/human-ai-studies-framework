"""Deterministic prescription table (FR-TPL-6)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prescription:
    """One row of the prescription table: what test to run and how to report it."""

    design_shape: str
    test: str
    effect_size: str
    correction: str
    sample_size_guidance: str
    rationale: str


_TABLE: dict[str, Prescription] = {
    "two-group": Prescription(
        design_shape="two-group",
        test="Mann-Whitney U (exact, two-sided)",
        effect_size="Cliff's delta",
        correction="none",
        sample_size_guidance="≥3 per cell for exact distribution; "
        "≥6 per cell recommended for stable effect-size estimates",
        rationale="Independent two-group comparison on ordinal/skewed data "
        "(most HCI/SE measures). Mann-Whitney is the non-parametric "
        "independent t-test. Cliff's delta is its effect-size twin, "
        "robust for small samples. Exact distribution avoids asymptotic "
        "approximation error. NFR-8: honest statistics by construction.",
    ),
    "paired": Prescription(
        design_shape="paired",
        test="Wilcoxon signed-rank (exact, two-sided)",
        effect_size="Matched-pairs rank-biserial correlation (r)",
        correction="none",
        sample_size_guidance="≥4 non-zero difference pairs for exact "
        "distribution; ≥6 pairs recommended",
        rationale="Within-subjects/paired comparison on ordinal data. "
        "Wilcoxon signed-rank is the non-parametric paired t-test. "
        "Rank-biserial r is interpretable as the fraction of pairs "
        "favouring one condition over the other. Zero differences are "
        "excluded following Siegel & Castellan. NFR-8: exact p-values.",
    ),
    "multi-group": Prescription(
        design_shape="multi-group",
        test="Kruskal-Wallis H (exact where available, else asymptotic)",
        effect_size="Epsilon-squared (ε²) or rank-eta-squared",
        correction="Holm-Bonferroni for post-hoc pairwise comparisons "
        "via Dunn's test",
        sample_size_guidance="≥3 per group; ≥5 per group recommended; "
        "post-hoc comparisons follow the paired/two-group guidance",
        rationale="Multi-group (3+) independent comparison. Kruskal-Wallis "
        "is the non-parametric one-way ANOVA. Epsilon-squared is the "
        "recommended effect size (Tomczak & Tomczak 2014). Post-hoc "
        "Dunn's test with Holm correction controls familywise error "
        "without the conservatism of Bonferroni. NFR-8: every pairwise "
        "comparison reports its own n, exact test, and effect size.",
    ),
    "multi-factorial": Prescription(
        design_shape="multi-factorial",
        test="Aligned-rank transform (ART) ANOVA or Scheirer-Ray-Hare",
        effect_size="Partial epsilon-squared (ε²p) or rank partial η²",
        correction="Holm-Bonferroni for post-hoc comparisons",
        sample_size_guidance="≥3 per cell; ≥5 per cell recommended; "
        "interaction effects require ≥3 per cell for reliable estimates",
        rationale="Factorial designs with ordinal data. ART ANOVA "
        "(Wobbrock et al. 2011) is the recommended non-parametric "
        "factorial test for HCI studies. Scheirer-Ray-Hare is an "
        "alternative when ART assumptions are violated. Main effects "
        "and interactions reported with effect sizes. Post-hoc "
        "comparisons use Dunn's test with Holm correction. "
        "NFR-8: per-cell n always stated.",
    ),
    "repeated-measures": Prescription(
        design_shape="repeated-measures",
        test="Friedman test (exact or asymptotic)",
        effect_size="Kendall's W (coefficient of concordance) or "
        "rank-biserial r for pairwise follow-ups",
        correction="Holm-Bonferroni for post-hoc pairwise Wilcoxon comparisons",
        sample_size_guidance="≥3 time points × ≥4 participants; "
        "≥6 participants recommended",
        rationale="Repeated measurements across 3+ time points. "
        "Friedman is the non-parametric repeated-measures ANOVA. "
        "Kendall's W measures agreement across measurements. "
        "Post-hoc: Wilcoxon signed-rank with Holm correction. "
        "NFR-8: per-cell n, exact p-values, effect sizes everywhere.",
    ),
    "proportion": Prescription(
        design_shape="proportion",
        test="Fisher's exact test (two-sided)",
        effect_size="Odds ratio with 95% CI",
        correction="none (single 2×2 table); "
        "Holm-Bonferroni if multiple proportion comparisons",
        sample_size_guidance="≥5 per cell recommended (Fisher remains "
        "valid below 5 — the exact test is defined for any 2×2 table)",
        rationale="Binary outcome (pass/fail, accept/reject) by condition. "
        "Fisher's exact test is the gold standard for 2×2 tables at "
        "pilot counts (no minimum cell count assumption). Odds ratio is "
        "the standard effect size for binary outcomes. "
        "NFR-8: cell counts stated, never a bare p-value.",
    ),
    "correlation": Prescription(
        design_shape="correlation",
        test="Spearman's rank correlation (ρ)",
        effect_size="Spearman's ρ (same as the test statistic)",
        correction="none for a single pair of variables; "
        "Holm-Bonferroni if evaluating multiple correlations",
        sample_size_guidance="≥4 pairs for a meaningful ρ estimate; "
        "≥10 pairs recommended for stable estimates",
        rationale="Monotonic association between two ordinal/continuous "
        "variables. Spearman's ρ is rank-based and robust to outliers. "
        "The test statistic and effect size are identical, simplifying "
        "reporting. NFR-8: n always stated; undefined when either "
        "variable is constant.",
    ),
    "single-arm": Prescription(
        design_shape="single-arm",
        test="Descriptive statistics only (mean/median, min/max, per-cell n); "
        "no inferential test",
        effect_size="No effect size applicable",
        correction="none",
        sample_size_guidance="No minimum (single-arm is always descriptive); "
        "report all observations and note the absence of a comparison group",
        rationale="Single-condition studies provide no comparison. "
        "Reporting descriptive statistics (n, min, median, mean, max) "
        "is the only honest analysis. Framed explicitly as "
        "hypothesis-generating (NFR-8). No p-values or effect sizes "
        "computed — they would be meaningless without a comparator.",
    ),
}

SHAPES = list(_TABLE.keys())


def prescribe(design_shape: str) -> Prescription | None:
    """Look up the prescription for a design shape."""
    return _TABLE.get(design_shape)


def prescription_table() -> list[Prescription]:
    """All prescriptions, in canonical order."""
    return [_TABLE[shape] for shape in SHAPES]


def design_shapes() -> list[str]:
    """Canonical list of supported design shapes."""
    return list(SHAPES)


_SHAPE_RECIPES = {
    "two-group": "two-group-nonparametric",
    "paired": "paired-nonparametric",
    "proportion": "two-proportion",
    "correlation": "correlation",
}


def shape_to_recipe_id(design_shape: str) -> str | None:
    """The built-in recipe that runs this shape's prescribed test, if any."""
    return _SHAPE_RECIPES.get(design_shape)


def runnable_shapes() -> list[str]:
    """Design shapes whose prescribed test PHOENIX can run itself."""
    return [s for s in SHAPES if s in _SHAPE_RECIPES]
