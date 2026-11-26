"""Listening before proposing, and answering what was asked (FR-CONV-9/10)."""

import model_double
import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

from middleware import assistant, elicitation

STUDY = "elicit-study"

SKETCH = (
    "I want to see whether developers finish maintenance tasks faster with an "
    "AI assistant than without one, measuring task completion time."
)


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "elicit.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    return TestClient(create_app(settings))


def _ask(client, text, study=STUDY, **options):
    res = client.post(
        f"/studies/{study}/conversation/turns", json={"text": text, **options}
    )
    assert res.status_code == 200, res.text
    return res.json()


LABELLED_BRIEF = """Title: Copilot and bug fixing
Research question: Does AI assistance change time to fix a bug?
Participants: novice developers
Design: within-subjects, counterbalanced
Duration: 45 minutes
N = 24
Ethics: pending committee review
"""


def test_a_model_outage_saves_the_brief_without_proposing_cards(client, monkeypatch):
    monkeypatch.setattr(assistant, "make_design_client", model_double.outage)
    reply = _ask(client, LABELLED_BRIEF)
    assert reply["source"] == "unavailable"
    assert reply["moves"] == []
    turns = client.get(f"/studies/{STUDY}/conversation").json()["turns"]
    assert turns[0]["text"] == LABELLED_BRIEF


def test_explicit_task_answer_becomes_a_reviewable_plan_part(client, monkeypatch):
    model = model_double.always(
        model_double.talk("I’ll use that task.", taskDescription="Fix a Python bug")
    )
    monkeypatch.setattr(assistant, "make_design_client", lambda: model)
    reply = _ask(client, "Yes, they will fix a Python bug.")
    assert reply["source"] == "llm"
    (move,) = reply["moves"]
    assert move["kind"] == "set-plan"
    assert move["status"] == "proposed"
    assert move["patch"]["plan"] == {"taskDescription": "Fix a Python bug"}


def test_an_explicit_request_lowers_the_bar_but_not_to_zero():
    nothing = elicitation.assess_understanding(["hello"])
    assert not elicitation.ready_for_design(nothing, requested=True)
    two = elicitation.assess_understanding(["students writing code"])
    assert sum(two.values()) == 2
    assert elicitation.ready_for_design(two, requested=True)
    assert not elicitation.ready_for_design(two)


def test_a_vague_opener_can_return_a_question_without_cards(client, monkeypatch):
    question = "What coding task could your participants do?"
    model = model_double.always(model_double.talk("Let’s narrow the study.", question))
    monkeypatch.setattr(assistant, "make_design_client", lambda: model)
    reply = _ask(client, "I want to study AI and productivity")
    assert reply["moves"] == []
    assert reply["questions"] == [{"ask": question, "options": []}]
    assert reply["understanding"]["nextQuestion"]
    assert reply["understanding"]["readyForDesign"] is False
    assert reply["understanding"]["missing"]


def test_scope_gate_allows_students_when_they_are_programming():
    assert (
        elicitation.classify_scope(
            [
                "Students debug a shared repository with and without "
                "an AI coding assistant."
            ]
        )
        == "supported"
    )


def test_scope_gate_allows_a_programming_task_named_by_its_language():
    # The Peng et al. replication, in a researcher's own words: no "code" or
    # "developer", but plainly a software-development task.
    assert (
        elicitation.classify_scope(
            [
                "Does AI assistance change the time to a passing solution for "
                "university students?",
                "Implement the toy HTTP engine in JavaScript; 12 automated checks",
                "university students with basic JavaScript experience",
            ]
        )
        == "supported"
    )
    assert (
        elicitation.classify_scope(
            ["Students solve Python programming exercises with and without AI help."]
        )
        == "supported"
    )


def test_scope_gate_blocks_exam_and_other_non_developer_studies(client):
    exam = _ask(client, "Students complete a course exam with and without an AI tool.")
    assert exam["source"] == "scope"
    assert exam["moves"] == []
    assert "outside" in exam["text"].lower()

    other = _ask(
        client,
        "I want to compare customer satisfaction after two different support journeys "
        "in a service organisation.",
        study="other-scope-study",
    )
    assert other["source"] == "scope"
    assert other["moves"] == []


def test_a_design_request_can_ask_for_study_details(client, monkeypatch):
    question = "Who can you recruit?"
    model = model_double.always(
        model_double.talk("Recruitment depends on your study.", question)
    )
    monkeypatch.setattr(assistant, "make_design_client", lambda: model)
    reply = _ask(client, "what design and statistics should I use?")
    assert reply["moves"] == []
    assert reply["questions"] == [{"ask": question, "options": []}]


