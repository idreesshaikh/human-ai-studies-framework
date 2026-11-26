"""The bounded checklist path compiles without a conversational model."""

import json

import pytest
from fastapi.testclient import TestClient

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


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "broken \ud800 title"),
        ("researchQuestions", ["Does \udfff change debugging time?"]),
        ("conditions", ["AI-assisted", "without \ud800"]),
        ("participantDescription", "developers \ud800"),
        ("taskDescription", "Fix a Python bug \udfff"),
        ("additionalTaskDescription", "A task with \udfff"),
        ("measures", ["task completion time \ud800"]),
        ("measureIds", ["E1\ud800"]),
        ("existingMeasureIds", ["custom\udfff"]),
    ],
)
def test_checklist_rejects_broken_unicode_without_saving_a_draft(
    client_no_protocol, field, value
):
    response = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        content=json.dumps({**BODY, field: value}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]
    assert client_no_protocol.get("/studies/pilot/protocol").status_code == 404


def test_checklist_creates_a_compiler_verified_draft(client_no_protocol: TestClient):
    response = client_no_protocol.post("/studies/pilot/quick-protocol", json=BODY)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["valid"] is True, result
    assert result["templateId"] == "within-subjects-crossover-v1"
    assert result["selectedMeasures"] == BODY["measures"]
    assert result["protocol"]["study"]["title"] == BODY["title"]
    assert (
        result["protocol"]["researchQuestions"][0]["text"]
        == BODY["researchQuestions"][0]
    )
    assert (
        result["protocol"]["participants"]["description"]
        == BODY["participantDescription"]
    )
    assert result["protocol"]["measures"] == BODY["measures"]
    assert result["protocol"]["tasks"][0]["description"] == BODY["taskDescription"]

    conversation = client_no_protocol.get("/studies/pilot/conversation").json()
    assert conversation["turns"][-1]["source"] == "scripted"
    assert all(
        move["status"] == "accepted" for move in conversation["turns"][-1]["moves"]
    )


def test_long_task_description_round_trips_without_truncation(client_no_protocol):
    task = "Debug the supplied repository and document each change.\n\n" * 20
    response = client_no_protocol.post(
        "/studies/pilot/quick-protocol", json={**BODY, "taskDescription": task.strip()}
    )
    assert response.status_code == 200, response.text
    assert response.json()["protocol"]["tasks"][0]["description"] == task.strip()


def test_manual_entry_adds_a_distinct_task_and_preserves_it_on_edit(client_no_protocol):
    second = "Review a different repository with a seeded defect."
    created = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        json={**BODY, "additionalTaskDescription": second, "additionalTaskMinutes": 30},
    )
    assert created.status_code == 200, created.text
    tasks = created.json()["protocol"]["tasks"]
    assert len(tasks) == 2
    assert tasks[1]["description"] == second
    assert tasks[1]["minutes"] == 30
    assert tasks[0]["id"] != tasks[1]["id"]
    from protocol.assignment import assign

    for participant in range(2):
        blocks = assign(created.json()["protocol"], participant)
        assert len({block.condition for block in blocks}) == 2
        assert len({block.task_id for block in blocks}) == 2

    edited = client_no_protocol.post(
        "/studies/pilot/quick-protocol", json={**BODY, "title": "Revised study"}
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["protocol"]["tasks"] == tasks

    revised = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        json={**BODY, "taskDescription": "Fix a different Python bug."},
    )
    assert revised.status_code == 200, revised.text
    revised_tasks = revised.json()["protocol"]["tasks"]
    assert revised_tasks[0]["id"] == tasks[0]["id"]
    assert revised_tasks[0]["title"] == "Fix a different Python bug"
    assert revised_tasks[1] == tasks[1]


def test_additional_task_time_must_fit_session(client_no_protocol):
    response = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        json={
            **BODY,
            "additionalTaskDescription": "A second task",
            "additionalTaskMinutes": 46,
        },
    )
    assert response.status_code == 422


def test_manual_task_list_can_reorder_and_remove_tasks(client_no_protocol):
    created = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        json={
            **BODY,
            "taskEdits": [
                {
                    "title": "First task",
                    "description": "Fix the first seeded bug.",
                    "minutes": 15,
                },
                {
                    "title": "Second task",
                    "description": "Fix the second seeded bug.",
                    "minutes": 15,
                },
                {
                    "title": "Third task",
                    "description": "Review a third code change.",
                    "minutes": 15,
                },
            ],
        },
    )
    assert created.status_code == 200, created.text
    original = created.json()["protocol"]["tasks"]
    assert [task["title"] for task in original] == [
        "First task",
        "Second task",
        "Third task",
    ]

    revised = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        json={
            **BODY,
            "taskDescription": original[1]["description"],
            "taskEdits": [
                {
                    "id": original[1]["id"],
                    "title": original[1]["title"],
                    "description": original[1]["description"],
                    "minutes": 15,
                },
                {
                    "id": original[0]["id"],
                    "title": original[0]["title"],
                    "description": original[0]["description"],
                    "minutes": 15,
                },
            ],
        },
    )
    assert revised.status_code == 200, revised.text
    tasks = revised.json()["protocol"]["tasks"]
    assert [task["id"] for task in tasks] == [original[1]["id"], original[0]["id"]]
    assert [task["title"] for task in tasks] == ["Second task", "First task"]
    turns = client_no_protocol.get("/studies/pilot/conversation").json()["turns"]
    assert any(
        turn["text"].startswith("Updated the manual protocol:") for turn in turns
    )
    assert any(turn["text"].startswith("The manual draft is updated") for turn in turns)


