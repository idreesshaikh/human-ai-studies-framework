"""The locked evaluator logs reads and refuses leakage or unsupported claims."""

import json
import math

import numpy as np
import pytest
from eval.final_eval import evaluate_once
from measure_mapping import data


def sealed_fixture(tmp_path, *, n=100):
    rows = [
        {
            "id": str(i),
            "text": f"synthetic phrase {i}",
            "label": "S1" if i % 2 == 0 else "none",
            "source": "paper",
            "provenance": "human-adjudicated",
            "group": f"paper-{i // 5}",
            "annotator": "A",
            "annotator2": "B",
            "adjudicated": True,
            "split": "test",
        }
        for i in range(n)
    ]
    test = tmp_path / "sealed.jsonl"
    test.write_text("".join(json.dumps(row) + "\n" for row in rows))
    lock = tmp_path / "test.locked.sha256"
    lock.write_text(data.lock_digest(rows) + "\n")
    return rows, test, lock


def evaluate(tmp_path, test, lock, **kwargs):
    kwargs.setdefault("exposure", [])
    return evaluate_once(
        test,
        lock,
        revision="frozen-model-1",
        classes=["S1", "none"],
        predict=lambda texts: np.tile([0.7, 0.3], (len(texts), 1)),
        threshold=0.8,
        runs=tmp_path / "runs",
        n_boot=30,
        **kwargs,
    )


@pytest.mark.parametrize("overlap", ["id", "group", "text"])
def test_evaluation_rejects_overlap_with_frozen_training_metadata(tmp_path, overlap):
    rows, test, lock = sealed_fixture(tmp_path)
    exposed = {
        "id": "training-only",
        "group": "training-paper",
        "text": "different wording",
    }
    exposed[overlap] = rows[0][overlap]
    with pytest.raises(data.DatasetError, match=r"overlap|leak"):
        evaluate(tmp_path, test, lock, exposure=[exposed])


def test_metrics_are_hand_computed_and_threshold_is_frozen(tmp_path):
    _, test, lock = sealed_fixture(tmp_path)
    result = evaluate(tmp_path, test, lock)
    assert result["items"] == 100
    assert result["metrics"]["accuracy"]["value"] == 0.5
    assert result["metrics"]["nll"]["value"] == pytest.approx(-math.log(0.21) / 2)
    assert result["metrics"]["brier"]["value"] == pytest.approx(0.58)
    assert result["metrics"]["macro_f1"]["value"] == pytest.approx(1 / 3)
    assert result["metrics"]["macro_f1_S"]["value"] == pytest.approx(2 / 3)
    assert result["metrics"]["macro_f1_E"]["value"] is None
    assert result["metrics"]["selective_coverage"]["value"] == 0.0
    assert result["metrics"]["selective_error"]["value"] is None
    assert result["threshold"] == 0.8
    assert result["metrics"]["coverage_at_5pct_risk"]["value"] == 0.0
    lo, hi = result["metrics"]["accuracy"]["ci"]
    assert lo <= 0.5 <= hi
    assert len((tmp_path / "runs" / "test_reads.log").read_text().splitlines()) == 1


def test_a_frozen_revision_cannot_read_the_test_set_twice(tmp_path):
    _, test, lock = sealed_fixture(tmp_path)
    evaluate(tmp_path, test, lock)
    test.unlink()  # Refusal must occur before even opening the test file again.
    with pytest.raises(data.DatasetError, match="already"):
        evaluate(tmp_path, test, lock)
    assert len((tmp_path / "runs" / "test_reads.log").read_text().splitlines()) == 1


def test_tampered_labels_are_refused_and_the_attempt_is_logged(tmp_path):
    rows, test, lock = sealed_fixture(tmp_path)
    rows[0]["label"] = "none"
    test.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(data.DatasetError, match="digest"):
        evaluate(tmp_path, test, lock)
    assert len((tmp_path / "runs" / "test_reads.log").read_text().splitlines()) == 1


@pytest.mark.parametrize("n", [0, 99])
def test_fewer_than_100_independent_real_items_cannot_support_comparison(tmp_path, n):
    _, test, lock = sealed_fixture(tmp_path, n=n)
    with pytest.raises(data.DatasetError, match="100"):
        evaluate(tmp_path, test, lock)


@pytest.mark.parametrize(
    "changes",
    [
        {"provenance": "llm"},
        {"provenance": "repo"},
        {"adjudicated": False},
        {"annotator2": "A"},
        {"split": "train"},
    ],
)
def test_generated_or_unresolved_truth_is_refused(tmp_path, changes):
    rows, test, lock = sealed_fixture(tmp_path)
    rows[0].update(changes)
    test.write_text("".join(json.dumps(row) + "\n" for row in rows))
    lock.write_text(data.lock_digest(rows))
    with pytest.raises(data.DatasetError):
        evaluate(tmp_path, test, lock)


def test_a_single_source_cluster_cannot_support_bootstrap_claims(tmp_path):
    rows, test, lock = sealed_fixture(tmp_path)
    for row in rows:
        row["group"] = "one-paper"
    test.write_text("".join(json.dumps(row) + "\n" for row in rows))
    lock.write_text(data.lock_digest(rows))
    with pytest.raises(data.DatasetError, match="clusters"):
        evaluate(tmp_path, test, lock)
