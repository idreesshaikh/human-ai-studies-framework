"""The prescription table: design shape → the exact statistics it calls for."""

from __future__ import annotations

from analysis.prescribe import (
    prescribe,
    shapes_from_recipe_ids,
)


def test_an_unknown_shape_returns_none_rather_than_guessing():
    """
    The caller's contract: no prescription means the conversation raises an unsourced
    caution, never an invented test.
    """
    assert prescribe("not-a-real-shape") is None
    assert prescribe("") is None


def test_paired_designs_get_a_paired_test():
    """
    A spot-check with real methodological content: a within-subjects comparison must not
    be handed an independent-samples test.
    """
    p = prescribe("paired")
    assert "Wilcoxon" in p.test
    assert "signed-rank" in p.test.lower()
    assert p.effect_size and p.sample_size_guidance and p.rationale


def test_multi_group_designs_carry_a_correction():
    """Several comparisons need one; saying "none" here would be wrong."""
    p = prescribe("multi-group")
    assert p.correction.lower() != "none"


def test_shapes_from_recipe_ids_resolves_a_studys_own_plan():
    """
    A study's compiled analysisPlan stores recipe ids ("paired-nonparametric"),
    not shape ids ("paired")  -  this is what lets the Data tab show only the
    prescription for a study's own design instead of every shape PHOENIX
    knows, regardless of that study's actual design (the previous bug).
    """
    assert shapes_from_recipe_ids({"paired-nonparametric"}) == {"paired"}
    assert shapes_from_recipe_ids({"two-group-nonparametric", "correlation"}) == {
        "two-group",
        "correlation",
    }


def test_shapes_from_recipe_ids_ignores_unknown_recipes():
    assert shapes_from_recipe_ids(set()) == set()
    assert shapes_from_recipe_ids({"not-a-real-recipe"}) == set()
