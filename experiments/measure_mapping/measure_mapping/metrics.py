"""Measure-mapping metrics; probabilities are numpy (n, k) arrays."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

_EPS = 1e-12


def _check(probs: np.ndarray, y: np.ndarray) -> None:
    if probs.ndim != 2 or len(probs) != len(y) or len(y) == 0:
        raise ValueError(
            "probs must be (n, k) with one true class index per row, n > 0"
        )
    if not np.allclose(probs.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("each row of probs must sum to 1")
    if not np.all(np.isfinite(probs)) or np.any(probs < 0) or np.any(probs > 1):
        raise ValueError("probabilities must be finite and between zero and one")
    if y.ndim != 1 or not np.issubdtype(y.dtype, np.integer):
        raise ValueError("true classes must be a one-dimensional integer array")
    if np.any(y < 0) or np.any(y >= probs.shape[1]):
        raise ValueError("true class index is outside the probability columns")


def accuracy(probs: np.ndarray, y: np.ndarray) -> float:
    _check(probs, y)
    return float(np.mean(probs.argmax(axis=1) == y))


def macro_f1(probs: np.ndarray, y: np.ndarray) -> float:
    """Mean F1 over true or predicted classes; skip absent classes."""
    _check(probs, y)
    pred = probs.argmax(axis=1)
    scores = []
    for c in sorted(set(y.tolist()) | set(pred.tolist())):
        tp = int(np.sum((pred == c) & (y == c)))
        fp = int(np.sum((pred == c) & (y != c)))
        fn = int(np.sum((pred != c) & (y == c)))
        denom = 2 * tp + fp + fn
        scores.append(0.0 if denom == 0 else 2 * tp / denom)
    return float(np.mean(scores))


def nll(probs: np.ndarray, y: np.ndarray) -> float:
    """Mean negative log-likelihood of the true class (lower is better)."""
    _check(probs, y)
    return float(-np.mean(np.log(np.clip(probs[np.arange(len(y)), y], _EPS, 1.0))))


def brier(probs: np.ndarray, y: np.ndarray) -> float:
    """Multiclass Brier score: mean squared distance to the one-hot truth."""
    _check(probs, y)
    onehot = np.zeros_like(probs)
    onehot[np.arange(len(y)), y] = 1.0
    return float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))


def ece(
    probs: np.ndarray, y: np.ndarray, *, bins: int = 10, equal_mass: bool = False
) -> float:
    """Expected calibration error of the top label, equal-width or equal-mass bins."""
    _check(probs, y)
    conf = probs.max(axis=1)
    correct = (probs.argmax(axis=1) == y).astype(float)
    if equal_mass:
        order = np.argsort(conf, kind="stable")
        groups = [g for g in np.array_split(order, bins) if len(g)]
    else:
        edges = np.linspace(0.0, 1.0, bins + 1)
        idx = np.clip(np.digitize(conf, edges[1:-1]), 0, bins - 1)
        groups = [np.where(idx == b)[0] for b in range(bins) if np.any(idx == b)]
    n = len(y)
    return float(
        sum(len(g) / n * abs(correct[g].mean() - conf[g].mean()) for g in groups)
    )


def coverage_at_risk(probs: np.ndarray, y: np.ndarray, max_risk: float) -> float:
    """
    Largest share answered by a confidence threshold within ``max_risk``.
    Equal-confidence items are answered together; 0.0 when no threshold qualifies.
    """
    _check(probs, y)
    if not 0 <= max_risk <= 1:
        raise ValueError("max_risk must be between zero and one")
    confidence = probs.max(axis=1)
    order = np.argsort(-confidence, kind="stable")
    wrong = (probs.argmax(axis=1) != y)[order].astype(float)
    risk = np.cumsum(wrong) / np.arange(1, len(y) + 1)
    ordered_confidence = confidence[order]
    ends = np.r_[ordered_confidence[:-1] != ordered_confidence[1:], True]
    ok = np.where((risk <= max_risk) & ends)[0]
    return float((ok[-1] + 1) / len(y)) if len(ok) else 0.0


def cluster_bootstrap(
    stat: Callable[[np.ndarray], float],
    groups: Sequence[str],
    *,
    n_boot: int = 2000,
    seed: int = 20261008,
    level: float = 0.95,
) -> tuple[float, float]:
    """
    Percentile interval for ``stat(index_array)``, resampling whole groups
    with replacement rather than treating items from one paper as independent.
    """
    labels = np.asarray(groups)
    if not len(labels) or n_boot < 1 or not 0 < level < 1:
        raise ValueError(
            "bootstrap needs groups, positive replicates and 0 < level < 1"
        )
    unique = np.unique(labels)
    members = {g: np.where(labels == g)[0] for g in unique}
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n_boot):
        chosen = rng.choice(unique, size=len(unique), replace=True)
        value = stat(np.concatenate([members[g] for g in chosen]))
        if not np.isfinite(value):
            raise ValueError(
                "bootstrap statistic is undefined in a resampled cluster set"
            )
        values.append(value)
    lo, hi = np.quantile(values, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi)


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float:
    """Chance-corrected agreement between two annotators over the same items."""
    if len(a) != len(b) or not a:
        raise ValueError("annotations must be the same non-zero length")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    labels = set(a) | set(b)
    expected = sum((a.count(c) / n) * (b.count(c) / n) for c in labels)
    if expected == 1.0:
        return float("nan")
    return (observed - expected) / (1 - expected)
