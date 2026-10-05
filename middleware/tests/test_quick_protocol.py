"""The bounded checklist path compiles without a conversational model."""

import model_double
from fastapi.testclient import TestClient

from middleware import assistant

BODY = {
    "title": "AI-assisted Python debugging",
    "researchQuestions": [
        "Does AI assistance change time and correctness when developers "
        "fix Python bugs?"
    ],
    "design": "within-subjects",
    "conditions": ["AI-assisted", "Unassisted"],
    "participantDescription": "novice Python developers",
    "plannedParticipants": 12,
    "taskDescription": "Fix a small Python bug in a provided repository.",
    "sessionMinutes": 45,
    "measures": ["task completion time", "solution correctness", "cognitive load"],
    "counterbalanced": True,
}


def test_checklist_creates_a_compiler_verified_draft(client_no_protocol: TestClient):
    response = client_no_protocol.post("/studies/pilot/quick-protocol", json=BODY)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["valid"] is True, result
    assert result["templateId"] == "within-subjects-crossover-v1"
    assert result["selectedMeasures"] == BODY["measures"]
    assert result["protocol"]["study"]["title"] == BODY["title"]
    assert result["protocol"]["researchQuestions"][0]["text"] == BODY[
        "researchQuestions"
    ][0]
    assert result["protocol"]["participants"]["description"] == BODY[
        "participantDescription"
    ]
    assert result["protocol"]["measures"] == BODY["measures"]
    assert result["protocol"]["tasks"][0]["description"] == BODY["taskDescription"]

    conversation = client_no_protocol.get("/studies/pilot/conversation").json()
    assert conversation["turns"][-1]["source"] == "scripted"
    assert all(
        move["status"] == "accepted"
        for move in conversation["turns"][-1]["moves"]
    )


def test_checklist_rejects_unsupported_study_families(client_no_protocol: TestClient):
    body = {
        **BODY,
        "researchQuestions": ["Does exam pressure change student performance?"],
        "participantDescription": "students in an introductory course",
        "taskDescription": "Complete a timed course exam.",
    }

    response = client_no_protocol.post("/studies/pilot/quick-protocol", json=body)

    assert response.status_code == 422
    assert "limited to task-based" in response.json()["detail"]


def test_checklist_rejects_duplicate_conditions(client_no_protocol: TestClient):
    response = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        json={**BODY, "conditions": ["AI-assisted", "ai-assisted"]},
    )

    assert response.status_code == 422
    assert "conditions must be different" in response.json()["detail"]


def test_checklist_supports_the_between_subjects_template(
    client_no_protocol: TestClient,
):
    body = {
        **BODY,
        "title": "Between-group debugging study",
        "design": "between-subjects",
        "plannedParticipants": 8,
        "counterbalanced": False,
    }

    response = client_no_protocol.post("/studies/pilot/quick-protocol", json=body)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["valid"] is True, result
    assert result["templateId"] == "two-group-rct-v1"
    assert result["protocol"]["participants"]["design"] == "between-subjects"
    assert result["protocol"]["participants"]["counterbalanced"] is False


def test_manual_entry_edits_an_existing_design_through_approval(
    client_designed: TestClient,
):
    client_designed.post("/studies/pilot/quick-protocol", json=BODY)
    edited = {**BODY, "title": "Edited debugging study", "measures": ["cognitive load"]}
    response = client_designed.post("/studies/pilot/quick-protocol", json=edited)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["valid"] is True, result
    assert result["protocol"]["study"]["title"] == edited["title"]
    assert result["protocol"]["measures"] == ["cognitive load"]

    compiled = client_designed.post(
        "/studies/pilot/conversation/compile", json={}
    ).json()
    assert compiled["protocol"] == result["protocol"]
    approved = client_designed.post(
        "/studies/pilot/conversation/approve",
        json={"compilationId": compiled["compilationId"], "approvedBy": "Owner"},
    )
    assert approved.status_code == 200, approved.text
    applied = client_designed.get("/studies/pilot/protocol").json()
    assert applied["title"] == edited["title"]


def test_editing_keeps_every_research_question_and_its_analysis(
    client_no_protocol: TestClient, monkeypatch
):
    questions = [
        BODY["researchQuestions"][0],
        "Does AI assistance change how often developers run the tests?",
        "Does AI assistance change how many fixes pass review first time?",
    ]
    body = {
        **BODY,
        "design": "between-subjects",
        "counterbalanced": False,
        "researchQuestions": questions,
    }
    entered = client_no_protocol.post("/studies/pilot/quick-protocol", json=body)
    assert entered.status_code == 200, entered.text
    assert [rq["text"] for rq in entered.json()["protocol"]["researchQuestions"]] == (
        questions
    )

    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: model_double.always(
            {
                "text": "Pass rates are proportions.",
                "moves": [model_double.prescription("two-proportion", "RQ-3")],
            }
        ),
    )
    reply = client_no_protocol.post(
        "/studies/pilot/conversation/turns",
        json={"text": "How should I analyse the review pass rate in RQ-3?"},
    ).json()
    for move in reply["moves"]:
        client_no_protocol.post(
            f"/studies/pilot/conversation/moves/{move['moveId']}/decision",
            json={"status": "accepted", "decidedBy": "Owner"},
        )

    edited = client_no_protocol.post(
        "/studies/pilot/quick-protocol", json={**body, "title": "Renamed study"}
    ).json()
    protocol = edited["protocol"]
    assert edited["valid"] is True, edited
    assert protocol["study"]["title"] == "Renamed study"
    assert [rq["text"] for rq in protocol["researchQuestions"]] == questions
    plan = {entry["rq"]: entry["recipes"] for entry in protocol["analysisPlan"]}
    assert plan["RQ-3"] == ["two-proportion"]


def test_research_questions_must_be_different(client_no_protocol: TestClient):
    response = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        json={**BODY, "researchQuestions": BODY["researchQuestions"] * 2},
    )

    assert response.status_code == 422
    assert "research questions must be different" in response.json()["detail"]


def test_task_proposal_has_no_template_prefix_or_doubled_full_stop(
    client_no_protocol: TestClient,
):
    response = client_no_protocol.post("/studies/pilot/quick-protocol", json=BODY)
    assert response.status_code == 200, response.text
    turn = client_no_protocol.get("/studies/pilot/conversation").json()["turns"][-1]
    task = next(m for m in turn["moves"] if m["kind"] == "declare-task")
    assert not task["proposal"].startswith("Declare the task")
    assert ".." not in task["proposal"]
    assert task["proposal"] == BODY["taskDescription"]
