"""Reproducible power planning. Pure functions; effect/SD units are explicit.

Normal: location shift in SD units; paired SD is the SD of differences.
Log-normal: effect/SD are on the log scale. Ordinal: latent normal shift,
cut at equally spaced quantiles into the declared number of categories.
Period/order effects use the same scale as the shift; no carryover model.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
from scipy import stats

from analysis.power import _paired_power_at, _power_at
from analysis.stats import wilcoxon_pvalues


@dataclass(frozen=True)
class PlanInput:
    design: str = "between-subjects"
    test: str = "mann-whitney"
    distribution: str = "normal"
    effect: float = 0.5
    sd: float = 1.0
    alpha: float = 0.05
    target_power: float = 0.8
    dropout: float = 0.0
    covariate_correlation: float = 0.0
    period_effect: float = 0.0
    order_effect: float = 0.0
    counterbalanced: bool = True
    planned_n: int = 40
    max_n: int = 400
    simulations: int = 1000
    seed: int = 20261007
    ordinal_levels: int = 7

    def validate(self) -> None:
        numeric = (
            self.effect,
            self.sd,
            self.alpha,
            self.target_power,
            self.dropout,
            self.covariate_correlation,
            self.period_effect,
            self.order_effect,
        )
        if not all(math.isfinite(v) for v in numeric):
            raise ValueError("All assumptions must be finite numbers")
        if self.effect <= 0 or self.sd <= 0:
            raise ValueError("effect and sd must be positive")
        if not 0 < self.alpha < 1 or not 0 < self.target_power < 1:
            raise ValueError("alpha and target_power must lie strictly between 0 and 1")
        if not 0 <= self.dropout < 1 or not -0.95 <= self.covariate_correlation <= 0.95:
            raise ValueError(
                "dropout must be in [0,1); covariate correlation in [-.95,.95]"
            )
        if not 4 <= self.planned_n <= 1000 or not 4 <= self.max_n <= 1000:
            raise ValueError("planned_n and max_n must be between 4 and 1000")
        if not 200 <= self.simulations <= 10000 or not 2 <= self.ordinal_levels <= 11:
            raise ValueError("simulations must be 200–10000; ordinal_levels 2–11")
        if not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("seed must be an unsigned 32-bit integer")
        if self.design == "crossover":
            raise ValueError(
                "Crossover with period/order regression is not "
                "supported by the analysis recipes; no sample size is "
                "reported"
            )
        if self.design not in {"between-subjects", "within-subjects"}:
            raise ValueError("Unsupported design")
        allowed = {
            "between-subjects": {"two-sample-t", "mann-whitney"},
            "within-subjects": {"paired-t", "wilcoxon"},
        }
        if self.test not in allowed[self.design]:
            raise ValueError("The planned test does not support this design")
        if self.distribution not in {"normal", "log-normal", "ordinal"}:
            raise ValueError("Unsupported outcome distribution")
        if self.covariate_correlation and self.test != "two-sample-t":
            raise ValueError(
                "Covariate adjustment is supported only for between-subjects ANCOVA"
            )
        if self.test in {"two-sample-t", "paired-t"} and (
            self.distribution not in {"normal", "log-normal"}
            or self.period_effect
            or self.order_effect
        ):
            raise ValueError(
                "Analytic t planning requires normal outcomes (or normal "
                "log-transformed outcomes) and zero period/order effects"
            )
        if self.design == "between-subjects" and (
            self.period_effect or self.order_effect
        ):
            raise ValueError("Period/order effects apply only to within-subjects plans")
        if self.test == "wilcoxon" and self.distribution == "log-normal":
            raise ValueError(
                "Paired log-normal outcomes need a joint distribution; "
                "this combination is not supported"
            )


def simulate_power(plan: PlanInput, n: int, effect: float | None = None) -> dict:
    """Monte Carlo rejection rate with a Wilson interval; seed and n fix draws."""
    plan.validate()
    if n < 2:
        raise ValueError("n must be at least 2")
    d = (plan.effect if effect is None else effect) / plan.sd
    rng = np.random.default_rng(np.random.SeedSequence([plan.seed, n]))
    shape = (plan.simulations, n)
    a = rng.normal(size=shape)
    b = rng.normal(size=shape)
    if plan.design == "within-subjects":
        # The input SD describes differences, not marginal observations.
        signs = (
            np.where(np.arange(n) % 2, -1, 1) if plan.counterbalanced else np.ones(n)
        )
        differences = a + d + signs * plan.period_effect / plan.sd
        differences += (signs > 0) * plan.order_effect / plan.sd
        if plan.distribution == "ordinal":
            cuts = stats.norm.ppf(
                np.arange(1, plan.ordinal_levels) / plan.ordinal_levels
            )
            base = b
            a = np.digitize(base + differences / 2, cuts).astype(float)
            b = np.digitize(base - differences / 2, cuts).astype(float)
            differences = a - b
        p = wilcoxon_pvalues(differences)
    else:
        b = b + d
        if plan.distribution == "log-normal":
            # Ranking is invariant to exp; avoid overflow without changing the test.
            pass
        elif plan.distribution == "ordinal":
            cuts = stats.norm.ppf(
                np.arange(1, plan.ordinal_levels) / plan.ordinal_levels
            )
            a = np.digitize(a, cuts)
            b = np.digitize(b, cuts)
        combined = np.sort(np.concatenate([a, b], axis=1), axis=1)
        exact = (
            ~np.any(np.diff(combined, axis=1) == 0, axis=1)
            if n <= 8
            else np.zeros(plan.simulations, dtype=bool)
        )
        p = np.ones(plan.simulations)
        for mask, method in ((exact, "exact"), (~exact, "asymptotic")):
            if mask.any():
                p[mask] = stats.mannwhitneyu(
                    a[mask], b[mask], axis=1, alternative="two-sided", method=method
                ).pvalue
    count = int(np.count_nonzero(p < plan.alpha))
    interval = stats.binomtest(count, plan.simulations).proportion_ci(method="wilson")
    return {
        "power": count / plan.simulations,
        "ci": [float(interval.low), float(interval.high)],
        "rejections": count,
    }


def power_at(plan: PlanInput, n: int, effect: float | None = None) -> dict:
    d = (plan.effect if effect is None else effect) / plan.sd
    if plan.test == "two-sample-t":
        # Standard ANCOVA variance reduction, an approximation for recruitment.
        p = _power_at(n, d / math.sqrt(1 - plan.covariate_correlation**2), plan.alpha)
    elif plan.test == "paired-t":
        p = _paired_power_at(n, d, plan.alpha)
    else:
        return simulate_power(plan, n, effect)
    return {"power": float(p), "ci": None}


def plan_study(plan: PlanInput, *, pilot: dict | None = None) -> dict:
    plan.validate()
    arms = 2 if plan.design == "between-subjects" else 1
    limit = plan.max_n // arms
    minimum = 2
    # Full analytic curves; bounded simulation curves plus integer search.
    ns = (
        list(range(minimum, limit + 1))
        if plan.test.endswith("-t")
        else sorted(
            set(np.linspace(minimum, limit, min(20, limit - 1), dtype=int).tolist())
        )
    )
    cache: dict[int, dict] = {}

    def at(n: int) -> dict:
        if n not in cache:
            cache[n] = power_at(plan, n)
        return cache[n]

    for n in ns:
        at(n)
    reached = next((n for n in ns if at(n)["power"] >= plan.target_power), None)
    if reached is not None and not plan.test.endswith("-t"):
        low = max((n for n in ns if n < reached), default=minimum - 1)
        high = reached
        while high - low > 1:
            mid = (low + high) // 2
            if at(mid)["power"] >= plan.target_power:
                high = mid
            else:
                low = mid
        reached = high
    sensitivity = []
    for total in sorted(
        {max(4, plan.planned_n // 2), plan.planned_n, min(1000, plan.planned_n * 2)}
    ):
        n = total // arms
        low, high = 0.0, plan.sd * 8
        supported = power_at(plan, n, high)["power"] >= plan.target_power
        if supported:
            for _ in range(12):
                mid = (low + high) / 2
                if power_at(plan, n, mid)["power"] >= plan.target_power:
                    high = mid
                else:
                    low = mid
        sensitivity.append(
            {
                "totalN": n * arms,
                "smallestDetectableEffect": high if supported else None,
            }
        )
    warnings = ["A plan based on assumptions is a hypothesis, not evidence."]
    if not plan.test.endswith("-t"):
        warnings.append(
            "Monte Carlo estimates can fluctuate across n; sample "
            "size is an estimate, with the displayed simulation "
            "interval."
        )
    if plan.distribution == "ordinal":
        warnings.append(
            "Ordinal effects are latent normal shifts, not observed "
            "Likert point differences."
        )
    if plan.covariate_correlation:
        warnings.append(
            "ANCOVA uses the approximate variance factor 1 − rho²; "
            "the declared covariate must be recorded before "
            "treatment."
        )
    if plan.design == "within-subjects":
        warnings.append(
            "SD refers to participant differences. Period/order "
            "shifts are simulated; carryover and mixed models are "
            "unsupported."
        )
        if not plan.counterbalanced:
            warnings.append(
                "Fixed order confounds condition and period; the "
                "planner cannot separate them."
            )
    null_power = None
    if not plan.test.endswith("-t"):
        null_power = simulate_power(plan, max(2, plan.planned_n // arms), 0)
        if null_power["ci"][0] > plan.alpha:
            warnings.append(
                "The simulated null rejection rate exceeds nominal "
                "alpha: these period/order assumptions may create false "
                "positives. Change the design before interpreting this "
                "plan."
            )
    required_withheld = None
    if reached is not None and not plan.test.endswith("-t"):
        null_at_required = simulate_power(plan, reached, 0)
        if null_at_required["ci"][0] > plan.alpha:
            # Bias-driven rejections would otherwise count as power and make a flawed
            # design look cheaper than a sound one.
            required_withheld = {
                "code": "inflated-null-rejection",
                "message": (
                    "No sample size is reported: at the size that would reach the "
                    "target, the simulated null rejection rate exceeds nominal alpha, "
                    "so these period/order assumptions would produce false positives. "
                    "Change the design (balance the order) before planning."
                ),
                "nullRejection": null_at_required,
            }
            reached = None
    if pilot:
        warnings.extend(pilot.get("warnings", []))
    required = (
        None
        if reached is None
        else {
            "nPerArm": reached,
            "totalN": reached * arms,
            "recruitPerArm": math.ceil(reached / (1 - plan.dropout)),
            "recruitTotal": math.ceil(reached / (1 - plan.dropout)) * arms,
            "power": at(reached)["power"],
            "ci": at(reached)["ci"],
        }
    )
    return {
        "inputs": asdict(plan),
        "basis": "pilot-data" if pilot else "assumptions",
        "method": "analytic" if plan.test.endswith("-t") else "simulation",
        "effectUnits": "latent SD"
        if plan.distribution == "ordinal"
        else "log units"
        if plan.distribution == "log-normal"
        else "outcome units (paired difference SD for within-subjects)",
        "required": required,
        "requiredWithheld": required_withheld,
        "curve": [{"totalN": n * arms, "nPerArm": n, **at(n)} for n in sorted(cache)],
        "sensitivity": sensitivity,
        "warnings": warnings,
        "pilot": pilot,
        "nullPower": null_power,
    }


def estimate_variance(values: list[float]) -> dict:
    """Normal-theory variance CI for independent participant summaries."""
    vals = np.asarray(values, dtype=float)
    if len(vals) < 2 or not np.isfinite(vals).all():
        raise ValueError(
            "At least two finite independent participant outcomes are required"
        )
    variance = float(np.var(vals, ddof=1))
    if variance <= 0:
        raise ValueError("Pilot variance is zero; a sample size cannot be estimated")
    df = len(vals) - 1
    ci = [
        float(df * variance / stats.chi2.ppf(0.975, df)),
        float(df * variance / stats.chi2.ppf(0.025, df)),
    ]
    return {
        "participants": len(vals),
        "variance": variance,
        "sd": math.sqrt(variance),
        "varianceCI": ci,
        "sdCI": [math.sqrt(x) for x in ci],
        "actionable": len(vals) >= 8,
        "warnings": (
            [
                "Fewer than 8 pilot participants: the variance interval "
                "is too wide to act on."
            ]
            if len(vals) < 8
            else []
        )
        + [
            "Variance intervals assume independent normal "
            "participant summaries; they do not include uncertainty "
            "in the effect assumption."
        ],
    }


def compatibility_curve(
    effect_sizes,
    *,
    design="between-subjects",
    test=None,
    alpha=0.05,
    power_target=0.8,
    max_total_n=120,
    counterbalanced=True,
):
    """Old wire shape, same planner engine. Unsaved exploratory assumptions."""
    test = test or ("paired-t" if design == "within-subjects" else "two-sample-t")
    sizes = list(effect_sizes)
    if not sizes or len(sizes) > 6:
        raise ValueError("Provide between one and six effect sizes")
    curves, required = [], []
    for effect in sizes:
        result = plan_study(
            PlanInput(
                design=design,
                test=test,
                effect=effect,
                alpha=alpha,
                target_power=power_target,
                max_n=max_total_n,
                counterbalanced=counterbalanced,
            )
        )
        curves.append(
            {
                "effectSize": effect,
                "points": [
                    {
                        "nPerGroup": p["nPerArm"],
                        "totalN": p["totalN"],
                        "power": round(p["power"], 6),
                    }
                    for p in result["curve"]
                ],
            }
        )
        req = result["required"]
        required.append(
            {
                "effectSize": effect,
                "nPerGroup": req["nPerArm"] if req else None,
                "totalN": req["totalN"] if req else None,
                "powerAtTargetN": req["power"] if req else None,
                "reachesTarget": req is not None,
            }
        )
    names = {
        "two-sample-t": "two-sample t-test",
        "paired-t": "paired t-test",
        "mann-whitney": "Mann-Whitney U simulation",
        "wilcoxon": "Wilcoxon signed-rank simulation",
    }
    return {
        "model": names[test],
        "assumption": "Exploratory standardized normal shifts, not observed findings.",
        "alpha": alpha,
        "powerTarget": power_target,
        "maxTotalN": max_total_n,
        "curves": curves,
        "requiredN": required,
    }
