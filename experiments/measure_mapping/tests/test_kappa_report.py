"""Blind sheets and chance-corrected agreement on hand-computed fixtures."""

import csv

import pytest
from scripts.kappa_report import agreement_report
from scripts.make_sheets import make_sheets


def test_both_annotators_receive_blank_label_columns(tmp_path):
    source = tmp_path / "phrases.jsonl"
    source.write_text('{"id":"a","text":"mental demand","label":"S1"}\n')
    paths = make_sheets(source, tmp_path / "sheets")
    for path in paths:
        with path.open() as file:
            rows = list(csv.DictReader(file))
        assert rows[0]["text"] == "mental demand"
        assert rows[0]["label"] == rows[0]["secondary_label"] == ""


def test_kappa_including_and_excluding_none_is_hand_computed():
    first = {"a": "S1", "b": "S1", "c": "E1", "d": "none"}
    second = {"a": "S1", "b": "E1", "c": "E1", "d": "none"}
    result = agreement_report(first, second)
    # Observed 3/4; chance 5/16; kappa = (12-5)/(16-5) = 7/11.
    assert result["with_none"]["kappa"] == pytest.approx(7 / 11)
    assert result["with_none"]["agreement"] == 3 / 4
    # Removing the both-none row: observed 2/3, chance 4/9, kappa 2/5.
    assert result["without_none"]["kappa"] == pytest.approx(2 / 5)
    assert result["confusion"]["S1"]["E1"] == 1
    assert not result["gate_passed"]  # Four items do not meet the pilot's 100.


def test_missing_labels_or_different_items_are_refused():
    with pytest.raises(ValueError):
        agreement_report({"a": "S1"}, {"b": "S1"})
    with pytest.raises(ValueError):
        agreement_report({"a": ""}, {"a": "S1"})


def test_single_label_agreement_is_undefined_and_cannot_pass_the_gate():
    labels = {str(i): "S1" for i in range(100)}
    result = agreement_report(labels, labels)
    assert result["with_none"]["agreement"] == 1.0
    assert result["with_none"]["kappa"] is None
    assert not result["gate_passed"]


def test_degenerate_cluster_resamples_do_not_produce_an_interval():
    labels = {"a": "S1", "b": "E1"}
    result = agreement_report(labels, labels, {"a": "paper-a", "b": "paper-b"})
    assert result["with_none"]["kappa"] == 1.0
    assert result["with_none"]["interval"] is None
    assert "undefined" in result["with_none"]["interval_reason"]
