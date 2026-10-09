import math

import pytest
from middleware.retrieval_metrics import mean, ndcg_at_k, recall_at_k, reciprocal_rank


def test_recall_counts_relevant_found_in_top_k():
    assert recall_at_k(["a", "b", "c", "d"], {"b", "d", "z"}, 2) == pytest.approx(1 / 3)
    assert recall_at_k(["a", "b", "c", "d"], {"b", "d", "z"}, 4) == pytest.approx(2 / 3)


def test_recall_is_undefined_without_relevant_items():
    assert recall_at_k(["a"], set(), 5) is None


def test_reciprocal_rank():
    assert reciprocal_rank(["x", "y", "b"], {"b"}) == pytest.approx(1 / 3)
    assert reciprocal_rank(["x"], {"b"}) == 0.0
    assert reciprocal_rank(["x"], set()) is None


def test_ndcg_is_one_for_the_ideal_order_and_lower_otherwise():
    grades = {"a": 2, "b": 1}
    assert ndcg_at_k(["a", "b"], grades, 2) == pytest.approx(1.0)
    swapped = ndcg_at_k(["b", "a"], grades, 2)
    expected = (1 / math.log2(2) + 3 / math.log2(3)) / (
        3 / math.log2(2) + 1 / math.log2(3)
    )
    assert swapped == pytest.approx(expected) and swapped < 1.0


def test_ndcg_undefined_without_graded_items_and_ignores_unjudged_refs():
    assert ndcg_at_k(["a"], {"a": 0}, 3) is None
    assert ndcg_at_k(["u1", "a"], {"a": 1}, 2) == pytest.approx(1 / math.log2(3))


@pytest.mark.parametrize(
    "fn,args", [(recall_at_k, (["a"], {"a"}, 0)), (ndcg_at_k, (["a"], {"a": 1}, 0))]
)
def test_k_must_be_positive(fn, args):
    with pytest.raises(ValueError):
        fn(*args)


def test_mean_skips_undefined_cases():
    assert mean([1.0, None, 0.0]) == pytest.approx(0.5)
    assert mean([None]) is None
