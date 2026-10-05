"""Evidence identity, uncertainty and review gates on synthetic contract cases."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest
from protocol.cli import main
from protocol.errors import ProtocolError
from protocol.evidence import (
    evidence_map_schema,
    load_evidence_map,
    validate_evidence_map,
)

EXAMPLE = Path(__file__).parents[1] / "examples" / "evidence-map.yaml"


@pytest.fixture()
def mapping():
    return load_evidence_map(EXAMPLE)


def test_example_keeps_unknowns_and_does_not_claim_a_review(mapping):
    assert mapping["studies"][0]["population"] is None
    assert mapping["relations"][0]["review"]["status"] == "unreviewed"
    assert "Synthetic" in mapping["description"]
    jsonschema.Draft202012Validator.check_schema(evidence_map_schema())


def test_multiple_studies_per_report_and_multiple_reports_per_study(mapping):
    report = {**mapping["publications"][0], "id": "report-2", "source": "fixture:2"}
    mapping["publications"].append(report)
    mapping["studies"][0]["publicationIds"].append("report-2")
    study = copy.deepcopy(mapping["studies"][0])
    study["id"] = "study-2"
    mapping["studies"].append(study)
    assert validate_evidence_map(mapping) == []


@pytest.mark.parametrize("status", ["compatible", "incompatible", "unknown"])
def test_contract_reviewed_applicable_incompatible_and_insufficient_cases(
    mapping, status
):
    # A contract test reviewer is not a scientific or pilot-map reviewer.
    relation = mapping["relations"][0]
    relation["review"] = {
        "status": "reviewed",
        "reviewers": ["synthetic-contract-test"],
        "notes": "Synthetic schema case; not literature review.",
    }
    relation["applicability"]["status"] = status
    relation["applicability"]["reasons"] = ["Synthetic case rationale"]
    assert validate_evidence_map(mapping) == []


@pytest.mark.parametrize("review_status", ["unreviewed", "disputed"])
def test_discovery_or_dispute_cannot_become_a_supported_recommendation(
    mapping, review_status
):
    relation = mapping["relations"][0]
    relation["review"]["status"] = review_status
    relation["applicability"]["status"] = "compatible"
    assert any("must be unknown" in e for e in validate_evidence_map(mapping))


def test_review_and_conditional_decisions_require_provenance(mapping):
    relation = mapping["relations"][0]
    relation["review"]["status"] = "reviewed"
    relation["applicability"].update(
        status="conditional", reasons=[], constraints=[], missingFacts=[]
    )
    errors = validate_evidence_map(mapping)
    assert any("identified reviewer" in e for e in errors)
    assert any("needs reasons" in e for e in errors)
    assert any("explicit conditions" in e for e in errors)


@pytest.mark.parametrize(
    "change, expected",
    [
        (lambda m: m["studies"][0]["publicationIds"].append("absent"), "publication"),
        (lambda m: m["relations"][0].update(studyId="absent"), "unknown study"),
        (
            lambda m: m["relations"][0]["passage"].update(publicationId="absent"),
            "passage",
        ),
        (
            lambda m: m["studies"][0]["captureRequirements"][0].update(
                measureId="absent"
            ),
            "capture",
        ),
        (
            lambda m: m["studies"][0]["measures"][0].update(construct="absent"),
            "construct",
        ),
        (
            lambda m: m["relations"][0].update(claimType="recommendation"),
            "reported fact",
        ),
        (
            lambda m: m["publications"].append(copy.deepcopy(m["publications"][0])),
            "duplicate",
        ),
    ],
)
def test_dangling_and_misleading_relations_are_rejected(mapping, change, expected):
    change(mapping)
    assert any(expected in e for e in validate_evidence_map(mapping))


def test_scores_cannot_masquerade_as_evidence_quality(mapping):
    relation = mapping["relations"][0]
    relation.update(extractionConfidence=0.9, evidenceQuality=0.9, rankingScore=0.9)
    assert validate_evidence_map(mapping)
    relation.pop("rankingScore")
    relation["evidenceQuality"] = "unknown"
    assert validate_evidence_map(mapping) == []


def test_schema_returns_an_independent_copy():
    schema = evidence_map_schema()
    schema["properties"]["schemaVersion"]["const"] = 2
    assert evidence_map_schema()["properties"]["schemaVersion"]["const"] == 1


def test_cli_validates_and_exports_schema(capsys):
    assert main(["validate-evidence-map", str(EXAMPLE)]) == 0
    assert "contract-demonstration" in capsys.readouterr().out
    assert main(["evidence-map-schema"]) == 0
    assert json.loads(capsys.readouterr().out)["$schema"].endswith("/schema")


def test_invalid_file_is_a_clear_cli_error(tmp_path, capsys):
    path = tmp_path / "bad.yaml"
    path.write_text("schemaVersion: 99\n")
    assert main(["validate-evidence-map", str(path)]) == 1
    assert "invalid evidence map" in capsys.readouterr().err
    path.write_text("broken: [")
    with pytest.raises(ProtocolError, match="cannot read evidence map"):
        load_evidence_map(path)
    with pytest.raises(ProtocolError, match="cannot read evidence map"):
        load_evidence_map(tmp_path / "missing.yaml")
