"""Source isolation and a sealed test set, using synthetic annotations only."""

import json

import pytest
from measure_mapping import data
from scripts.make_splits import make_splits, write_splits


def rows():
    return [
        {
            "id": f"item-{i:02}",
            "text": f"signal number{i} measurement{i}",
            "label": "S1" if i % 2 else "none",
            "source": "paper",
            "provenance": "human-adjudicated",
            "group": f"paper-{i // 2}",
            "annotator": "A",
            "annotator2": "B",
            "adjudicated": True,
        }
        for i in range(40)
    ]


def test_splits_keep_source_groups_together_and_are_order_independent():
    source = rows()
    result = make_splits(source, {"S1"})
    assert result == make_splits(list(reversed(source)), {"S1"})
    assert result["splits"] != make_splits(source, {"S1"}, seed=7)["splits"]
    by_group = {}
    for row in source:
        by_group.setdefault(row["group"], set()).add(result["splits"][row["id"]])
    assert all(len(splits) == 1 for splits in by_group.values())
    assert set(result["splits"].values()) == {"train", "calibration", "test"}


def test_repository_and_model_phrases_force_the_whole_group_into_training():
    source = rows()
    source[0]["provenance"] = "repo"
    source[2]["provenance"] = "llm"
    result = make_splits(source, {"S1"})
    assert all(result["splits"][f"item-{i:02}"] == "train" for i in range(4))


def test_near_duplicate_training_phrases_are_removed_without_moving_test_items():
    source = rows()
    source.append({**source[0], "id": "seed", "group": "seed", "provenance": "repo"})
    before = make_splits(source, {"S1"})
    test_id = next(i for i, split in before["splits"].items() if split == "test")
    target = next(row for row in source if row["id"] == test_id)
    source[-1]["text"] = target["text"]
    result = make_splits(source, {"S1"})
    assert result["removed"] == ["seed"]
    assert "seed" not in result["splits"]
    assert result["splits"][test_id] == "test"


def test_calibration_test_overlap_is_refused_instead_of_hidden():
    source = rows()
    assignments = make_splits(source, {"S1"})["splits"]
    test = next(row for row in source if assignments[row["id"]] == "test")
    calibration = next(row for row in source if assignments[row["id"]] == "calibration")
    calibration["text"] = test["text"]
    with pytest.raises(data.DatasetError, match=r"calibration.*test"):
        make_splits(source, {"S1"})


def test_test_lock_changes_with_a_test_label_and_refuses_unknown_classes():
    source = rows()
    before = make_splits(source, {"S1"})
    test = next(row for row in source if before["splits"][row["id"]] == "test")
    test["label"] = "none" if test["label"] == "S1" else "S1"
    after = make_splits(source, {"S1"})
    assert after["splits"] == before["splits"]
    assert after["testDigest"] != before["testDigest"]
    test["label"] = "invented"
    with pytest.raises(data.DatasetError, match="unknown label"):
        make_splits(source, {"S1"})


def test_training_files_exclude_test_labels_and_cannot_be_overwritten(tmp_path):
    source = rows()
    output = tmp_path / "splits"
    sealed = tmp_path / "sealed" / "test.jsonl"
    write_splits(source, {"S1"}, output, sealed)
    mapping = json.loads((output / "split.v1.json").read_text())
    training = [
        json.loads(line) for line in (output / "train.jsonl").read_text().splitlines()
    ]
    calibration = [
        json.loads(line)
        for line in (output / "calibration.jsonl").read_text().splitlines()
    ]
    test = [json.loads(line) for line in sealed.read_text().splitlines()]
    assert training and calibration and test
    assert {row["id"] for row in training + calibration}.isdisjoint(
        row["id"] for row in test
    )
    assert all(
        mapping[row["id"]] == row["split"] for row in training + calibration + test
    )
    assert (output / "test.locked.sha256").read_text().strip() == data.lock_digest(test)
    with pytest.raises(FileExistsError):
        write_splits(source, {"S1"}, output, sealed)


def test_sealed_test_file_must_be_outside_the_working_tree(tmp_path):
    with pytest.raises(data.DatasetError, match="outside"):
        write_splits(
            rows(),
            {"S1"},
            tmp_path / "output",
            tmp_path / "test.jsonl",
            worktree=tmp_path,
        )


def test_unresolved_annotations_cannot_be_sealed_for_evaluation(tmp_path):
    source = rows()
    assignments = make_splits(source, {"S1"})["splits"]
    test = next(row for row in source if assignments[row["id"]] == "test")
    test["adjudicated"] = False
    with pytest.raises(data.DatasetError, match="adjudicat"):
        write_splits(source, {"S1"}, tmp_path / "output", tmp_path / "test.jsonl")
