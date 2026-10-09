import json

import pytest
from measure_mapping import data, rules

CLASSES = {"S1", "E1", "E2"}


def row(i, label="S1", group="g1", **kw):
    return {
        "id": i,
        "text": f"text {i}",
        "label": label,
        "source": "template",
        "provenance": "repo",
        "group": group,
        **kw,
    }


def test_validate_accepts_classes_and_none_and_rejects_bad_rows():
    assert len(data.validate_rows([row("a"), row("b", label="none")], CLASSES)) == 2
    for bad in (
        row("a", label="ZZ"),
        row("a", provenance="guess"),
        {"id": "a", "text": "t"},
    ):
        with pytest.raises(data.DatasetError):
            data.validate_rows([bad], CLASSES)
    with pytest.raises(data.DatasetError):
        data.validate_rows([row("a"), row("a")], CLASSES)


def test_model_written_text_cannot_enter_calibration_or_test():
    with pytest.raises(data.DatasetError):
        data.validate_rows([row("a", provenance="llm", split="test")], CLASSES)
    data.validate_rows([row("a", provenance="llm", split="train")], CLASSES)


@pytest.mark.parametrize("split", ["calibration", "test"])
def test_repo_written_seeds_cannot_enter_independent_evaluation(split):
    with pytest.raises(data.DatasetError):
        data.validate_rows([row("a", split=split)], CLASSES)


def test_null_required_fields_are_refused():
    with pytest.raises(data.DatasetError):
        data.validate_rows([row("a", text=None)], CLASSES)


def test_splits_are_group_disjoint_deterministic_and_roughly_proportional():
    groups = {f"i{n}": f"g{n % 20}" for n in range(200)}
    first = data.assign_splits(groups, seed=7)
    assert first == data.assign_splits(groups, seed=7)
    assert first != data.assign_splits(groups, seed=8)
    by_group = {}
    for item, split in first.items():
        by_group.setdefault(groups[item], set()).add(split)
    assert all(len(s) == 1 for s in by_group.values())
    shares = {s: sum(v == s for v in first.values()) / 200 for s in data.SPLITS}
    assert shares["train"] == pytest.approx(0.6, abs=0.15) and shares["test"] > 0


def test_bad_fractions_are_refused():
    with pytest.raises(data.DatasetError):
        data.assign_splits({"a": "g"}, seed=1, fractions={"train": 0.5, "test": 0.5})


@pytest.mark.parametrize(
    "fractions",
    [
        {},
        {"train": 1.2, "calibration": -0.1, "test": -0.1},
        {"train": float("nan"), "calibration": 0.2, "test": 0.2},
    ],
)
def test_invalid_fraction_values_cannot_create_a_frozen_split(fractions):
    with pytest.raises(data.DatasetError):
        data.assign_splits({"a": "g"}, seed=1, fractions=fractions)


def test_leaky_pairs_find_near_duplicates_across_splits_only():
    texts = {
        "a": "how mentally taxing was the task",
        "b": "how mentally taxing was this task",
        "c": "task completion time",
    }
    splits = {"a": "train", "b": "test", "c": "test"}
    assert data.leaky_pairs(texts, splits, jaccard=0.6) == [("a", "b")]
    assert data.leaky_pairs(texts, {"a": "test", "b": "test", "c": "test"}) == []


def test_lock_digest_is_order_independent_and_changes_with_any_edit():
    rows = [row("a"), row("b", label="E1")]
    assert data.lock_digest(rows) == data.lock_digest(list(reversed(rows)))
    assert data.lock_digest(rows) != data.lock_digest([row("a"), row("b", label="E2")])
    assert data.lock_digest(rows) != data.lock_digest(
        [row("a"), {**row("b", label="E1"), "text": "changed"}]
    )


def test_training_code_refuses_test_rows():
    rows = [row("a"), row("b")]
    with pytest.raises(data.DatasetError):
        data.training_rows(rows, {"a": "train", "b": "test"})
    assert [
        r["id"] for r in data.training_rows(rows, {"a": "train", "b": "calibration"})
    ] == ["a", "b"]


TRAIN = [
    {"text": "how mentally taxing was the task", "label": "S1"},
    {"text": "mental demand of the task", "label": "S1"},
    {"text": "time until the tests passed", "label": "E1"},
    {"text": "task completion time", "label": "E1"},
    {"text": "trust in the assistant", "label": "none"},
    {"text": "satisfaction with the tool", "label": "none"},
]


def test_keyword_model_learns_cues_and_gives_probabilities():
    model = rules.KeywordModel().fit(TRAIN)
    probs = model.predict_proba("how mentally demanding was it")
    assert probs["S1"] == max(probs.values()) and sum(probs.values()) == pytest.approx(
        1.0
    )
    assert model.predict_proba("completion time of tasks")["E1"] > 0.5
    assert (
        max(model.predict_proba("trust"), key=model.predict_proba("trust").get)
        == "none"
    )


def test_keyword_model_refuses_empty_training_and_bad_smoothing():
    with pytest.raises(ValueError):
        rules.KeywordModel().fit([])
    with pytest.raises(ValueError):
        rules.KeywordModel(alpha=0)


def test_unseen_words_do_not_crash():
    probs = rules.KeywordModel().fit(TRAIN).predict_proba("zzz qqq")
    assert sum(probs.values()) == pytest.approx(1.0)


def test_lock_digest_is_a_stable_known_value():
    rows = [{"id": "a", "text": "t", "label": "S1"}]
    expected = (
        __import__("hashlib")
        .sha256(json.dumps([("a", "t", "S1")], separators=(",", ":")).encode())
        .hexdigest()
    )
    assert data.lock_digest(rows) == expected
