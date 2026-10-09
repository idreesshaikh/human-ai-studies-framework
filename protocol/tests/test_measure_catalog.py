"""The product catalog connects supported outcomes to declared capture and analysis."""

import copy

import analysis.recipes  # noqa: F401 - registers recipes
import pytest
from analysis.core import REGISTRY
from protocol.measure_catalog import (
    apply_catalog_measures,
    measure_catalog,
    suggest_measures,
)


def draft(design="within-subjects"):
    return {
        "protocolVersion": 5,
        "participants": {"design": design},
        "researchQuestions": [
            {"id": "RQ-1", "text": "Does AI assistance change developer outcomes?"}
        ],
        "instruments": {},
        "analysisPlan": [],
        "measures": [{"catalogId": "E1"}, {"catalogId": "S1"}],
    }


def test_catalog_has_twenty_classes_and_only_registered_outcome_recipes():
    catalog = measure_catalog()
    assert len(catalog) == 20
    assert len({row["id"] for row in catalog}) == 20
    for row in catalog:
        for recipe in row["recipeByDesign"].values():
            assert recipe is None or recipe in REGISTRY


@pytest.mark.parametrize(
    "design,recipe",
    [
        ("within-subjects", "paired-nonparametric"),
        ("between-subjects", "two-group-nonparametric"),
    ],
)
def test_accepted_catalog_measures_declare_capture_surveys_and_design_matched_recipes(
    design, recipe
):
    protocol = draft(design)
    assert apply_catalog_measures(protocol) == []
    assert protocol["protocolVersion"] == 6
    assert protocol["measures"][0]["analysisRecipe"] == recipe
    assert protocol["measures"][1]["fields"] == [
        "survey_response.responses.mental_demand"
    ]
    assert protocol["instruments"]["taskHarness"]["enabled"] is True
    assert protocol["instruments"]["surveys"][0]["id"] == "raw-nasa-tlx"
    assert {recipe, "typed-measures"} <= set(protocol["analysisPlan"][0]["recipes"])
    assert protocol["measureSetVersion"]


def test_catalog_is_returned_as_a_copy_and_does_not_mutate_existing_survey_wording():
    catalog = measure_catalog()
    catalog[0]["construct"] = "changed"
    assert measure_catalog()[0]["construct"] == "mental demand"
    protocol = draft()
    apply_catalog_measures(protocol)
    protocol["instruments"]["surveys"][0]["items"][0]["text"] = "Researcher wording"
    protocol["measures"].append({"catalogId": "S2"})
    assert apply_catalog_measures(protocol) == []
    assert (
        protocol["instruments"]["surveys"][0]["items"][0]["text"]
        == "Researcher wording"
    )
    assert len(protocol["instruments"]["surveys"]) == 1


def test_unsupported_within_subject_binary_analysis_does_not_silently_upgrade():
    protocol = draft()
    protocol["measures"] = [{"catalogId": "E2"}]
    before = copy.deepcopy(protocol)
    problems = apply_catalog_measures(protocol)
    assert problems and "design" in problems[0]
    assert protocol == before


def test_unknown_free_text_does_not_get_an_invented_measure():
    protocol = draft()
    protocol["measures"].append("trust in AI")
    before = copy.deepcopy(protocol)
    assert apply_catalog_measures(protocol)
    assert protocol == before


def test_suggestions_match_aliases_and_abstain_for_unknown_constructs():
    result = suggest_measures("time pressure", "within-subjects")
    assert result["suggestions"][0]["id"] == "S4"
    assert result["method"] == "catalog-aliases"
    assert result["calibrated"] is False
    assert result["abstain"] is False
    assert suggest_measures("trust in AI", "within-subjects")["abstain"] is True
    assert (
        suggest_measures("productivity perception", "between-subjects")["suggestions"]
        == []
    )


def test_unsupported_design_stays_visible_but_is_not_selectable():
    result = suggest_measures("test success", "within-subjects")
    assert result["suggestions"][0]["designCompatible"] is False
    assert result["abstain"] is True


def test_prior_skill_is_a_covariate_and_never_an_outcome_recipe():
    protocol = draft()
    protocol["measures"].append({"catalogId": "S10"})
    assert apply_catalog_measures(protocol) == []
    assert protocol["covariate"] == {
        "instrument": "pre-task-skill",
        "field": "pre_task_covariate.score",
        "timing": "pre-task",
    }
    assert all(
        measure["instrument"] != "pre-task-skill" for measure in protocol["measures"]
    )


def test_malformed_catalog_ids_are_reported_without_a_crash():
    protocol = draft()
    protocol["measures"] = [{"catalogId": []}]
    before = copy.deepcopy(protocol)
    assert apply_catalog_measures(protocol)
    assert protocol == before


def test_a_disabled_producer_cannot_be_presented_as_capturing_an_outcome():
    protocol = draft()
    protocol["instruments"]["taskHarness"] = {"enabled": False}
    before = copy.deepcopy(protocol)
    assert any("disabled" in problem for problem in apply_catalog_measures(protocol))
    assert protocol == before


def test_perceived_duration_is_not_suggested_as_a_first_green_timer():
    result = suggest_measures("perceived task completion time", "between-subjects")
    assert result["abstain"] is True
    assert result["suggestions"] == []
