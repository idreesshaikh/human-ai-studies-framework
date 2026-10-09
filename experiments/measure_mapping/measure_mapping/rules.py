"""B1: a training-only keyword baseline using multinomial Naive Bayes."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from itertools import pairwise


def tokens(text: str) -> list[str]:
    """Lower-cased words plus adjacent word pairs."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return words + [f"{a}_{b}" for a, b in pairwise(words)]


class KeywordModel:
    """Smoothed class-conditional token counts, including the ``none`` class."""

    def __init__(self, alpha: float = 0.5):
        if alpha <= 0:
            raise ValueError("alpha must be positive")
        self.alpha = alpha
        self.class_counts: Counter[str] = Counter()
        self.token_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.vocab: set[str] = set()

    def fit(self, rows: list[dict]) -> KeywordModel:
        if not rows:
            raise ValueError("no training rows")
        for row in rows:
            self.class_counts[row["label"]] += 1
            for tok in tokens(row["text"]):
                self.token_counts[row["label"]][tok] += 1
                self.vocab.add(tok)
        return self

    @property
    def classes(self) -> list[str]:
        return sorted(self.class_counts)

    def predict_proba(self, text: str) -> dict[str, float]:
        total_rows = sum(self.class_counts.values())
        scores = {}
        for cls in self.classes:
            denom = sum(self.token_counts[cls].values()) + self.alpha * (
                len(self.vocab) + 1
            )
            logp = math.log(self.class_counts[cls] / total_rows)
            for tok in tokens(text):
                logp += math.log((self.token_counts[cls][tok] + self.alpha) / denom)
            scores[cls] = logp
        top = max(scores.values())
        exp = {c: math.exp(s - top) for c, s in scores.items()}
        z = sum(exp.values())
        return {c: v / z for c, v in exp.items()}
