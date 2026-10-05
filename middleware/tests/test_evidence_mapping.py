"""Evidence is not a phrase match; decisions retain immutable source snapshots."""

import copy
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest
import yaml
from middleware.evidence_mapping import EvidenceContext, rank_candidates
from protocol.evidence import validate_evidence_map


@pytest.fixture
def evidence():
    root = Path(__file__).resolve().parents[2]
    document = yaml.safe_load(
        (root / "protocol/examples/evidence-map.yaml").read_text()
    )
    study = document["studies"][0]
    study["population"] = "Novice Python developers"
    study["tasks"] = ["Fix a Python bug"]
    study["measures"][0].update(
        {
            "instrument": "task-harness",
            "datasetFields": ["task_outcome.firstGreenMs"],
            "analysisRecipe": "two-group-nonparametric",
        }
    )
    study["captureRequirements"][0].update(
        {
            "producer": "task-harness",
            "eventTypes": ["task_outcome"],
        }
    )
    relation = document["relations"][0]
    relation.update(
        {
            "kind": "conditional-applicability",
            "claimType": "recommendation",
            "claim": "Synthetic test guidance for a between-subjects comparison.",
            "review": {
                "status": "reviewed",
                "reviewers": ["Synthetic test reviewer"],
                "notes": "Fixture only; no independent review claimed.",
            },
            "applicability": {
                "status": "compatible",
                "context": "Synthetic novice Python debugging study",
                "reasons": ["Synthetic fixture matches the stated context."],
                "constraints": [],
                "missingFacts": [],
            },
        }
    )
    assert validate_evidence_map(document) == []
    return document


@pytest.fixture
def context():
    return EvidenceContext(
        query="Does assistance change task completion time?",
        population="Novice Python developers",
        task="Fix a Python bug",
        construct="completion-time",
        producers=["task-harness"],
        instruments=["task-harness"],
        confirmedRelationIds=["reported-design"],
    )


def candidate(evidence, context):
    return rank_candidates(evidence, context)[0]


def test_compatible_needs_review_and_researcher_context(evidence, context):
    assert candidate(evidence, context)["status"] == "compatible"
    context.confirmedRelationIds = []
    result = candidate(evidence, context)
    assert result["status"] == "insufficient-evidence"
    assert "Confirm source context: reported-design" in result["missingFacts"]


@pytest.mark.parametrize("review", ["unreviewed", "disputed"])
def test_phrase_matches_are_not_evidence(evidence, context, review):
    relation = evidence["relations"][0]
    relation["review"]["status"] = review
    relation["applicability"]["status"] = "unknown"
    relation["extractionConfidence"] = 1.0
    result = candidate(evidence, context)
    assert result["discoveryScore"] > 0
    assert result["status"] == "insufficient-evidence"


def test_reported_use_is_not_a_recommendation(evidence, context):
    evidence["relations"][0]["kind"] = "reported-method-use"
    evidence["relations"][0]["claimType"] = "reported-fact"
    assert candidate(evidence, context)["status"] == "insufficient-evidence"


def test_revised_capture_constraint_recomputes(evidence, context):
    assert candidate(evidence, context)["status"] == "compatible"
    context.producers = []
    result = candidate(evidence, context)
    assert result["status"] == "incompatible"
    assert result["reasons"][-1] == "Missing producer: task-harness"


def test_topical_but_different_population_abstains(evidence, context):
    context.population = "Expert Python developers"
    assert candidate(evidence, context)["status"] == "insufficient-evidence"


def test_conflicting_guidance_blocks(evidence, context):
    conflict = copy.deepcopy(evidence["relations"][0])
    conflict["id"] = "conflict"
    conflict["applicability"]["status"] = "incompatible"
    evidence["relations"].append(conflict)
    assert candidate(evidence, context)["status"] == "incompatible"


