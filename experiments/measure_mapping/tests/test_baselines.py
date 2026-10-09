"""Baselines fit training data and calibrate using a separate source split."""

import numpy as np
import pytest
from measure_mapping import data, metrics
from scripts.run_baseline import fit_baseline, select_threshold, temperature_scale


def row(i, text, label, split="train"):
    return {
        "id": str(i),
        "text": text,
        "label": label,
        "source": "paper",
        "provenance": "human-adjudicated",
        "group": f"paper-{i}",
        "split": split,
    }


TRAIN = [
    row(1, "mental demand taxing task", "S1"),
    row(2, "mental demand questionnaire", "S1"),
    row(3, "trust in automation", "none"),
    row(4, "confidence in automation", "none"),
]
CALIBRATION = [
    row(5, "mental demand score", "S1", "calibration"),
    row(6, "trust in the tool", "none", "calibration"),
]


def test_prior_baseline_returns_training_frequencies_in_catalog_order():
    model = fit_baseline("prior", TRAIN[:3], CALIBRATION, ["S1", "none"])
    assert model.predict(["anything"])[0] == pytest.approx([2 / 3, 1 / 3])


def test_keyword_baseline_handles_none_and_unseen_catalog_classes():
    model = fit_baseline("keyword", TRAIN, CALIBRATION, ["E1", "S1", "none"])
    probs = model.predict(["mental demand", "trust automation"])
    assert probs.shape == (2, 3)
    assert probs.argmax(axis=1).tolist() == [1, 2]
    assert probs[:, 0].tolist() == [0.0, 0.0]
    assert probs.sum(axis=1) == pytest.approx([1.0, 1.0])


def test_temperature_is_fitted_to_calibration_errors():
    probs = np.tile([0.9, 0.1], (20, 1))
    y = np.array([0, 1] * 10)
    temperature = temperature_scale(probs, y)
    scaled = np.exp(np.log(probs) / temperature)
    scaled /= scaled.sum(axis=1, keepdims=True)
    assert temperature > 2
    assert metrics.nll(scaled, y) < metrics.nll(probs, y)


def test_threshold_answers_confidence_ties_together():
    probs = np.array([[0.8, 0.2], [0.7, 0.3], [0.6, 0.4], [0.6, 0.4]])
    assert select_threshold(probs, np.array([0, 0, 0, 1])) == 0.7
    assert select_threshold(np.array([[0.9, 0.1]]), np.array([1])) is None


def test_training_code_refuses_any_test_labels():
    with pytest.raises(data.DatasetError, match="test rows"):
        fit_baseline(
            "keyword", [row(7, "secret", "none", "test")], CALIBRATION, ["S1", "none"]
        )


def test_source_groups_cannot_overlap_training_and_calibration():
    calibration = [{**CALIBRATION[0], "group": TRAIN[0]["group"]}, CALIBRATION[1]]
    with pytest.raises(data.DatasetError, match="source"):
        fit_baseline("prior", TRAIN, calibration, ["S1", "none"])


def test_tfidf_baseline_runs_real_binary_and_multiclass_estimators():
    pytest.importorskip("sklearn")
    binary = fit_baseline("tfidf", TRAIN, CALIBRATION, ["S1", "none"])
    assert binary.predict(["mental demand", "trust automation"]).argmax(
        axis=1
    ).tolist() == [0, 1]
    train = [*TRAIN, row(7, "task completion duration time", "E1")]
    calibration = [*CALIBRATION, row(8, "completion duration", "E1", "calibration")]
    multiclass = fit_baseline("tfidf", train, calibration, ["E1", "S1", "none"])
    probs = multiclass.predict(
        ["completion duration", "mental demand", "trust automation"]
    )
    assert probs.argmax(axis=1).tolist() == [0, 1, 2]
    assert probs.sum(axis=1) == pytest.approx([1.0, 1.0, 1.0])
