"""Sample-size planning: the power/sensitivity curve (P2-2).

A planning tool, not a result: given the study's planned primary comparison
(a two-sample t-test over the two conditions, the pilot protocol's shape),
how does power move with per-group n, and what n does a target power need
per plausible effect size?

The exact non-central t distribution does the work — no normal
approximation, no simulation, deterministic for any fixed inputs. Honesty
notes that travel with the numbers:

- The model is the two-sample t-test with equal per-group n. The
  statistics module runs nonparametric tests on actual data, but *planning*
  power for a nonparametric test needs an assumed distribution; the t-test
  power is the standard planning instrument and the ethics package should
  say so.
- Every curve carries its alpha and target explicitly — never a bare
  "you need N=64".
- ``requiredN`` entries say whether the target is *reached within the
  explored range*; a "no" means the target needs more participants than
  the range examined, which is information, not a failure.
"""

from __future__ import annotations

from collections.abc import Iterable

from scipy import stats as sps

#: The conventional planning targets the platform's power panel shows by
#: default (small / medium / large, Cohen's d).
DEFAULT_EFFECT_SIZES = (0.2, 0.5, 0.8)
DEFAULT_ALPHA = 0.05
DEFAULT_POWER_TARGET = 0.8
DEFAULT_MAX_TOTAL_N = 120


def _validate(alpha: float, power_target: float, max_total_n: int) -> None:
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha!r}")
    if not 0.0 < power_target < 1.0:
        raise ValueError(f"power_target must be in (0, 1), got {power_target!r}")
    if max_total_n < 4:
        raise ValueError(f"max_total_n must be >= 4, got {max_total_n!r}")


def _power_at(n_per_group: int, d: float, alpha: float) -> float:
    """Exact power of a two-sample t-test (equal groups, two-sided) via the
    non-central t distribution."""
    df = 2 * n_per_group - 2
    noncentrality = d * (n_per_group / 2) ** 0.5
    t_crit = sps.t.ppf(1.0 - alpha / 2.0, df)
    return float(
        sps.nct.sf(t_crit, df, noncentrality) + sps.nct.cdf(-t_crit, df, noncentrality)
    )


def two_sample_power_curve(
    effect_sizes: Iterable[float] = DEFAULT_EFFECT_SIZES,
    *,
    alpha: float = DEFAULT_ALPHA,
    power_target: float = DEFAULT_POWER_TARGET,
    max_total_n: int = DEFAULT_MAX_TOTAL_N,
) -> dict:
    """The power/sensitivity curve as JSON-friendly planning data.

    Returns a dict with the model statement, the explored parameters, one
    ``curves`` entry per effect size (power at every per-group n from 2 up
    to ``max_total_n // 2``), and one ``requiredN`` entry per effect size
    (the first n at which power reaches the target, or ``None`` if the
    range is too small). Deterministic: same inputs, same numbers.
    """
    sizes = [float(d) for d in effect_sizes]
    if not sizes:
        raise ValueError("at least one effect size is required")
    if any(d <= 0 or d != d for d in sizes):
        raise ValueError(f"effect sizes must be positive numbers, got {effect_sizes!r}")
    _validate(alpha, power_target, max_total_n)

    max_per_group = max_total_n // 2
    ns = list(range(2, max_per_group + 1))
    curves: list[dict] = []
    required: list[dict] = []
    for d in sizes:
        powers = [_power_at(n, d, alpha) for n in ns]
        curves.append(
            {
                "effectSize": d,
                "points": [
                    {"nPerGroup": n, "totalN": 2 * n, "power": round(p, 6)}
                    for n, p in zip(ns, powers, strict=True)
                ],
            }
        )
        reached = next(
            ((n, p) for n, p in zip(ns, powers, strict=True) if p >= power_target), None
        )
        required.append(
            {
                "effectSize": d,
                "nPerGroup": reached[0] if reached else None,
                "totalN": 2 * reached[0] if reached else None,
                "powerAtTargetN": round(reached[1], 6) if reached else None,
                "reachesTarget": reached is not None,
            }
        )

    return {
        "model": ("two-sample t-test, independent means, equal per-group n, two-sided"),
        "alpha": alpha,
        "powerTarget": power_target,
        "maxTotalN": max_total_n,
        "curves": curves,
        "requiredN": required,
    }
