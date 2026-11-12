"""
Non-compliance simulation: what broken AI conditions do to a between-subjects study.

Given how often participants break their assigned AI condition and how well telemetry
flags actual use, how biased are three analyses against the true effect of *using* AI
(``effect_d``, in SD units), and how many participants does each need?

Data model (per replicate)::

    skill ~ N(0, 1)
    y     = effect_d * used_ai + 0.7 * skill + sqrt(0.51) * N(0, 1)

so ``sd(y)`` is 1 at fixed ``used_ai`` and ``effect_d`` is in SD units.

Treatment-arm members use AI unless they are non-users; control-arm members use AI
only if they violate. ``random`` draws violators and non-users independently;
``skill-linked`` makes the lowest-skill ``control_violation`` fraction of controls
violate and the highest-skill ``treatment_nonuse`` fraction of the treated arm not use
AI. The telemetry flag is ``Bernoulli(sensitivity)`` for people who used AI and
``Bernoulli(1 - specificity)`` for people who did not.

Estimators (all Welch's t, target ``effect_d``):

* ``itt``: arms by assignment.
* ``exclude-detected``: as published studies exclude, drop only the control-arm
  participants flagged as AI users, then compare the arms. Treated participants are
  never dropped (non-use in the treated arm is what ``as-detected`` addresses). With
  nobody flagged (for example sensitivity 0 and specificity 1) it reduces to ``itt``.
* ``as-detected``: flagged users against non-flagged people, across both arms.

``refused`` counts replicates where an estimator's comparison had a group with fewer
than two people (or no variance to estimate from); those replicates are left out of
that estimator's bias, coverage and power. When every replicate is refused the three
metrics are ``None``. Outputs never contain NaN.

``power`` is the share of replicates whose two-sided Welch test rejects "no difference"
at ``alpha``. It is not the power to recover the true effect when the estimator is
biased.

Everything is vectorised over replicates. Arrays are shaped ``(people, replicates)``
and each random variable has its own stream, so for a fixed seed the first ``n`` people
are identical whatever the arm size is (common random numbers). Memory scales with
``n_per_arm * reps`` (about 8 float64 arrays of that size per arm).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from numbers import Integral, Real
from typing import Literal

import numpy as np
from scipy import stats as sps

DEFAULT_SEED = 20261112
ESTIMATORS = ("itt", "exclude-detected", "as-detected")
SKILL_LOADING = 0.7
NOISE_SD = math.sqrt(1.0 - SKILL_LOADING**2)  # sqrt(0.51): sd(y | used_ai) = 1

_ROUTES = (
    "copilot-inline",
    "copilot-chat",
    "browser-paste",
    "retype",
    "cli-agent-hooks",
    "cli-agent-no-hooks",
)
MIXES: dict[str, dict[str, float]] = {
    "instruction-only": {route: 1 / len(_ROUTES) for route in _ROUTES},
    "locked-environment": {"browser-paste": 0.5, "retype": 0.5},
}

_STREAMS = (
    "skill_t",
    "noise_t",
    "skill_c",
    "noise_c",
    "u_nonuse",
    "u_viol",
    "u_flag_t",
    "u_flag_c",
)


@dataclass(frozen=True)
class Scenario:
    effect_d: float
    n_per_arm: int
    control_violation: float
    treatment_nonuse: float
    mechanism: Literal["random", "skill-linked"]
    sensitivity: float
    specificity: float
    alpha: float = 0.05

    def __post_init__(self) -> None:
        if not isinstance(self.effect_d, Real) or not math.isfinite(self.effect_d):
            raise ValueError(f"effect_d must be a finite number, got {self.effect_d!r}")
        for name in (
            "control_violation",
            "treatment_nonuse",
            "sensitivity",
            "specificity",
        ):
            value = getattr(self, name)
            if not isinstance(value, Real) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value!r}")
        if self.control_violation > 0.5:
            raise ValueError(
                f"control_violation must be at most 0.5, got {self.control_violation!r}"
            )
        if (
            not isinstance(self.n_per_arm, Integral)
            or isinstance(self.n_per_arm, bool)
            or self.n_per_arm < 4
        ):
            raise ValueError(
                f"n_per_arm must be an integer >= 4, got {self.n_per_arm!r}"
            )
        if self.mechanism not in ("random", "skill-linked"):
            raise ValueError(
                f"mechanism must be 'random' or 'skill-linked', got {self.mechanism!r}"
            )
        if not isinstance(self.alpha, Real) or not 0.0 < self.alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {self.alpha!r}")


def _draw_inputs(n: int, reps: int, seed: int) -> dict[str, np.ndarray]:
    """
    Raw random inputs, one independent stream per variable, shaped ``(n, reps)``.

    Row-major filling along the first axis means ``_draw_inputs(m, ...)`` is exactly the
    first ``m`` rows of ``_draw_inputs(n, ...)`` for ``m <= n``, so sample-size searches
    reuse the same people (common random numbers).
    """
    children = np.random.SeedSequence(seed).spawn(len(_STREAMS))
    out: dict[str, np.ndarray] = {}
    for name, child in zip(_STREAMS, children, strict=True):
        rng = np.random.Generator(np.random.PCG64(child))
        if name.startswith("u_"):
            out[name] = rng.random((n, reps))
        else:
            out[name] = rng.standard_normal((n, reps))
    return out


def _extreme_mask(skill: np.ndarray, rate: float, *, lowest: bool) -> np.ndarray:
    """Per replicate, mark the ``rate`` fraction with the lowest/highest skill."""
    n = skill.shape[0]
    k = math.floor(rate * n + 0.5)
    mask = np.zeros(skill.shape, dtype=bool)
    if k == 0:
        return mask
    order = np.argsort(skill, axis=0)
    chosen = order[:k] if lowest else order[n - k :]
    np.put_along_axis(mask, chosen, True, axis=0)
    return mask


def _welch_masked(
    y: np.ndarray, g1: np.ndarray, g0: np.ndarray, alpha: float
) -> tuple[np.ndarray, ...]:
    """
    Welch's t comparison of group 1 minus group 0, per replicate (column).

    ``y`` is ``(rows, reps)``; ``g1``/``g0`` are boolean masks (broadcastable to ``y``)
    that pick each group's rows in every replicate. Returns ``(estimate, ci_low,
    ci_high, p_value, valid)``; entries where ``valid`` is False (a group below two
    people, or no variance) are NaN and must be ignored. Matches
    ``scipy.stats.ttest_ind(equal_var=False)`` and its ``confidence_interval``.
    """
    y = y - y.mean(axis=0)  # conditioning only; differences are unaffected
    ysq = y * y
    g1 = np.broadcast_to(g1, y.shape)
    g0 = np.broadcast_to(g0, y.shape)

    def moments(g: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        count = g.sum(axis=0).astype(float)
        total = (y * g).sum(axis=0)
        squares = (ysq * g).sum(axis=0)
        with np.errstate(divide="ignore", invalid="ignore"):
            mean = total / count
            var = np.maximum((squares - count * mean * mean) / (count - 1.0), 0.0)
        return count, mean, var

    n1, m1, v1 = moments(g1)
    n0, m0, v0 = moments(g0)
    with np.errstate(divide="ignore", invalid="ignore"):
        q1, q0 = v1 / n1, v0 / n0
        se2 = q1 + q0
        valid = (n1 >= 2) & (n0 >= 2) & np.isfinite(se2) & (se2 > 0)
        df = se2 * se2 / (q1 * q1 / (n1 - 1.0) + q0 * q0 / (n0 - 1.0))
    valid &= np.isfinite(df)

    safe_df = np.where(valid, df, 1.0)
    safe_se = np.where(valid, np.sqrt(np.where(valid, se2, 1.0)), 1.0)
    est = np.where(valid, m1 - m0, np.nan)
    half = sps.t.ppf(1.0 - alpha / 2.0, safe_df) * safe_se
    t_stat = np.where(valid, m1 - m0, 0.0) / safe_se
    p = 2.0 * sps.t.sf(np.abs(t_stat), safe_df)
    return (
        est,
        np.where(valid, est - half, np.nan),
        np.where(valid, est + half, np.nan),
        np.where(valid, p, np.nan),
        valid,
    )


def _summarise(
    result: tuple[np.ndarray, ...], effect_d: float, alpha: float, reps: int
) -> dict[str, float | int | None]:
    est, lo, hi, p, valid = result
    kept = int(valid.sum())
    refused = reps - kept
    if kept == 0:
        return {"bias": None, "coverage": None, "power": None, "refused": refused}
    return {
        "bias": float(np.mean(est[valid] - effect_d)),
        "coverage": float(np.mean((lo[valid] <= effect_d) & (effect_d <= hi[valid]))),
        "power": float(np.mean(p[valid] < alpha)),
        "refused": refused,
    }


def _simulate_data(s: Scenario, reps: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Outcomes and telemetry flags for every person in every replicate.

    Both arrays are ``(2 * n_per_arm, reps)``; the first ``n_per_arm`` rows are the
    treated arm and the rest the control arm.
    """
    n = int(s.n_per_arm)
    draws = _draw_inputs(n, reps, seed)

    if s.mechanism == "random":
        violates = draws["u_viol"] < s.control_violation
        nonuse = draws["u_nonuse"] < s.treatment_nonuse
    else:
        violates = _extreme_mask(draws["skill_c"], s.control_violation, lowest=True)
        nonuse = _extreme_mask(draws["skill_t"], s.treatment_nonuse, lowest=False)
    used_t = ~nonuse
    used_c = violates

    y_t = (
        s.effect_d * used_t
        + SKILL_LOADING * draws["skill_t"]
        + NOISE_SD * draws["noise_t"]
    )
    y_c = (
        s.effect_d * used_c
        + SKILL_LOADING * draws["skill_c"]
        + NOISE_SD * draws["noise_c"]
    )
    flag_t = np.where(
        used_t,
        draws["u_flag_t"] < s.sensitivity,
        draws["u_flag_t"] < 1.0 - s.specificity,
    )
    flag_c = np.where(
        used_c,
        draws["u_flag_c"] < s.sensitivity,
        draws["u_flag_c"] < 1.0 - s.specificity,
    )
    return np.concatenate([y_t, y_c]), np.concatenate([flag_t, flag_c])


