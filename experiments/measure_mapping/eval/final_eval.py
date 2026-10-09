"""Read a sealed test set once per frozen system and report clustered intervals."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from measure_mapping import data, metrics


def _group_f1(
    probs: np.ndarray, y: np.ndarray, classes: list[str], prefix: str
) -> float:
    pred = probs.argmax(axis=1)
    values = []
    for index, name in enumerate(classes):
        if not name.startswith(prefix):
            continue
        tp = int(np.sum((pred == index) & (y == index)))
        denominator = int(np.sum(pred == index) + np.sum(y == index))
        if denominator:
            values.append(2 * tp / denominator)
    return float(np.mean(values)) if values else float("nan")


def _statistics(
    probs: np.ndarray, y: np.ndarray, classes: list[str], threshold: float | None
) -> dict[str, float]:
    confidence = probs.max(axis=1)
    wrong = probs.argmax(axis=1) != y
    answered = (
        confidence >= threshold
        if threshold is not None
        else np.zeros(len(y), dtype=bool)
    )
    return {
        "accuracy": metrics.accuracy(probs, y),
        "macro_f1": metrics.macro_f1(probs, y),
        "macro_f1_S": _group_f1(probs, y, classes, "S"),
        "macro_f1_E": _group_f1(probs, y, classes, "E"),
        "nll": metrics.nll(probs, y),
        "brier": metrics.brier(probs, y),
        "ece_equal_width": metrics.ece(probs, y),
        "ece_equal_mass": metrics.ece(probs, y, equal_mass=True),
        "coverage_at_5pct_risk": metrics.coverage_at_risk(probs, y, 0.05),
        "coverage_at_10pct_risk": metrics.coverage_at_risk(probs, y, 0.10),
        "selective_coverage": float(answered.mean()),
        "selective_error": float(wrong[answered].mean())
        if answered.any()
        else float("nan"),
        "confident_wrong_rate": float(np.mean(wrong & answered)),
    }


def evaluate_once(
    test_path: Path,
    lock_path: Path,
    *,
    revision: str,
    classes: list[str],
    predict: Callable[[list[str]], np.ndarray],
    exposure: list[dict],
    threshold: float | None,
    runs: Path,
    calibration_digest: str | None = None,
    n_boot: int = 2000,
    seed: int = 20261008,
) -> dict:
    if (
        not revision.strip()
        or len(set(classes)) != len(classes)
        or "none" not in classes
    ):
        raise data.DatasetError(
            "a frozen revision and unique classes including none are required"
        )
    if threshold is not None and not 0 <= threshold <= 1:
        raise data.DatasetError(
            "a confidence threshold must be in [0, 1] or abstain-all"
        )
    digest = lock_path.read_text().strip()
    runs.mkdir(parents=True, exist_ok=True)
    revision_hash = hashlib.sha256(revision.encode()).hexdigest()
    reservation = runs / f".test-read-{revision_hash}.json"
    try:
        with reservation.open("x") as file:
            record = {
                "revision": revision,
                "testDigest": digest,
                "readAt": datetime.now(UTC).isoformat(),
            }
            file.write(json.dumps(record) + "\n")
    except FileExistsError as exc:
        raise data.DatasetError(
            "this frozen revision has already read the test set"
        ) from exc
    with (runs / "test_reads.log").open("a") as file:
        file.write(json.dumps(record) + "\n")
    rows = [
        json.loads(line) for line in test_path.read_text().splitlines() if line.strip()
    ]
    if data.lock_digest(rows) != digest:
        raise data.DatasetError("test digest does not match the frozen lock")
    rows = data.validate_rows(rows, set(classes) - {"none"})
    if ({row["id"] for row in rows} & {row["id"] for row in exposure}) or (
        {row["group"] for row in rows} & {row["group"] for row in exposure}
    ):
        raise data.DatasetError(
            "test ids or source groups overlap training/calibration"
        )
    if data.leaky_pairs(
        {row["id"]: row["text"] for row in [*exposure, *rows]},
        {
            **{row["id"]: "exposed" for row in exposure},
            **{row["id"]: "test" for row in rows},
        },
    ):
        raise data.DatasetError("test wording leaks into training/calibration")
    if len(rows) < 100 or sum(row["source"] == "paper" for row in rows) < 100:
        raise data.DatasetError(
            "comparison requires at least 100 independent real test items"
        )
    for row in rows:
        if (
            row.get("split") != "test"
            or row.get("adjudicated") is not True
            or row["provenance"] != "human-adjudicated"
            or not row.get("annotator")
            or not row.get("annotator2")
            or row["annotator"] == row["annotator2"]
        ):
            raise data.DatasetError(
                "test truth needs independent, adjudicated human annotations"
            )
    groups = [row["group"] for row in rows]
    if len(set(groups)) < 2:
        raise data.DatasetError(
            "comparison needs at least two independent source clusters"
        )
    probs = np.asarray(predict([row["text"] for row in rows]), dtype=float)
    if probs.shape != (len(rows), len(classes)):
        raise data.DatasetError("prediction columns must match the frozen class order")
    y = np.array([classes.index(row["label"]) for row in rows])
    values = _statistics(probs, y, classes, threshold)
    estimates = {}
    # Bootstrap the same source resamples for every metric, without recomputing
    # the whole metric table once per metric per replicate.
    samples = {name: [] for name in values}
    rng = np.random.default_rng(seed)
    group_names = sorted(set(groups))
    members = {
        group: np.flatnonzero(np.array(groups) == group) for group in group_names
    }
    if n_boot < 1:
        raise data.DatasetError("bootstrap replicates must be positive")
    for _ in range(n_boot):
        chosen = rng.choice(group_names, len(group_names), replace=True)
        idx = np.concatenate([members[group] for group in chosen])
        for name, value in _statistics(probs[idx], y[idx], classes, threshold).items():
            samples[name].append(value)
    for name, value in values.items():
        defined = math.isfinite(value)
        interval = (
            np.quantile(samples[name], [0.025, 0.975]).tolist()
            if defined and all(math.isfinite(sample) for sample in samples[name])
            else None
        )
        estimates[name] = {"value": value if defined else None, "ci": interval}
        if interval is None:
            estimates[name]["interval_reason"] = (
                "statistic undefined in this data or a cluster resample"
            )
    result = {
        "revision": revision,
        "testDigest": digest,
        "calibrationDigest": calibration_digest,
        "threshold": threshold,
        "classes": classes,
        "items": len(rows),
        "sourceClusters": len(group_names),
        "seed": seed,
        "bootstrapReplicates": n_boot,
        "classCounts": {
            name: int(np.sum(y == index)) for index, name in enumerate(classes)
        },
        "metrics": estimates,
    }
    (runs / f"{revision_hash}.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    return result