def test_manual_task_times_account_for_tasks_per_participant(client_no_protocol):
    response = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        json={
            **BODY,
            "sessionMinutes": 45,
            "taskEdits": [
                {"description": "Fix the first seeded bug.", "minutes": 30},
                {"description": "Fix the second seeded bug.", "minutes": 20},
            ],
        },
    )
    assert response.status_code == 422
    assert "recorded task times exceed the session length" in response.json()["detail"]


def test_manual_task_time_counts_a_task_repeated_across_conditions(client_no_protocol):
    response = client_no_protocol.post(
        "/studies/pilot/quick-protocol",
        json={
            **BODY,
            "sessionMinutes": 45,
            "taskEdits": [
                {"description": "Fix the same seeded bug.", "minutes": 25},
            ],
        },
    )
    assert response.status_code == 422
    assert "recorded task times exceed the session length" in response.json()["detail"]


def test_manual_task_edit_keeps_custom_title_and_material_metadata():
    from middleware.schemas import QuickProtocolIn

    from middleware import compiler, study_plan

    task = {
        "id": "custom-task",
        "title": "Parser exercise",
        "description": "Fix the original bug.",
        "materials": "repository/example",
        "version": "v1",
    }
    current = {"protocolVersion": 6, "tasks": [task]}
    body = QuickProtocolIn(**{**BODY, "taskDescription": "Fix the updated bug."})
    moves = study_plan._moves(
        "study",
        body,
        questions=body.researchQuestions,
        conditions=body.conditions,
        measures=body.measures,
        current=current,
    )
    task_move = next(move for move in moves if move["kind"] == "declare-task")
    draft = {"protocolVersion": 6, "tasks": [task]}
    compiler._apply_task_moves(draft, [{**task_move, "status": "accepted"}])
    assert draft["tasks"] == [{**task, "description": "Fix the updated bug."}]


def test_manual_task_list_can_update_and_clear_materials_and_revision():
    from middleware.schemas import QuickProtocolIn

    from middleware import compiler, study_plan

    task = {
        "id": "custom-task",
        "title": "Parser exercise",
        "description": "Fix the original bug.",
        "materials": "repository/example",
        "version": "v1",
    }

    def compile_task_edit(materials: str, version: str) -> dict:
        body = QuickProtocolIn(
            **{
                **BODY,
                "taskDescription": "Fix the updated bug.",
                "taskEdits": [
                    {
                        "id": "custom-task",
                        "title": "Parser exercise",
                        "description": "Fix the updated bug.",
                        "minutes": None,
                        "materials": materials,
                        "version": version,
                    }
                ],
            }
        )
        moves = study_plan._moves(
            "study",
            body,
            questions=body.researchQuestions,
            conditions=body.conditions,
            measures=body.measures,
            current={"protocolVersion": 6, "tasks": [task]},
        )
        draft = {"protocolVersion": 6, "tasks": [task]}
        compiler._apply_task_moves(
            draft, [{**move, "status": "accepted"} for move in moves]
        )
        return draft["tasks"][0]

    updated = compile_task_edit("repository/revised", "v2")
    assert updated["materials"] == "repository/revised"
    assert updated["version"] == "v2"
    assert updated["title"] == "Parser exercise"
    cleared = compile_task_edit("", "")
    assert "materials" not in cleared
    assert "version" not in cleared


def test_checklist_rejects_unsupported_study_families(client_no_protocol: TestClient):
    body = {
        **BODY,
        "researchQuestions": ["Does exam pressure change student performance?"],
        "participantDescription": "students in an introductory course",
        "taskDescription": "Complete a timed course exam.",
    }

    response = client_no_protocol.post("/studies/pilot/quick-protocol", json=body)

    assert response.status_code == 422
    assert (
        "task-based human–AI software-development studies"
        in (response.json()["detail"])
    )


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
    # The study was designed in chat, so its measures are catalog-typed.
    typed = {**BODY, "measures": ["overall workload"], "measureIds": ["S8"]}
    client_designed.post("/studies/pilot/quick-protocol", json=typed)
    edited = {**typed, "title": "Edited debugging study"}
    response = client_designed.post("/studies/pilot/quick-protocol", json=edited)

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["valid"] is True, result
    assert result["protocol"]["study"]["title"] == edited["title"]
    assert [m["id"] for m in result["protocol"]["measures"]] == ["S8"]

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

    # An analysis chosen outside the checklist, as the evidence comparison does.
    from middleware.db import ConversationTurn, DesignMoveRow, make_session_factory

    factory = make_session_factory(f"sqlite:///{client_no_protocol.db_path}")
    with factory() as s:
        s.add(
            ConversationTurn(
                id="analysis-turn",
                study_id="pilot",
                seq=99,
                role="platform",
                created_at="",
            )
        )
        s.add(
            DesignMoveRow(
                id="analysis-turn:m1",
                study_id="pilot",
                turn_id="analysis-turn",
                seq=1,
                kind="prescribe-statistics",
                target="analysisPlan",
                proposal="Analyse with two-proportion.",
                patch={"recipeId": "two-proportion", "rq": "RQ-3"},
                grounding=[],
                status="accepted",
            )
        )
        s.commit()

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
