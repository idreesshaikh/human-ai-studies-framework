"""Hand-calculated extraction summaries, with eligibility and missingness explicit."""
# ruff: noqa: S101 -- assertions on synthetic research fixtures

import csv

import pytest
from indicators import summarise


@pytest.fixture
def sheets(tmp_path):
    rows = [
        {
            "id": "a",
            "design": "between",
            "n_total_analysed": "128",
            "n_per_arm_analysed": "64",
            "a_priori_power_analysis": "yes",
            "effect_size_reported": "yes",
            "ci_reported": "yes",
            "preregistered": "yes",
            "n_primary_comparisons": "2",
            "multiple_comparison_correction": "yes",
            "tool_and_version_reported": "yes",
        },
        {
            "id": "b",
            "design": "within",
            "n_total_analysed": "34",
            "n_per_arm_analysed": "",
            "a_priori_power_analysis": "no",
            "effect_size_reported": "yes",
            "ci_reported": "no",
            "preregistered": "no",
            "n_primary_comparisons": "1",
            "multiple_comparison_correction": "not_applicable",
            "tool_and_version_reported": "partial",
        },
        {
            "id": "c",
            "design": "between",
            "n_total_analysed": "40",
            "n_per_arm_analysed": "20",
            "a_priori_power_analysis": "not_stated",
            "effect_size_reported": "no",
            "ci_reported": "",
            "preregistered": "not_stated",
            "n_primary_comparisons": "3",
            "multiple_comparison_correction": "no",
            "tool_and_version_reported": "no",
        },
        {
            "id": "d",
            "design": "crossover",
            "n_total_analysed": "20",
            "n_per_arm_analysed": "",
            "a_priori_power_analysis": "yes",
            "effect_size_reported": "no",
            "ci_reported": "yes",
            "preregistered": "no",
            "n_primary_comparisons": "",
            "multiple_comparison_correction": "not_stated",
            "tool_and_version_reported": "yes",
        },
    ]
    for row in rows:
        row.update(
            abstract_only="false",
            coder="fixture-coder",
            page_or_table_reference="Table 1",
        )
    extraction = tmp_path / "extraction.csv"
    with extraction.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    screening = tmp_path / "screening.csv"
    screening.write_text("id,decision\na,include\nb,include\nc,include\nd,include\n")
    return extraction, screening


def test_hand_calculated_medians_shares_and_missing_counts(sheets):
    result = summarise(*sheets)
    assert result["studies"] == 4
    assert result["numeric"]["n_total_analysed"] == {
        "n": 4,
        "missing": 0,
        "median": 37.0,
        "q1": 30.5,
        "q3": 62.0,
    }
    assert result["numeric"]["n_per_arm_analysed"] == {
        "n": 2,
        "missing": 2,
        "median": 42.0,
        "q1": 31.0,
        "q3": 53.0,
    }
    proportions = result["proportions"]
    assert proportions["a_priori_power_analysis"]["share"] == 2 / 3
    assert proportions["a_priori_power_analysis"]["missing"] == 1
    assert proportions["effect_size_reported"]["share"] == 1 / 2
    assert proportions["ci_reported"]["share"] == 2 / 3
    assert proportions["preregistered"]["share"] == 1 / 3
    assert proportions["tool_and_version_reported"]["share"] == 1 / 2
    correction = proportions["multiple_comparison_correction"]
    assert correction["share"] == 1 / 2 and correction["n"] == 2
    assert correction["eligibility_unknown"] == 1
    assert result["sensitivity"]["skipped_design"] == 1
    assert result["sensitivity"]["n"] == 3
    assert result["sensitivity"]["median"] == pytest.approx(0.5, abs=0.01)
    # Exact Clopper-Pearson interval for two successes in four trials.
    assert proportions["effect_size_reported"]["ci"] == pytest.approx(
        [0.067586, 0.932414], abs=1e-6
    )


def test_abstract_only_and_excluded_studies_do_not_enter_indicators(sheets):
    extraction, screening = sheets
    text = extraction.read_text().replace(
        "false,fixture-coder", "true,fixture-coder", 1
    )
    extraction.write_text(text)
    screening.write_text(screening.read_text().replace("d,include", "d,exclude"))
    result = summarise(*sheets)
    assert result["studies"] == 2 and result["abstract_only"] == 1
    assert result["numeric"]["n_total_analysed"]["median"] == 37.0


def test_empty_extraction_has_no_invented_values(tmp_path):
    extraction = tmp_path / "extraction.csv"
    extraction.write_text("id,abstract_only\n")
    screening = tmp_path / "screening.csv"
    screening.write_text("id,decision\n")
    result = summarise(extraction, screening)
    assert result["studies"] == 0
    assert result["numeric"]["n_total_analysed"]["median"] is None
    assert result["proportions"]["effect_size_reported"]["share"] is None
