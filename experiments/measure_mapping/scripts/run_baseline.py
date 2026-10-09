"""Fit B0/B1/B2 on train, calibrate separately, then use the sealed evaluator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import numpy as np
from eval.final_eval import evaluate_once
from measure_mapping import data, metrics, rules
from scipy.optimize import minimize_scalar
from scipy.special import softmax


def _scale(probs: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probs, 1e-12, 1)) / temperature
    logits[probs == 0] = -np.inf
    return softmax(logits, axis=1)


def temperature_scale(probs: np.ndarray, y: np.ndarray) -> float:
    metrics.nll(probs, y)  # Validate before optimization.
    result = minimize_scalar(
        lambda log_t: metrics.nll(_scale(probs, float(np.exp(log_t))), y),
        bounds=(-4, 4),
        method="bounded",
    )
    if not result.success:
        raise ValueError("temperature calibration did not converge")
    return float(np.exp(result.x))


def select_threshold(
    probs: np.ndarray, y: np.ndarray, *, max_risk: float = 0.05
) -> float | None:
    metrics.nll(probs, y)
    if not 0 <= max_risk <= 1:
        raise ValueError("max_risk must lie between zero and one")
    confidence = probs.max(axis=1)
    wrong = probs.argmax(axis=1) != y
    for threshold in sorted(set(confidence)):
        answered = confidence >= threshold
        if wrong[answered].mean() <= max_risk:
            return float(threshold)
    return None


@dataclass(frozen=True)
class Baseline:
    raw_predict: Callable[[list[str]], np.ndarray]
    classes: list[str]
    temperature: float
    threshold: float | None

    def predict(self, texts: list[str]) -> np.ndarray:
        return _scale(self.raw_predict(texts), self.temperature)


def fit_baseline(
    kind: str, train: list[dict], calibration: list[dict], classes: list[str]
) -> Baseline:
    combined = train + calibration
    data.training_rows(combined, {row["id"]: row.get("split") for row in combined})
    data.validate_rows(combined, set(classes))
    if (
        not train
        or not calibration
        or "none" not in classes
        or len(set(classes)) != len(classes)
        or any(row.get("split") != "train" for row in train)
        or any(row.get("split") != "calibration" for row in calibration)
    ):
        raise data.DatasetError(
            "provide nonempty train/calibration splits "
            "and unique catalog classes including none"
        )
    if {row["group"] for row in train} & {row["group"] for row in calibration}:
        raise data.DatasetError("training and calibration source groups overlap")
    if data.leaky_pairs(
        {row["id"]: row["text"] for row in combined},
        {row["id"]: row["split"] for row in combined},
    ):
        raise data.DatasetError("training and calibration have near-duplicate wording")
    if kind == "prior":
        counts = Counter(row["label"] for row in train)
        prior = np.array([counts[name] / len(train) for name in classes])

        def raw_predict(texts):
            return np.tile(prior, (len(texts), 1))
    elif kind == "keyword":
        model = rules.KeywordModel().fit(train)

        def raw_predict(texts):
            return np.array(
                [
                    [scores.get(name, 0.0) for name in classes]
                    for scores in (model.predict_proba(text) for text in texts)
                ]
            )
    elif kind == "tfidf":
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline

        model = make_pipeline(
            TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
            LogisticRegression(
                class_weight="balanced", max_iter=2000, random_state=20261008
            ),
        )
        model.fit([row["text"] for row in train], [row["label"] for row in train])
        indices = [classes.index(name) for name in model.classes_]

        def raw_predict(texts):
            probs = np.zeros((len(texts), len(classes)))
            probs[:, indices] = model.predict_proba(texts)
            return probs
    else:
        raise ValueError(f"unknown baseline {kind!r}")
    probs = raw_predict([row["text"] for row in calibration])
    y = np.array([classes.index(row["label"]) for row in calibration])
    temperature = 1.0 if kind == "prior" else temperature_scale(probs, y)
    threshold = select_threshold(_scale(probs, temperature), y)
    return Baseline(raw_predict, classes, temperature, threshold)


def require_preregistration(path: Path) -> str:
    text = path.read_text()
    signature = next(
        (
            line
            for line in text.splitlines()
            if line.startswith("Owner signature/date:")
        ),
        "",
    )
    if not re.search(r"\d{4}-\d{2}-\d{2}", signature) or "pending" in signature.lower():
        raise data.DatasetError(
            "owner-signed preregistration is required "
            "before evaluating a trained system"
        )
    return hashlib.sha256(text.encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", choices=["prior", "keyword", "tfidf"], required=True
    )
    for name in (
        "train",
        "calibration",
        "catalog",
        "test",
        "lock",
        "runs",
        "preregistration",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    prereg_digest = require_preregistration(args.preregistration)
    train = [
        json.loads(line) for line in args.train.read_text().splitlines() if line.strip()
    ]
    calibration = [
        json.loads(line)
        for line in args.calibration.read_text().splitlines()
        if line.strip()
    ]
    classes = [
        *sorted(row["id"] for row in json.loads(args.catalog.read_text())),
        "none",
    ]
    model = fit_baseline(args.baseline, train, calibration, classes)
    manifest = {
        "baseline": args.baseline,
        "trainDigest": data.lock_digest(train),
        "calibrationDigest": data.lock_digest(calibration),
        "exposureDigest": hashlib.sha256(
            json.dumps(
                sorted(
                    (row["id"], row["group"], row["text"])
                    for row in [*train, *calibration]
                )
            ).encode()
        ).hexdigest(),
        "catalogDigest": hashlib.sha256(args.catalog.read_bytes()).hexdigest(),
        "preregistrationDigest": prereg_digest,
        "classes": classes,
        "temperature": model.temperature,
        "threshold": model.threshold,
        "versions": {name: version(name) for name in ("numpy", "scipy")},
        "codeDigests": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), Path(rules.__file__))
        },
    }
    if args.baseline == "tfidf":
        manifest["versions"]["scikit-learn"] = version("scikit-learn")
    revision = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    result = evaluate_once(
        args.test,
        args.lock,
        revision=revision,
        classes=classes,
        predict=model.predict,
        exposure=[
            {key: row[key] for key in ("id", "text", "group")}
            for row in [*train, *calibration]
        ],
        threshold=model.threshold,
        calibration_digest=manifest["calibrationDigest"],
        runs=args.runs,
    )
    args.runs.joinpath(f"{revision}.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    probs = model.predict([row["text"] for row in calibration])
    errors = [
        {
            "id": row["id"],
            "label": row["label"],
            "predicted": classes[int(pred)],
            "text": row["text"],
        }
        for row, pred in zip(calibration, probs.argmax(axis=1), strict=True)
        if classes[int(pred)] != row["label"]
    ]
    args.runs.joinpath(f"{revision}.calibration-errors.json").write_text(
        json.dumps(errors, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
