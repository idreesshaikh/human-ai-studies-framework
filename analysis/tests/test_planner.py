"""Planner validation: nominal alpha ±.015, normal power agreement ±.06.

Seeded calibration is a numerical validation, not an audit accuracy claim.
"""

from dataclasses import replace

import numpy as np
import pytest
from analysis.planner import (
    PlanInput,
    estimate_variance,
    plan_study,
    power_at,
    simulate_power,
)

from analysis import stats


def test_textbook_two_sample_and_paired_values_and_dropout():
    result = plan_study(PlanInput(test="two-sample-t", dropout=0.2))
    assert result["required"]["nPerArm"] == 64
    assert result["required"]["power"] == pytest.approx(0.8014595579)
    assert result["required"]["recruitPerArm"] == 80
    assert result["required"]["recruitTotal"] == 160
    paired = plan_study(PlanInput(design="within-subjects", test="paired-t"))
    assert paired["required"]["totalN"] == 34
    assert result["basis"] == "assumptions"
    assert result["sensitivity"][1]["totalN"] == 40


def test_ancova_reduces_n_using_declared_correlation():
    unadjusted = plan_study(PlanInput(test="two-sample-t"))["required"]["nPerArm"]
    adjusted = plan_study(PlanInput(test="two-sample-t", covariate_correlation=0.6))[
        "required"
    ]["nPerArm"]
    assert adjusted < unadjusted
    assert abs(adjusted / unadjusted - (1 - 0.6**2)) < 0.04


@pytest.mark.parametrize(
    "design,test,distribution",
    [
        ("between-subjects", "mann-whitney", "normal"),
        ("between-subjects", "mann-whitney", "log-normal"),
        ("between-subjects", "mann-whitney", "ordinal"),
        ("within-subjects", "wilcoxon", "normal"),
        ("within-subjects", "wilcoxon", "ordinal"),
    ],
)
def test_simulation_recovers_nominal_alpha(design, test, distribution):
    plan = PlanInput(
        design=design, test=test, distribution=distribution, simulations=4000, seed=59
    )
    result = simulate_power(plan, 40, effect=0)
    assert abs(result["power"] - plan.alpha) < 0.015
    assert result["ci"][0] <= result["power"] <= result["ci"][1]


@pytest.mark.parametrize(
    "design,test,analytic,n",
    [
        ("between-subjects", "mann-whitney", "two-sample-t", 64),
        ("within-subjects", "wilcoxon", "paired-t", 34),
    ],
)
def test_normal_simulation_agrees_with_analytic_within_stated_tolerance(
    design, test, analytic, n
):
    plan = PlanInput(design=design, test=test, simulations=4000, seed=73)
    observed = simulate_power(plan, n)["power"]
    reference = power_at(replace(plan, test=analytic), n)["power"]
    assert abs(observed - reference) < 0.06


def test_reproducible_curve_and_explicit_unreached_target():
    plan = PlanInput(effect=0.1, max_n=40, simulations=200)
    a, b = plan_study(plan), plan_study(plan)
    assert a == b
    assert a["required"] is None
    assert a["method"] == "simulation"
    assert a["nullPower"]["ci"] is not None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"design": "crossover"},
        {"design": "within-subjects", "test": "mann-whitney"},
        {"test": "binary"},
        {"effect": float("inf")},
        {"sd": 0},
        {"alpha": 1},
        {"dropout": 1},
        {"covariate_correlation": 0.5},
        {"simulations": 100000},
        {"test": "two-sample-t", "distribution": "ordinal"},
        {"design": "within-subjects", "test": "wilcoxon", "distribution": "log-normal"},
        {"test": "paired-t", "design": "within-subjects", "period_effect": 0.3},
    ],
)
def test_refuses_unsupported_or_invalid_assumptions(kwargs):
    with pytest.raises(ValueError):
        plan_study(replace(PlanInput(), **kwargs))


def test_paired_period_and_order_shifts_are_explicit_and_warn_about_null_bias():
    base = PlanInput(design="within-subjects", test="wilcoxon", simulations=1000)
    shifted = replace(base, order_effect=2)
    assert simulate_power(base, 40) != simulate_power(shifted, 40)
    result = plan_study(shifted)
    assert result["nullPower"]["power"] > 0.05
    assert any("false positives" in w for w in result["warnings"])


def test_batched_zero_and_tie_handling_matches_recipe():
    differences = np.array([[1, 2, 3, 4, 0], [1, 1, -2, -2, 0], [0, 0, 0, 0, 0]])
    p = stats.wilcoxon_pvalues(differences)
    for row, observed in zip(differences, p, strict=True):
        expected = stats.wilcoxon_paired(row.tolist(), [0] * len(row), ("a", "b"))
        assert observed == pytest.approx(expected.p)


def test_pilot_variance_intervals_and_small_pilot_flag():
    pilot = estimate_variance([1, 2, 3, 4, 5, 6])
    assert pilot["variance"] == pytest.approx(3.5)
    assert pilot["varianceCI"][0] < pilot["variance"] < pilot["varianceCI"][1]
    assert not pilot["actionable"] and pilot["warnings"]
    assert estimate_variance(list(range(8)))["actionable"]
    for values in ([1], [1, 1], [1, float("nan")]):
        with pytest.raises(ValueError):
            estimate_variance(values)


def test_inflated_null_rejection_withholds_the_required_sample_size():
    """A design with inflated false positives must not report a cheaper-looking n."""
    biased = replace(
        PlanInput(design="within-subjects", test="wilcoxon", simulations=1000),
        order_effect=0.5,
    )
    result = plan_study(biased)
    assert result["required"] is None
    withheld = result["requiredWithheld"]
    assert withheld["code"] == "inflated-null-rejection"
    assert "false positives" in withheld["message"]
    assert withheld["nullRejection"]["ci"][0] > biased.alpha


def test_unbiased_plan_reports_its_sample_size_and_no_withholding():
    clean = PlanInput(design="within-subjects", test="wilcoxon", simulations=1000)
    result = plan_study(clean)
    assert result["required"] is not None
    assert result["requiredWithheld"] is None
