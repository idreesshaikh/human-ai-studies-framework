import numpy as np
import pytest
from measure_mapping import metrics as m

Y = np.array([0, 1, 2, 1])
P = np.array(
    [
        [0.7, 0.2, 0.1],
        [0.1, 0.8, 0.1],
        [0.2, 0.2, 0.6],
        [0.6, 0.3, 0.1],  # wrong, confident
    ]
)


def test_coverage_cannot_split_equal_confidence_items():
    probabilities = np.array([[0.8, 0.2], [0.8, 0.2]])
    truth = np.array([0, 1])
    assert m.coverage_at_risk(probabilities, truth, 0.05) == 0.0
    assert m.coverage_at_risk(probabilities[::-1], truth[::-1], 0.05) == 0.0


@pytest.mark.parametrize(
    "probs,y",
    [
        (np.array([[-0.1, 1.1]]), np.array([1])),
        (np.array([[0.5, 0.5]]), np.array([-1])),
        (np.array([[0.5, 0.5]]), np.array([2])),
    ],
)
def test_invalid_probabilities_or_class_indices_are_refused(probs, y):
    with pytest.raises(ValueError):
        m.nll(probs, y)


def test_accuracy_and_macro_f1():
    assert m.accuracy(P, Y) == pytest.approx(0.75)
    # class 0: tp1 fp1 fn0 -> 2/3; class 1: tp1 fp0 fn1 -> 2/3; class 2: tp1 -> 1.0
    assert m.macro_f1(P, Y) == pytest.approx((2 / 3 + 2 / 3 + 1.0) / 3)


def test_nll_and_brier_hand_computed():
    assert m.nll(P, Y) == pytest.approx(
        -(np.log(0.7) + np.log(0.8) + np.log(0.6) + np.log(0.3)) / 4
    )
    expected = np.mean(
        [0.09 + 0.04 + 0.01, 0.01 + 0.04 + 0.01, 0.04 + 0.04 + 0.16, 0.36 + 0.49 + 0.01]
    )
    assert m.brier(P, Y) == pytest.approx(expected)


def test_a_perfect_confident_model_has_zero_nll_brier_ece():
    probs = np.eye(3)[Y]
    assert m.nll(probs, Y) == pytest.approx(0.0, abs=1e-9)
    assert m.brier(probs, Y) == pytest.approx(0.0)
    assert m.ece(probs, Y) == pytest.approx(0.0)


def test_ece_detects_overconfidence_in_both_binning_schemes():
    # Distinct confidences 0.85-0.95, but only half the answers right: ECE is about 0.4.
    conf = np.linspace(0.85, 0.95, 20)
    probs = np.stack([conf, 1 - conf], axis=1)
    y = np.array([0, 1] * 10)  # right, wrong, right, wrong, ...
    assert m.ece(probs, y, bins=10) == pytest.approx(0.4, abs=0.01)
    assert m.ece(probs, y, bins=10, equal_mass=True) == pytest.approx(0.4, abs=0.01)


def test_equal_mass_binning_splits_tied_confidences_by_input_order():
    """Use equal-width ECE bins when many confidences are tied."""
    probs = np.tile([0.9, 0.1], (10, 1))
    y = np.array([0] * 5 + [1] * 5)
    assert m.ece(probs, y, bins=10) == pytest.approx(0.4)  # one bin: |0.5 - 0.9|
    assert m.ece(probs, y, bins=5, equal_mass=True) != pytest.approx(0.4)


def test_coverage_at_risk():
    # The two tied .6 items must be answered together; their joint risk is .25.
    assert m.coverage_at_risk(P, Y, 0.0) == pytest.approx(0.5)
    assert m.coverage_at_risk(P, Y, 0.25) == pytest.approx(1.0)
    assert m.coverage_at_risk(np.array([[0.9, 0.1]]), np.array([1]), 0.05) == 0.0


def test_bootstrap_resamples_groups_and_is_reproducible():
    groups = ["a", "a", "b", "b", "c", "c"]
    correct = np.array([1, 1, 0, 0, 1, 1], dtype=float)
    stat = lambda idx: float(correct[idx].mean())  # noqa: E731
    first = m.cluster_bootstrap(stat, groups, n_boot=500, seed=1)
    assert first == m.cluster_bootstrap(stat, groups, n_boot=500, seed=1)
    assert 0.0 <= first[0] <= 2 / 3 <= first[1] <= 1.0
    # with one group there is nothing to resample: a degenerate interval
    lo, hi = m.cluster_bootstrap(stat, ["x"] * 6, n_boot=50, seed=1)
    assert lo == hi


def test_kappa():
    assert m.cohen_kappa(list("aabb"), list("aabb")) == pytest.approx(1.0)
    assert m.cohen_kappa(list("aabb"), list("abab")) == pytest.approx(0.0)
    assert np.isnan(m.cohen_kappa(list("aaaa"), list("aaaa")))
    with pytest.raises(ValueError):
        m.cohen_kappa(["a"], ["a", "b"])


def test_bad_inputs_are_refused():
    with pytest.raises(ValueError):
        m.nll(np.array([[0.5, 0.2]]), np.array([0]))
    with pytest.raises(ValueError):
        m.accuracy(np.zeros((0, 2)), np.array([]))


def test_bootstrap_refuses_undefined_statistics():
    with pytest.raises(ValueError, match="undefined"):
        m.cluster_bootstrap(lambda idx: float("nan"), ["a", "b"], n_boot=10)
