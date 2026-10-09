"""Confirmed catalog choices survive authoring and never bypass study permissions."""

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings
from protocol.loader import validate_protocol

from middleware import compiler, design_llm


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "catalog.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
        auth="none",
    )
    with TestClient(create_app(settings)) as client:
        yield client


def study(client):
    return client.post(
        "/projects/implicit/studies", json={"name": "Catalog study"}
    ).json()["id"]


def test_catalog_and_suggestions_are_read_only_and_work_before_a_protocol(client):
    catalog = client.get("/measure-catalog")
    assert catalog.status_code == 200
    assert len(catalog.json()["measures"]) == 20
    sid = study(client)
    result = client.post(
        f"/studies/{sid}/measure-suggestions",
        json={
            "text": "time pressure",
            "design": "within-subjects",
            "requestId": "request-1",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["requestId"] == "request-1"
    assert result.json()["suggestions"][0]["id"] == "S4"
    assert result.json()["calibrated"] is False
    assert client.get(f"/studies/{sid}/conversation").json()["turns"] == []
    assert client.get("/projects/implicit").json()["studies"][0]["hasProtocol"] is False


@pytest.mark.parametrize(
    "body",
    [
        {"text": " ", "design": "within-subjects"},
        {"text": "effort", "design": "unknown"},
        {"text": "effort", "design": "within-subjects", "topK": 1000},
    ],
)
def test_suggestion_requests_are_bounded(client, body):
    sid = study(client)
    assert (
        client.post(f"/studies/{sid}/measure-suggestions", json=body).status_code == 422
    )


def test_signed_identity_is_required_for_the_catalog_and_suggestions(tmp_path):
    settings = Settings(
        db_path=tmp_path / "auth.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
        auth="token",
        token="synthetic-test-token",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/measure-catalog").status_code == 401
        assert (
            client.post(
                "/studies/private/measure-suggestions",
                json={"text": "effort", "design": "within-subjects"},
            ).status_code
            == 401
        )


def test_catalog_patch_is_preserved_and_hallucinated_fields_are_not_trusted():
    patch = design_llm._validate_patch(
        "add-measure",
        {
            "section": "measures",
            "op": "set",
            "value": {
                "catalogId": "S1",
                "fields": ["secret.data"],
                "analysisRecipe": "invented",
            },
        },
    )
    assert patch is not None
    assert patch["value"]["catalogId"] == "S1"
    assert "fields" not in patch["value"]
    assert "analysisRecipe" not in patch["value"]


@pytest.mark.parametrize(
    "template,ids",
    [
        ("within-subjects-crossover-v1", ["E1", "S1", "S10", "E3", "E9", "E10"]),
        ("two-group-rct-v1", ["E2", "S6", "S9"]),
    ],
)
def test_confirmed_measures_compile_with_their_capture_and_analysis(template, ids):
    moves = [
        {
            "kind": "choose-template",
            "status": "accepted",
            "patch": {"templateId": template, "parameters": {}},
        },
        {
            "kind": "add-measure",
            "status": "accepted",
            "patch": {
                "section": "measures",
                "op": "set",
                "value": [{"catalogId": ident} for ident in ids],
            },
        },
    ]
    result = compiler.compile_moves(moves)
    assert result.valid, (result.errors, result.unresolved)
    assert result.draft["protocolVersion"] == 6
    assert [row["id"] for row in result.draft["measures"]] == [
        ident for ident in ids if ident != "S10"
    ]
    assert validate_protocol(result.draft) == []
    if "S10" in ids:
        assert result.draft["covariate"]["timing"] == "pre-task"
        assert set(result.draft["instruments"]) >= {
            "surveys",
            "tern",
            "agentCapture",
            "metrics",
            "taskHarness",
        }
    else:
        assert "two-proportion" in result.draft["analysisPlan"][0]["recipes"]


def test_manual_catalog_choices_survive_apply_and_reach_a_saved_plan(client):
    sid = study(client)
    result = client.post(
        f"/studies/{sid}/quick-protocol",
        json={
            "title": "AI-assisted maintenance",
            "researchQuestions": [
                "Does AI assistance change time to passing tests during coding?"
            ],
            "design": "within-subjects",
            "conditions": ["unassisted", "ai-assisted"],
            "participantDescription": "professional software developers",
            "plannedParticipants": 20,
            "taskDescription": "Repair a Python function in VS Code "
            "and run acceptance tests.",
            "sessionMinutes": 45,
            "measures": ["time to first green", "mental demand"],
            "measureIds": ["E1", "S1"],
            "counterbalanced": True,
        },
    )
    assert result.status_code == 200, result.text
    compilation = result.json()
    assert compilation["valid"] is True
    assert len(compilation["protocol"]["researchQuestions"]) == 1
    assert len(compilation["protocol"]["analysisPlan"]) == 1
    assert set(compilation["protocol"]["analysisPlan"][0]["recipes"]) == {
        "paired-nonparametric",
        "typed-measures",
    }
    applied = client.post(
        f"/studies/{sid}/conversation/approve",
        json={
            "compilationId": compilation["compilationId"],
            "approvedBy": "Researcher",
        },
    )
    assert applied.status_code == 200, applied.text
    response = client.post(
        f"/studies/{sid}/plan",
        json={
            "design": "within-subjects",
            "test": "wilcoxon",
            "measure_id": "E1",
            "effect": 0.5,
            "simulations": 200,
            "max_n": 80,
            "planned_n": 20,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["required"]["totalN"] is not None


def test_typed_authoring_cannot_fall_back_when_custom_outcomes_are_unresolved(client):
    sid = study(client)
    body = {
        "title": "Mixed outcomes",
        "researchQuestions": [
            "Does AI affect mental demand and trust during programming?"
        ],
        "design": "within-subjects",
        "conditions": ["unassisted", "ai-assisted"],
        "participantDescription": "Python developers",
        "plannedParticipants": 20,
        "taskDescription": "Fix a Python maintenance task in VS Code.",
        "sessionMinutes": 45,
        "measures": ["mental demand", "trust in AI"],
        "measureIds": ["S1"],
        "typedMeasures": True,
    }
    assert client.post(f"/studies/{sid}/quick-protocol", json=body).status_code == 422
    body["measureIds"] = []
    assert client.post(f"/studies/{sid}/quick-protocol", json=body).status_code == 422


def test_manual_edits_keep_existing_measure_scale_wording_covariate_and_audit(client):
    import copy

    from protocol.measures import shipped_instruments

    from middleware import template_registry

    protocol = template_registry.instantiate_template(
        "within-subjects-crossover-v2", {}
    )["protocol"]
    legacy = next(
        row for row in shipped_instruments() if row["id"] == "legacy-tlx-inspired"
    )
    skill = next(row for row in shipped_instruments() if row["id"] == "pre-task-skill")
    legacy = copy.deepcopy(legacy)
    legacy["items"][0]["text"] = "Existing researcher wording"
    legacy["version"] = "1.1"
    protocol["instruments"]["surveys"] = [legacy, skill]
    protocol["measures"] = [
        {
            "id": "original-demand",
            "construct": "mental demand",
            "instrument": "legacy-tlx-inspired",
            "fields": ["survey_response.responses.mental_demand"],
            "analysisRecipe": "typed-measures",
            "version": "1.1",
        }
    ]
    protocol["covariate"] = {
        "instrument": "pre-task-skill",
        "field": "pre_task_covariate.score",
        "timing": "pre-task",
    }
    protocol["analysisPlan"] = [
        {"rq": "RQ-1", "recipes": ["typed-measures", "control_arm_audit"]}
    ]
    protocol["researchQuestions"] = [protocol["researchQuestions"][0]]
    sid = client.post(
        "/projects/implicit/studies",
        json={"name": "Existing scales", "protocol": protocol},
    ).json()["id"]
    result = client.post(
        f"/studies/{sid}/quick-protocol",
        json={
            "title": "Edited title",
            "researchQuestions": [protocol["researchQuestions"][0]["text"]],
            "design": "within-subjects",
            "conditions": protocol["conditions"],
            "participantDescription": "Python developers",
            "plannedParticipants": 20,
            "taskDescription": "Fix a Python maintenance task in VS Code.",
            "sessionMinutes": 45,
            "measures": ["mental demand"],
            "existingMeasureIds": ["original-demand"],
            "typedMeasures": True,
        },
    )
    assert result.status_code == 200, result.text
    saved = result.json()["protocol"]
    assert result.json()["valid"], result.text
    assert saved["measures"] == protocol["measures"]
    assert saved["instruments"]["surveys"] == protocol["instruments"]["surveys"]
    assert saved["covariate"] == protocol["covariate"]
    assert "control_arm_audit" in saved["analysisPlan"][0]["recipes"]