def test_conditional_and_external_capture_are_explicit(evidence, context):
    evidence["studies"][0]["captureRequirements"][0]["availability"] = "external"
    result = candidate(evidence, context)
    assert result["status"] == "conditional"
    assert "Arrange external capture: task-harness" in result["constraints"]


@pytest.mark.parametrize(
    "availability,status",
    [("unknown", "insufficient-evidence"), ("unavailable", "incompatible")],
)
def test_capture_limits(evidence, context, availability, status):
    evidence["studies"][0]["captureRequirements"][0]["availability"] = availability
    assert candidate(evidence, context)["status"] == status


def test_unknown_family_is_not_executable(evidence, context):
    evidence["studies"][0]["designFamily"] = "case-study"
    evidence["studies"][0]["measures"][0]["analysisRecipe"] = None
    evidence["relations"][0]["target"] = "case-study"
    assert candidate(evidence, context)["status"] == "insufficient-evidence"


def test_unsupported_recipe_is_not_substituted(evidence, context):
    evidence["studies"][0]["measures"][0]["analysisRecipe"] = "invented-recipe"
    result = candidate(evidence, context)
    assert result["status"] == "incompatible"
    assert "Unsupported analysis recipe: invented-recipe" in result["reasons"]


def test_recipe_inputs_cannot_be_replaced_with_timer_telemetry(evidence, context):
    evidence["studies"][0]["captureRequirements"][0]["eventTypes"] = [
        "session_timer_ended"
    ]
    result = candidate(evidence, context)
    assert result["status"] == "insufficient-evidence"
    assert "Missing recipe input event: task_outcome" in result["missingFacts"]


def test_paired_analysis_cannot_support_separate_groups(evidence, context):
    evidence["studies"][0]["measures"][0]["analysisRecipe"] = "paired-nonparametric"
    assert candidate(evidence, context)["status"] == "incompatible"


def test_synthetic_demo_map_is_valid_and_has_two_alternatives(context):
    path = (
        Path(__file__).resolve().parents[2]
        / "protocol/examples/evidence-workflow-demo.json"
    )
    document = json.loads(path.read_text())
    assert validate_evidence_map(document) == []
    context.confirmedRelationIds = [r["id"] for r in document["relations"]]
    assert [c["status"] for c in rank_candidates(document, context)] == [
        "conditional",
        "conditional",
    ]


def test_map_import_is_versioned_and_exported(client_designed, evidence):
    path = "/studies/pilot/evidence-map"
    assert client_designed.get(path).json()["document"] is None
    imported = client_designed.put(path, json=evidence)
    assert imported.status_code == 200, imported.text
    assert client_designed.put(path, json=evidence).json() == imported.json()
    assert client_designed.put(path, json={}).status_code == 422
    changed = copy.deepcopy(evidence)
    changed["description"] += " changed"
    assert client_designed.put(path, json=changed).status_code == 409
    changed["mapVersion"] = "0.2.0"
    assert client_designed.put(path, json=changed).status_code == 200
    assert client_designed.put(path, json=evidence).status_code == 409
    record = client_designed.get("/studies/pilot/conversation/export").json()
    assert [r["document"]["mapVersion"] for r in record["evidenceMaps"]] == [
        "0.1.0",
        "0.2.0",
    ]


