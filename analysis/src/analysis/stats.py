"""Honest statistics for tiny samples (NFR-8)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sps

SMALL_N = 12


@dataclass(frozen=True)
class TestResult:
    """One comparison, formatted honestly (NFR-8)."""

    test: str
    statistic: float
    p: float
    effect_name: str
    effect: float
    n: dict[str, int]
    note: str = ""

    @property
    def small_n(self) -> bool:
        return not self.n or min(self.n.values()) < SMALL_N

    def line(self) -> str:
        """The one honest sentence recipes put in summaries and tables."""
        cells = ", ".join(f"{k} n={v}" for k, v in self.n.items())
        text = (
            f"{self.test}: statistic={self.statistic:g}, "
            f"{'exact p' if '(exact,' in self.test else 'p'}={self.p:.3f}, "
            f"{self.effect_name}={self.effect:+.2f} ({cells})"
        )
        if self.note:
            text += f"; {self.note}"
        if self.small_n:
            text += ". Small n: hypothesis-generating only, not confirmatory."
        return text

    def row(self) -> dict:
        """Table-friendly dict (one row per comparison)."""
        return {
            "test": self.test,
            "statistic": self.statistic,
            "p_value": self.p,
            "p_method": "exact" if "exact" in self.test.lower() else "asymptotic",
            "p_exact": self.p if "exact" in self.test.lower() else None,
            "effect_name": self.effect_name,
            "effect": self.effect,
            **{f"n_{k}": v for k, v in self.n.items()},
            "note": self.note,
        }


def cliffs_delta(a: list[float], b: list[float]) -> float:
    """Cliff's delta: P(a > b) - P(a < b) over all pairs."""
    if not a or not b:
        return float("nan")
    gt = sum(1 for x in a for y in b if x > y)
    lt = sum(1 for x in a for y in b if x < y)
    return (gt - lt) / (len(a) * len(b))


def mann_whitney_method(a, b) -> str:
    """Exact only for small untied continuous samples; ties use correction."""
    x, y = np.atleast_2d(a), np.atleast_2d(b)
    joined = np.sort(np.concatenate([x, y], axis=-1), axis=-1)
    tied = np.any(np.diff(joined, axis=-1) == 0)
    return "exact" if min(x.shape[-1], y.shape[-1]) <= 8 and not tied else "asymptotic"


def wilcoxon_pvalues(differences):
    """Identical zero/tie handling in the recipes and simulation."""
    arr = np.asarray(differences, dtype=float)
    rows = np.atleast_2d(arr)
    result = np.ones(len(rows))
    counts = np.count_nonzero(rows, axis=1)
    absolute = np.sort(np.where(rows == 0, np.inf, np.abs(rows)), axis=1)
    tied = np.any(
        (
            absolute
            == np.concatenate([np.full((len(rows), 1), -1), absolute[:, :-1]], axis=1)
        )
        & np.isfinite(absolute),
        axis=1,
    )
    exact = (counts > 0) & (counts <= 50) & ~tied
    for mask, method in ((exact, "exact"), ((counts > 0) & ~exact, "asymptotic")):
        if mask.any():
            values = np.where(rows[mask] == 0, np.nan, rows[mask])
            result[mask] = sps.wilcoxon(
                values,
                axis=1,
                alternative="two-sided",
                method=method,
                nan_policy="omit",
            ).pvalue
    return float(result[0]) if arr.ndim == 1 else result


def mann_whitney(a: list[float], b: list[float], labels: tuple[str, str]) -> TestResult:
    """Exact Mann-Whitney U with Cliff's delta (independent cells)."""
    method = mann_whitney_method(a, b)
    res = sps.mannwhitneyu(a, b, alternative="two-sided", method=method)
    return TestResult(
        test=f"Mann-Whitney U ({method}, two-sided)",
        statistic=float(res.statistic),
        p=float(res.pvalue),
        effect_name="Cliff's delta",
        effect=cliffs_delta(a, b),
        n={labels[0]: len(a), labels[1]: len(b)},
    )


