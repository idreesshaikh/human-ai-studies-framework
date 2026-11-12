"""Non-compliance simulation: bias, coverage and sample size when AI use breaks."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError, replace

import numpy as np
import pytest
from analysis.adherence_sim import (
    MIXES,
    Scenario,
    _comparison_masks,
    _draw_inputs,
    _simulate_data,
    _welch_masked,
    mixed_sensitivity,
    required_n,
    simulate,
)
from scipy import stats as sps

ESTIMATORS = ("itt", "exclude-detected", "as-detected")
ROUTES = (
    "copilot-inline",
    "copilot-chat",
    "browser-paste",
    "retype",
    "cli-agent-hooks",
    "cli-agent-no-hooks",
)


def scenario(**overrides) -> Scenario:
    base = {
        "effect_d": 0.5,
        "n_per_arm": 200,
        "control_violation": 0.0,
        "treatment_nonuse": 0.0,
        "mechanism": "random",
        "sensitivity": 1.0,
        "specificity": 1.0,
    }
    return Scenario(**{**base, **overrides})


def finite_or_none(value) -> bool:
    return value is None or (isinstance(value, float) and math.isfinite(value))


def test_full_compliance_all_unbiased():
    out = simulate(scenario(), reps=2000)
    assert set(out) == set(ESTIMATORS)
    for name in ESTIMATORS:
        assert abs(out[name]["bias"]) < 0.03, name
        assert out[name]["refused"] == 0, name


def test_itt_dilutes_by_violation_rate():
    out = simulate(
        scenario(control_violation=0.25, sensitivity=0.9, specificity=0.95), reps=2000
    )
    assert abs(out["itt"]["bias"] - (-0.125)) < 0.03


def test_undetectable_violation_exclusion_equals_itt():
    out = simulate(scenario(control_violation=0.25, sensitivity=0.0), reps=2000)
    assert abs(out["exclude-detected"]["bias"] - out["itt"]["bias"]) < 0.03


@pytest.mark.parametrize("mechanism", ["random", "skill-linked"])
@pytest.mark.parametrize("sensitivity", [0.0, 0.6, 1.0])
@pytest.mark.parametrize("specificity", [0.0, 0.7, 1.0])
@pytest.mark.parametrize("nonuse", [0.0, 0.3, 1.0])
def test_exclude_detected_never_drops_treated_participants(
    mechanism, sensitivity, specificity, nonuse
):
    s = scenario(
        n_per_arm=12,
        control_violation=0.3,
        treatment_nonuse=nonuse,
        mechanism=mechanism,
        sensitivity=sensitivity,
        specificity=specificity,
    )
    _, flagged = _simulate_data(s, 50, 20261112)
    treated, control = _comparison_masks(12, flagged)["itt"]
    kept_treated, kept_control = _comparison_masks(12, flagged)["exclude-detected"]
    kept_treated = np.broadcast_to(kept_treated, flagged.shape)
    kept_control = np.broadcast_to(kept_control, flagged.shape)
    # Treated-arm n is 12 in every replicate and nobody in it is dropped.
    assert (kept_treated.sum(axis=0) == 12).all()
    np.testing.assert_array_equal(kept_treated, np.broadcast_to(treated, flagged.shape))
    # Only control participants flagged as AI users are dropped.
    np.testing.assert_array_equal(
        kept_control, np.broadcast_to(control, flagged.shape) & ~flagged
    )


def test_exclude_detected_ignores_treated_non_use_when_nobody_in_control_is_flagged():
    # Every treated participant is a non-user; the old "drop unflagged treated" rule
    # would empty the arm. Dropping only flagged controls leaves the analysis as ITT.
    out = simulate(scenario(treatment_nonuse=1.0), reps=300)
    assert out["exclude-detected"] == out["itt"]
    assert out["exclude-detected"]["refused"] == 0
    blind = simulate(scenario(control_violation=0.25, sensitivity=0.0), reps=300)
    assert blind["exclude-detected"] == blind["itt"]


def test_skill_linked_exclusion_biased_even_with_perfect_detection():
    out = simulate(
        scenario(control_violation=0.25, mechanism="skill-linked"), reps=2000
    )
    assert out["exclude-detected"]["bias"] < -0.05
    assert out["as-detected"]["bias"] < -0.05
    # Removing the lowest-skill quarter of controls shifts their mean skill by about
    # 0.7 * 0.424 = 0.30, so the exclusion bias is not a small effect.
    assert out["exclude-detected"]["bias"] == pytest.approx(-0.30, abs=0.04)


def test_required_n_itt_matches_dilution_rule():
    s = scenario(control_violation=0.25, treatment_nonuse=0.0)
    n = required_n(s, "itt")
    expected = math.ceil(64 / 0.75**2)
    assert expected == 114
    assert n is not None
    assert abs(n - expected) <= 0.12 * expected


def test_edge_inputs_never_nan():
    s = scenario(
        control_violation=0.35,
        treatment_nonuse=0.2,
        sensitivity=0.0,
        specificity=1.0,
        n_per_arm=4,
    )
    out = simulate(s, reps=500)
    assert set(out) == set(ESTIMATORS)
    for name, row in out.items():
        assert set(row) == {"bias", "coverage", "power", "refused"}, name
        assert row["refused"] >= 0
        for key in ("bias", "coverage", "power"):
            assert finite_or_none(row[key]), (name, key, row[key])
    # Nobody is ever flagged, so the as-detected analysis never has a flagged group.
    assert out["as-detected"]["refused"] == 500
    assert out["as-detected"]["bias"] is None
    assert out["as-detected"]["coverage"] is None
    assert out["as-detected"]["power"] is None


def test_mixed_sensitivity_rejects_bad_mix():
    per_route = {"browser-paste": 0.4, "retype": 0.2}
    with pytest.raises(ValueError):
        mixed_sensitivity(per_route, {"browser-paste": 0.5, "retype": 0.4})


# --- extra checks beyond the brief ---------------------------------------------------


def test_mixed_sensitivity_weighted_mean_and_missing_route():
    per_route = {r: 0.1 * (i + 1) for i, r in enumerate(ROUTES)}
    mean = mixed_sensitivity(per_route, MIXES["instruction-only"])
    assert mean == pytest.approx(sum(per_route.values()) / 6)
    locked = mixed_sensitivity(per_route, MIXES["locked-environment"])
    assert locked == pytest.approx(
        0.5 * per_route["browser-paste"] + 0.5 * per_route["retype"]
    )
    with pytest.raises(ValueError):
        mixed_sensitivity({"retype": 0.5}, MIXES["locked-environment"])
    with pytest.raises(ValueError):
        mixed_sensitivity(per_route, {})
    with pytest.raises(ValueError):
        mixed_sensitivity(per_route, {"browser-paste": 1.5, "retype": -0.5})


def test_mixes_are_the_specified_routes():
    assert set(MIXES) == {"instruction-only", "locked-environment"}
    assert set(MIXES["instruction-only"]) == set(ROUTES)
    assert sum(MIXES["instruction-only"].values()) == pytest.approx(1.0, abs=1e-9)
    assert all(w == pytest.approx(1 / 6) for w in MIXES["instruction-only"].values())
    assert MIXES["locked-environment"] == {"browser-paste": 0.5, "retype": 0.5}


@pytest.mark.parametrize(
    "overrides",
    [
        {"control_violation": -0.01},
        {"control_violation": 0.51},
        {"treatment_nonuse": 1.01},
        {"treatment_nonuse": -0.1},
        {"sensitivity": 1.2},
        {"specificity": -0.2},
        {"sensitivity": float("nan")},
        {"n_per_arm": 3},
        {"alpha": 0.0},
        {"mechanism": "bogus"},
    ],
)
def test_scenario_validation_rejects_bad_inputs(overrides):
    with pytest.raises(ValueError):
        scenario(**overrides)


def test_scenario_boundaries_are_accepted():
    scenario(
        control_violation=0.5,
        treatment_nonuse=1.0,
        sensitivity=0.0,
        specificity=0.0,
        n_per_arm=4,
    )
    with pytest.raises(FrozenInstanceError):
        scenario().n_per_arm = 10  # type: ignore[misc]


def test_welch_matches_scipy_including_confidence_interval():
    rng = np.random.default_rng(7)
    n_rows, reps = 30, 5
    y = rng.normal(0.3, 1.4, size=(n_rows, reps))
    g1 = rng.random((n_rows, reps)) < 0.55
    g0 = ~g1 & (rng.random((n_rows, reps)) < 0.8)
    est, lo, hi, p, valid = _welch_masked(y, g1, g0, alpha=0.05)
    assert valid.all()
    for r in range(reps):
        a, b = y[g1[:, r], r], y[g0[:, r], r]
        ref = sps.ttest_ind(a, b, equal_var=False)
        ci = ref.confidence_interval(0.95)
        assert est[r] == pytest.approx(a.mean() - b.mean())
        assert p[r] == pytest.approx(ref.pvalue, rel=1e-9)
        assert lo[r] == pytest.approx(ci.low, rel=1e-9)
        assert hi[r] == pytest.approx(ci.high, rel=1e-9)


def test_welch_marks_groups_smaller_than_two_invalid():
    y = np.arange(12, dtype=float).reshape(6, 2)
    g1 = np.array([[1, 1], [1, 0], [1, 0], [0, 0], [0, 0], [0, 0]], dtype=bool)
    g0 = np.array([[0, 0], [0, 0], [0, 0], [1, 1], [1, 1], [1, 1]], dtype=bool)
    est, lo, hi, _p, valid = _welch_masked(y, g1, g0, alpha=0.05)
    assert valid.tolist() == [True, False]  # column 1 has a one-person group
    assert np.isfinite(est[0]) and np.isfinite(lo[0]) and np.isfinite(hi[0])


def test_full_compliance_coverage_and_power_match_textbook():
    ci = simulate(scenario(n_per_arm=64), reps=3000)["itt"]
    assert ci["coverage"] == pytest.approx(0.95, abs=0.02)
    # 64 per arm at d=0.5 is the textbook 80% power design.
    assert ci["power"] == pytest.approx(0.80, abs=0.04)


def test_dilution_destroys_itt_coverage_of_the_true_effect():
    out = simulate(scenario(control_violation=0.25), reps=2000)["itt"]
    assert out["coverage"] < 0.85


def test_random_exclusion_is_unbiased_with_imperfect_detection():
    s = scenario(
        control_violation=0.25,
        treatment_nonuse=0.1,
        sensitivity=0.8,
        specificity=0.9,
    )
    out = simulate(s, reps=2000)
    # Detected users are a random subset of users, so the exclusion contrast is
    # contaminated only by missed violators and falsely excluded controls.
    assert out["exclude-detected"]["bias"] > out["itt"]["bias"]
    assert abs(out["exclude-detected"]["bias"]) < abs(out["itt"]["bias"])


def test_refused_counts_small_groups_and_stays_within_reps():
    s = scenario(
        control_violation=0.5,
        treatment_nonuse=0.5,
        n_per_arm=4,
        sensitivity=1.0,
        specificity=1.0,
    )
    out = simulate(s, reps=400)
    for row in out.values():
        assert 0 <= row["refused"] <= 400
    assert out["itt"]["refused"] == 0
    assert out["exclude-detected"]["refused"] > 0


def test_simulate_is_deterministic_and_seed_sensitive():
    s = scenario(
        control_violation=0.2, treatment_nonuse=0.1, sensitivity=0.8, specificity=0.9
    )
    first = simulate(s, reps=300)
    again = simulate(s, reps=300)
    other = simulate(s, reps=300, seed=1)
    assert first == again
    assert first != other


def test_draws_are_common_random_numbers_across_n():
    small = _draw_inputs(10, 6, seed=20261112)
    large = _draw_inputs(40, 6, seed=20261112)
    assert set(small) == set(large)
    for key in small:
        np.testing.assert_array_equal(small[key], large[key][:10])


def test_required_n_is_deterministic_and_monotone_in_effect():
    base = scenario(control_violation=0.1)
    n_big = required_n(replace(base, effect_d=0.8), "itt", reps=400)
    n_small = required_n(replace(base, effect_d=0.5), "itt", reps=400)
    assert n_big is not None and n_small is not None
    assert n_big < n_small
    assert required_n(replace(base, effect_d=0.5), "itt", reps=400) == n_small


def test_required_n_returns_none_when_target_not_reached():
    # No true effect: a power target of 80% is never reached, whatever the n.
    assert required_n(scenario(effect_d=0.0), "itt", reps=200, max_n=64) is None
    # A hard cap below the needed n.
    assert required_n(scenario(effect_d=0.2), "itt", reps=200, max_n=20) is None


def test_required_n_rejects_unknown_estimator():
    with pytest.raises(ValueError):
        required_n(scenario(), "per-protocol")
