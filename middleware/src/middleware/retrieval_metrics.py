"""Ranking metrics for the frozen retrieval benchmark. Pure functions."""

from __future__ import annotations

import math


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float | None:
    """Share of the relevant refs found in the top k; None when nothing is relevant."""
    if k < 1:
        raise ValueError("k must be at least 1")
    if not relevant:
        return None
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float | None:
    """
    1/rank of the first relevant ref (0 if none returned); None if nothing
    relevant.
    """
    if not relevant:
        return None
    for position, ref in enumerate(ranked, start=1):
        if ref in relevant:
            return 1.0 / position
    return 0.0


def ndcg_at_k(ranked: list[str], grades: dict[str, int], k: int) -> float | None:
    """nDCG@k with graded relevance (gain 2**g - 1); None if no ref has a grade > 0."""
    if k < 1:
        raise ValueError("k must be at least 1")
    ideal = sorted((g for g in grades.values() if g > 0), reverse=True)[:k]
    if not ideal:
        return None
    dcg = sum(
        (2 ** grades.get(ref, 0) - 1) / math.log2(i + 2)
        for i, ref in enumerate(ranked[:k])
    )
    best = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / best


def mean(values: list[float | None]) -> float | None:
    """
    Mean over the cases where the metric is defined; None if it is defined
    nowhere.
    """
    defined = [v for v in values if v is not None]
    return sum(defined) / len(defined) if defined else None
