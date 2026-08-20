"""The prescription table: design shape → the exact statistics it calls for."""

from __future__ import annotations

import pytest
from analysis.prescribe import (
    design_shapes,
    prescribe,
    prescription_table,
    shape_to_recipe_id,
    shapes_from_recipe_ids,
)


def test_every_declared_shape_has_a_prescription():
    """
    A shape the platform advertises but cannot prescribe for is worse than one it does
    not advertise: the conversation offers a design and then has nothing to say about
    how to analyse it.
    """
    missing = [shape for shape in design_shapes() if prescribe(shape) is None]
    assert missing == []


@pytest.mark.parametrize("shape", design_shapes())
def test_a_prescription_is_complete_enough_to_act_on(shape):
    """NFR-8: never a bare test name."""
    p = prescribe(shape)
    assert p.test, shape
    assert p.effect_size, shape
    assert p.sample_size_guidance, shape
    assert p.rationale, shape
    assert p.correction, shape


def test_an_unknown_shape_returns_none_rather_than_guessing():
    """
    The caller's contract: no prescription means the conversation raises an unsourced
    caution, never an invented test.
    """
    assert prescribe("not-a-real-shape") is None
    assert prescribe("") is None


def test_the_table_is_deterministic():
    assert prescribe("paired") == prescribe("paired")
    assert [p.design_shape for p in prescription_table()] == design_shapes()


def test_paired_designs_get_a_paired_test():
    """
    A spot-check with real methodological content: a within-subjects comparison must not
    be handed an independent-samples test.
    """
    p = prescribe("paired")
    assert "Wilcoxon" in p.test
    assert "signed-rank" in p.test.lower()


def test_multi_group_designs_carry_a_correction():
    """Several comparisons need one; saying "none" here would be wrong."""
    p = prescribe("multi-group")
    assert p.correction.lower() != "none"


def test_a_named_recipe_always_exists():
    """A shape mapped to a recipe id the registry does not have is a dead reference."""
    import analysis.recipes  # noqa: F401 - importing registers the built-ins
    from analysis.core import REGISTRY

    for shape in design_shapes():
        recipe_id = shape_to_recipe_id(shape)
        if recipe_id is not None:
            assert recipe_id in REGISTRY, f"{shape} -> missing recipe {recipe_id}"


def test_shapes_from_recipe_ids_resolves_a_studys_own_plan():
    """
    A study's compiled analysisPlan stores recipe ids ("paired-nonparametric"),
    not shape ids ("paired") — this is what lets the Data tab show only the
    prescription for a study's own design instead of every shape PHOENIX
    knows, regardless of that study's actual design (the previous bug).
    """
    assert shapes_from_recipe_ids({"paired-nonparametric"}) == {"paired"}
    assert shapes_from_recipe_ids(
        {"two-group-nonparametric", "correlation"}
    ) == {"two-group", "correlation"}


def test_shapes_from_recipe_ids_ignores_unknown_recipes():
    assert shapes_from_recipe_ids(set()) == set()
    assert shapes_from_recipe_ids({"not-a-real-recipe"}) == set()


def test_a_shape_without_a_recipe_is_still_prescribed_for():
    """
    PHOENIX emits the analysis plan rather than running it, so "we cannot run this here"
    must never become "we cannot tell you what to run".
    """
    from analysis.prescribe import runnable_shapes

    not_runnable = set(design_shapes()) - set(runnable_shapes())
    assert not_runnable, "this test is meaningless if everything is runnable"
    for shape in not_runnable:
        assert prescribe(shape) is not None, shape
        assert prescribe(shape).test, shape