def wilcoxon_paired(
    a: list[float], b: list[float], labels: tuple[str, str]
) -> TestResult:
    """Exact Wilcoxon signed-rank on paired values (within-subjects)."""
    diffs = [x - y for x, y in zip(a, b, strict=True)]
    nonzero = [d for d in diffs if d != 0]
    note = ""
    if len(nonzero) < len(diffs):
        note = f"{len(diffs) - len(nonzero)} zero difference(s) dropped"
    if not nonzero:
        return TestResult(
            test="Wilcoxon signed-rank (exact, two-sided)",
            statistic=float("nan"),
            p=1.0,
            effect_name="rank-biserial r",
            effect=0.0,
            n={labels[0]: len(a), labels[1]: len(b)},
            note="all paired differences are zero",
        )
    exact = len(nonzero) <= 50 and len({abs(d) for d in nonzero}) == len(nonzero)
    method = "exact" if exact else "asymptotic"
    res = sps.wilcoxon(nonzero, alternative="two-sided", method=method)
    ranks = sps.rankdata([abs(d) for d in nonzero])
    w_plus = sum(r for r, d in zip(ranks, nonzero, strict=True) if d > 0)
    w_minus = sum(r for r, d in zip(ranks, nonzero, strict=True) if d < 0)
    total = len(nonzero) * (len(nonzero) + 1) / 2
    return TestResult(
        test=f"Wilcoxon signed-rank ({method}, two-sided)",
        statistic=float(res.statistic),
        p=float(res.pvalue),
        effect_name="rank-biserial r",
        effect=(w_plus - w_minus) / total,
        n={labels[0]: len(a), labels[1]: len(b)},
        note=note,
    )


def fisher_2x2(
    table: list[list[int]], cells: dict[str, int], note: str = ""
) -> TestResult:
    """Fisher's exact test on a 2x2 count table (e.g. pass/fail x condition)."""
    odds, p = sps.fisher_exact(table, alternative="two-sided")
    return TestResult(
        test="Fisher's exact (two-sided)",
        statistic=float("nan"),
        p=float(p),
        effect_name="odds ratio",
        effect=float(odds),
        n=cells,
        note=note,
    )


def spearman(a: list[float], b: list[float], label: str) -> TestResult:
    """Spearman rank correlation (monotone association, small-n friendly)."""
    if len(set(a)) < 2 or len(set(b)) < 2:
        return TestResult(
            test="Spearman rank correlation",
            statistic=float("nan"),
            p=float("nan"),
            effect_name="rho",
            effect=float("nan"),
            n={label: len(a)},
            note="undefined - one input is constant",
        )
    res = sps.spearmanr(a, b)
    return TestResult(
        test="Spearman rank correlation",
        statistic=float(res.statistic),
        p=float(res.pvalue),
        effect_name="rho",
        effect=float(res.statistic),
        n={label: len(a)},
    )


def compare_by_condition(
    df: pd.DataFrame,
    value: str,
    conditions: tuple[str, str],
    participant: str = "participantId",
) -> TestResult:
    """The standard two-condition comparison, choosing the right test."""
    per = df.groupby([participant, "condition"])[value].mean().reset_index()
    wide = per.pivot(index=participant, columns="condition", values=value)
    for c in conditions:
        if c not in wide.columns:
            wide[c] = float("nan")
    paired = wide.dropna(subset=list(conditions))
    if len(paired) >= 2:
        res = wilcoxon_paired(
            paired[conditions[0]].tolist(),
            paired[conditions[1]].tolist(),
            labels=conditions,
        )
        return TestResult(
            **{
                **res.__dict__,
                "note": (res.note + "; " if res.note else "")
                + f"paired on {len(paired)} participant(s), per-participant means",
            }
        )
    a = wide[conditions[0]].dropna().tolist()
    b = wide[conditions[1]].dropna().tolist()
    res = mann_whitney(a, b, labels=conditions)
    return TestResult(
        **{
            **res.__dict__,
            "note": (res.note + "; " if res.note else "")
            + "unpaired cells (too few participants with both conditions), "
            "per-participant means",
        }
    )
