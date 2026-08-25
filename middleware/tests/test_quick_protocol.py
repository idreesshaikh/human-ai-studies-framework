"""The bounded checklist path compiles without a conversational model."""

from fastapi.testclient import TestClient

BODY = {
    "title": "AI-assisted Python debugging",
    "researchQuestion": (
        "Does AI assistance change time and correctness when developers "
        "fix Python bugs?"
    ),
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
        "researchQuestion"
    ]
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
        "researchQuestion": "Does exam pressure change student performance?",
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