def test_a_described_study_can_reach_a_design_in_a_later_turn(client, monkeypatch):
    model = model_double.in_turn(
        [model_double.talk("Understood."), model_double.draft()]
    )
    monkeypatch.setattr(assistant, "make_design_client", lambda: model)
    _ask(client, SKETCH)
    reply = _ask(client, "what design and statistics should I use?")
    assert reply["understanding"]["readyForDesign"] is True
    assert any(m["patch"]["part"] == "design" for m in reply["moves"])


@pytest.mark.parametrize("question", ["Why did you give me this?", "Why that design?"])
def test_answers_only_followup_leaves_the_proposed_plan_intact(
    client, monkeypatch, question
):
    model = model_double.always(model_double.draft("Order effects matter here."))
    monkeypatch.setattr(assistant, "make_design_client", lambda: model)
    proposed = _ask(client, SKETCH)
    assert proposed["moves"], "precondition: something was proposed to ask about"

    answer = _ask(client, question, steer="checks")
    assert answer["moves"] == []
    assert answer["text"] == "Order effects matter here."
    turns = client.get(f"/studies/{STUDY}/conversation").json()["turns"]
    assert turns[1]["moves"][0]["status"] == "proposed"


def test_a_partial_description_can_propose_one_decision(client, monkeypatch):
    model = model_double.always(
        model_double.talk(
            "Let’s start here.", participantDescription="Junior developers"
        )
    )
    monkeypatch.setattr(assistant, "make_design_client", lambda: model)
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    assert reply["understanding"]["readyForDesign"] is False
    (move,) = reply["moves"]
    assert move["patch"]["plan"] == {"participantDescription": "Junior developers"}


def test_understanding_accumulates_across_turns(client):
    """Facets are read from the whole conversation, not just this message."""
    first = _ask(client, "my participants are professional developers")
    assert first["understanding"]["readyForDesign"] is False
    later = _ask(client, "they refactor a legacy module, and I'll time them")
    known = later["understanding"]["known"]
    assert "population" in known and "task" in known


def test_requested_measure_guidance_can_include_a_plan_card(client, monkeypatch):
    model = model_double.in_turn(
        [
            model_double.talk("Understood."),
            model_double.talk(
                "Start with task time and add correctness if the task allows it.",
                measureIds=["E1"],
            ),
        ]
    )
    monkeypatch.setattr(assistant, "make_design_client", lambda: model)
    _ask(
        client,
        "I want junior engineers to debug code with AI and without AI in a "
        "45-minute lab session.",
    )
    reply = _ask(client, "I don't know you help me")
    assert "task time" in reply["text"]
    assert "correctness" in reply["text"]
    (move,) = reply["moves"]
    assert move["patch"]["plan"] == {"measureIds": ["E1"]}


def test_the_profile_catalog_is_served(client):
    body = client.get("/conversation/profiles").json()
    ids = {p["id"] for p in body["profiles"]}
    assert ids == {"student", "new-researcher", "experienced", "industry"}
    assert body["default"] in ids
    assert all(p["label"] and p["description"] for p in body["profiles"])


def test_a_researcher_can_name_a_design_before_describing_everything(
    client, monkeypatch
):
    model = model_double.always(
        model_double.talk("A crossover works here.", design="within-subjects")
    )
    monkeypatch.setattr(assistant, "make_design_client", lambda: model)
    reply = _ask(client, "let's run a within-subjects crossover study")
    assert reply["understanding"]["readyForDesign"] is False
    (move,) = reply["moves"]
    assert move["patch"]["plan"] == {"design": "within-subjects"}


def test_template_ids_from_the_repertoire_reach_the_model(client, monkeypatch):
    requests = []
    model = model_double.silent(requests)
    monkeypatch.setattr(assistant, "make_design_client", lambda: model)
    message = "Could we combine metr-rct-v1 with survey-self-report-v1?"
    reply = _ask(client, message)
    assert reply["source"] == "llm"
    assert message in requests[0]["messages"][-1]["content"]


def test_understanding_summary_asks_nothing_once_every_facet_is_known():
    understanding = dict.fromkeys(elicitation.FACETS, True)
    assert elicitation.understanding_summary(understanding)["nextQuestion"] == ""


@pytest.mark.parametrize(
    "brief", [LABELLED_BRIEF, "Let's run a within-subjects study."]
)
def test_without_a_model_a_brief_is_saved_and_manual_setup_remains_available(
    client, monkeypatch, brief
):
    monkeypatch.setattr(assistant, "make_design_client", lambda: None)
    reply = _ask(client, brief)
    assert reply["source"] == "unavailable"
    assert reply["moves"] == []
    assert "checklist" in reply["text"]
    turns = client.get(f"/studies/{STUDY}/conversation").json()["turns"]
    assert turns[0]["text"] == brief
