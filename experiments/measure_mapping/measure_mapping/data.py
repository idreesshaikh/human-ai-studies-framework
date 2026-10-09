"""Rows of the measure-mapping dataset: validation, and the split / lock rules."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections.abc import Iterable

SPLITS = ("train", "calibration", "test")
PROVENANCES = ("repo", "human", "human-adjudicated", "llm")
REQUIRED = ("id", "text", "label", "source", "provenance", "group")


class DatasetError(ValueError):
    """A row or a split breaks a rule of the experiment."""


def validate_rows(rows: Iterable[dict], classes: set[str]) -> list[dict]:
    """Check shape, labels (a catalog class or ``none``), unique ids and provenance."""
    out, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise DatasetError("each row must be an object")
        missing = [
            k for k in REQUIRED if not isinstance(row.get(k), str) or not row[k].strip()
        ]
        if missing:
            raise DatasetError(f"row {row.get('id')!r} is missing {missing}")
        if row["id"] in seen:
            raise DatasetError(f"duplicate id {row['id']!r}")
        seen.add(row["id"])
        if row["label"] != "none" and row["label"] not in classes:
            raise DatasetError(f"row {row['id']!r}: unknown label {row['label']!r}")
        if row["provenance"] not in PROVENANCES:
            raise DatasetError(
                f"row {row['id']!r}: unknown provenance {row['provenance']!r}"
            )
        if row["provenance"] in ("llm", "repo") and row.get("split") in (
            "calibration",
            "test",
        ):
            raise DatasetError(
                f"row {row['id']!r}: generated and repo seeds are training only"
            )
        out.append(row)
    return out


def assign_splits(
    groups: dict[str, str],
    *,
    seed: int,
    fractions: dict[str, float] | None = None,
) -> dict[str, str]:
    """
    Keep every item of a paper, template or paraphrase cluster in one split.
    Deterministic for a given seed and set of ids.
    """
    if fractions is None:
        fractions = {"train": 0.6, "calibration": 0.2, "test": 0.2}
    if (
        set(fractions) != set(SPLITS)
        or any(
            not math.isfinite(value) or not 0 <= value <= 1
            for value in fractions.values()
        )
        or abs(sum(fractions.values()) - 1.0) > 1e-9
    ):
        raise DatasetError(
            "fractions must name train, calibration and test and sum to 1"
        )
    members: dict[str, list[str]] = {}
    for item, group in groups.items():
        members.setdefault(group, []).append(item)
    names = sorted(members)
    random.Random(seed).shuffle(names)  # noqa: S311 - reproducible split
    total = len(groups)
    targets = {s: fractions[s] * total for s in SPLITS}
    filled = dict.fromkeys(SPLITS, 0)
    result: dict[str, str] = {}
    for group in names:
        # Fill the largest shortfall, preferring test on ties.
        split = max(reversed(SPLITS), key=lambda s: targets[s] - filled[s])
        for item in members[group]:
            result[item] = split
        filled[split] += len(members[group])
    return result


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def leaky_pairs(
    texts: dict[str, str], splits: dict[str, str], *, jaccard: float = 0.7
) -> list[tuple[str, str]]:
    """Find near-duplicate wording across splits."""
    ids = sorted(texts)
    toks = {i: _tokens(texts[i]) for i in ids}
    pairs = []
    for a_pos, a in enumerate(ids):
        for b in ids[a_pos + 1 :]:
            if splits[a] == splits[b] or not toks[a] or not toks[b]:
                continue
            if len(toks[a] & toks[b]) / len(toks[a] | toks[b]) >= jaccard:
                pairs.append((a, b))
    return pairs


def lock_digest(rows: Iterable[dict]) -> str:
    """SHA-256 of test (id, text, label) triples, sorted by id."""
    triples = sorted((r["id"], r["text"], r["label"]) for r in rows)
    return hashlib.sha256(
        json.dumps(triples, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def training_rows(rows: Iterable[dict], splits: dict[str, str]) -> list[dict]:
    """Read training/calibration rows; refuse any test rows."""
    rows = list(rows)
    offending = [r["id"] for r in rows if splits.get(r["id"]) == "test"]
    if offending:
        raise DatasetError(f"test rows were passed to training: {offending[:5]}")
    return [r for r in rows if splits.get(r["id"]) in ("train", "calibration")]