def test_proposal_approval_and_exports_retain_sources(
    client_designed, evidence, context
):
    client = client_designed
    context.query = client.get("/studies/pilot/protocol").json()["document"][
        "researchQuestions"
    ][0]["text"]
    path = "/studies/pilot/evidence-map"
    before = client.get("/studies/pilot/protocol").json()["document"]
    imported = client.put(path, json=evidence).json()
    compared = client.post(path + "/candidates", json=context.model_dump())
    assert compared.status_code == 200, compared.text
    body = {
        **context.model_dump(),
        "candidateId": "fixture-study-1",
        "mapDigest": imported["digest"],
        "requestId": "synthetic-proposal",
    }
    response = client.post(path + "/propose", json=body)
    assert response.status_code == 200, response.text
    move_id = response.json()["moveId"]
    assert client.post(path + "/propose", json=body).json()["moveId"] == move_id
    assert (
        client.post(
            path + "/propose", json={**body, "query": "Other question"}
        ).status_code
        == 409
    )
    assert client.get("/studies/pilot/protocol").json()["document"] == before
    decision = client.post(
        f"/studies/pilot/conversation/moves/{move_id}/decision",
        json={"status": "accepted", "decidedBy": "Test researcher"},
    )
    assert decision.status_code == 200, decision.text
    compiled = client.post("/studies/pilot/conversation/compile", json={}).json()
    assert compiled["valid"], compiled
    assert compiled["protocol"]["participants"]["design"] == "between-subjects"
    assert compiled["protocol"]["analysisPlan"][0]["recipes"] == [
        "two-group-nonparametric"
    ]
    assert (
        client.post(
            f"/studies/pilot/conversation/moves/{move_id}/decision",
            json={"status": "proposed", "decidedBy": "Test researcher"},
        ).status_code
        == 200
    )
    undone = client.post("/studies/pilot/conversation/compile", json={}).json()
    assert (
        undone["protocol"]["participants"]["design"] == before["participants"]["design"]
    )
    assert undone["protocol"]["analysisPlan"] == before["analysisPlan"]
    assert (
        client.post(
            f"/studies/pilot/conversation/moves/{move_id}/decision",
            json={"status": "accepted", "decidedBy": "Test researcher"},
        ).status_code
        == 200
    )
    compiled = client.post("/studies/pilot/conversation/compile", json={}).json()
    assert client.get("/studies/pilot/protocol").json()["document"] == before
    assert (
        client.post(
            "/studies/pilot/conversation/approve",
            json={
                "compilationId": compiled["compilationId"],
                "approvedBy": "Test researcher",
            },
        ).status_code
        == 200
    )
    exported = client.get("/studies/pilot/conversation/export").json()
    move = next(
        m for t in exported["turns"] for m in t["moves"] if m["moveId"] == move_id
    )
    snapshot = move["grounding"][0]["evidence"]
    assert move["decidedBy"] == "Test researcher"
    assert move["decidedAt"]
    assert snapshot["mapDigest"] == imported["digest"]
    assert (
        snapshot["candidate"]["sources"][0]["passage"]
        == evidence["relations"][0]["passage"]
    )
    archive = zipfile.ZipFile(
        io.BytesIO(client.get("/studies/pilot/data-bundle").content)
    )
    maps = json.loads(archive.read("files/evidence-maps.json"))
    assert maps[0]["document"] == evidence
    decisions = json.loads(archive.read("files/design-decisions.json"))
    assert (
        next(m for m in decisions if m["moveId"] == move_id)["grounding"][0]["evidence"]
        == snapshot
    )
    kit = client.get("/studies/pilot/replication-kit")
    assert kit.status_code == 200, kit.text
    with tarfile.open(fileobj=io.BytesIO(kit.content), mode="r:gz") as archive:
        member = next(
            name
            for name in archive.getnames()
            if name.endswith("/design-evidence.json")
        )
        record = json.loads(archive.extractfile(member).read())
    assert record["evidenceMaps"][0]["document"] == evidence
    assert record["approvals"]


def test_unreviewed_and_stale_proposals_are_blocked(client_designed, evidence, context):
    path = "/studies/pilot/evidence-map"
    assert client_designed.post(path + "/candidates", json={}).status_code == 409
    fingerprint = client_designed.put(path, json=evidence).json()["digest"]
    body = {
        **context.model_dump(),
        "candidateId": "fixture-study-1",
        "mapDigest": fingerprint,
        "requestId": "choice",
    }
    assert (
        client_designed.post(
            path + "/propose", json={**body, "confirmedRelationIds": []}
        ).status_code
        == 409
    )
    evidence["mapVersion"] = "0.2.0"
    client_designed.put(path, json=evidence)
    assert client_designed.post(path + "/propose", json=body).status_code == 409