def _comparison_masks(
    n: int, flagged: np.ndarray
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Group 1 and group 0 row masks per estimator (rows: treated, then control)."""
    treated = (np.arange(2 * n) < n)[:, None]
    control = ~treated
    return {
        "itt": (treated, control),
        # Only flagged controls are dropped; the treated arm is never touched.
        "exclude-detected": (treated, control & ~flagged),
        "as-detected": (flagged, ~flagged),
    }


def simulate(
    s: Scenario, reps: int = 2000, seed: int = DEFAULT_SEED
) -> dict[str, dict]:
    """
    Bias, coverage and "power" of each estimator for scenario ``s``.

    Returns ``{"itt" | "exclude-detected" | "as-detected": {"bias", "coverage",
    "power", "refused"}}``. Bias is the mean of (estimate - effect_d); coverage is how
    often the Welch CI at level ``1 - alpha`` contains ``effect_d``; ``power`` is the
    share of replicates rejecting "no difference" at ``alpha`` (not power to recover
    the true effect when the estimator is biased). Metrics are None when every
    replicate was refused.
    """
    if not isinstance(reps, Integral) or isinstance(reps, bool) or reps < 1:
        raise ValueError(f"reps must be a positive integer, got {reps!r}")
    reps = int(reps)
    y, flagged = _simulate_data(s, reps, int(seed))
    return {
        name: _summarise(_welch_masked(y, g1, g0, s.alpha), s.effect_d, s.alpha, reps)
        for name, (g1, g0) in _comparison_masks(int(s.n_per_arm), flagged).items()
    }


def required_n(
    s: Scenario,
    estimator: str,
    target: float = 0.8,
    reps: int = 1000,
    seed: int = DEFAULT_SEED,
    max_n: int = 2000,
) -> int | None:
    """
    Smallest ``n_per_arm`` in ``[4, max_n]`` at which ``estimator``'s power reaches
    ``target`` under scenario ``s`` (its ``n_per_arm`` is ignored), or None if it does
    not by ``max_n``. "Power" is the rejection share described in ``simulate``.
    Doubles from 4 until the target is met, then bisects, assuming power is monotone
    in n; the fixed seed reuses the same people at every n, so the curve is stable. A
    power that cannot be computed (every replicate refused) counts as not reaching the
    target.
    """
    if estimator not in ESTIMATORS:
        raise ValueError(f"estimator must be one of {ESTIMATORS}, got {estimator!r}")
    if not 0.0 < target < 1.0:
        raise ValueError(f"target must be in (0, 1), got {target!r}")
    if not isinstance(max_n, Integral) or isinstance(max_n, bool) or max_n < 4:
        raise ValueError(f"max_n must be an integer >= 4, got {max_n!r}")

    cache: dict[int, bool] = {}

    def reaches(n: int) -> bool:
        if n not in cache:
            power = simulate(replace(s, n_per_arm=n), reps, seed)[estimator]["power"]
            cache[n] = power is not None and power >= target
        return cache[n]

    lo, n = 3, 4  # lo is a virtual "fails" below the smallest allowed n
    while not reaches(n):
        if n >= max_n:
            return None
        lo, n = n, min(2 * n, int(max_n))
    hi = n
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if reaches(mid):
            hi = mid
        else:
            lo = mid
    return hi


def mixed_sensitivity(per_route: dict[str, float], mix: dict[str, float]) -> float:
    """Weighted mean of per-route sensitivities; the mix weights must sum to 1."""
    if not mix:
        raise ValueError("mix must name at least one route")
    for route, weight in mix.items():
        if not isinstance(weight, Real) or not math.isfinite(weight) or weight < 0:
            raise ValueError(
                f"mix weight for {route!r} must be non-negative, got {weight!r}"
            )
    if abs(sum(mix.values()) - 1.0) > 1e-9:
        raise ValueError(f"mix weights must sum to 1, got {sum(mix.values())!r}")
    missing = sorted(route for route in mix if route not in per_route)
    if missing:
        raise ValueError(f"mix names routes without a sensitivity: {missing}")
    total = 0.0
    for route, weight in mix.items():
        value = per_route[route]
        if not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError(
                f"sensitivity for {route!r} must be a finite number, got {value!r}"
            )
        total += weight * value
    return float(total)
