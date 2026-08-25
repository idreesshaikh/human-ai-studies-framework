"""Listening before proposing, and answering what was asked (FR-CONV-9/10)."""

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

from middleware import elicitation

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
    tc = TestClient(create_app(settings))
    tc.db_url = f"sqlite:///{settings.db_path}"
    return tc


def _ask(client, text, study=STUDY):
    res = client.post(f"/studies/{study}/conversation/turns", json={"text": text})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.parametrize(
    "text",
    [
        "why did you give me this?",
        "Why?",
        "why that template and not the other one",
        "what do you mean by counterbalanced?",
        "explain that",
        "on what basis?",
        "I asked why, you didn't answer",
        "how do you know that?",
    ],
)
def test_questions_about_prior_turns_are_recognised(text):
    assert elicitation.classify_turn(text) == "followup-question"


@pytest.mark.parametrize(
    "text",
    [
        "I don't know",
        "I dont know you help me",
        "not sure",
        "what?",
        "can you help me",
        "okay",
        "exactly",
        "same thing",
        "exactly the same thing",
        "yes indeed",
        "yes absolutely",
        "I've a sample example",
        "what else do you need",
    ],
)
def test_low_information_replies_request_scaffolding(text):
    assert elicitation.needs_scaffolding(text)
    assert elicitation.classify_turn(text) == "needs-scaffolding"


def test_a_question_about_a_prior_move_is_not_misclassified_as_stuck():
    assert not elicitation.needs_scaffolding("I don't know why you proposed that")
    assert (
        elicitation.classify_turn("I don't know why you proposed that")
        == "followup-question"
    )


@pytest.mark.parametrize(
    "text",
    [
        "what design and statistics should I use?",
        "which template do you recommend?",
        "just give me the design",
        "suggest a study design please",
        "skip the questions",
    ],
)
def test_explicit_design_requests_are_recognised(text):
    assert elicitation.classify_turn(text) == "design-request"


def test_a_description_is_not_a_question():
    assert elicitation.classify_turn(SKETCH) == "describe"


def test_a_real_description_covers_several_facets():
    understanding = elicitation.assess_understanding([SKETCH])
    assert understanding["population"]
    assert understanding["task"]
    assert understanding["comparison"]
    assert understanding["outcome"]
    assert elicitation.ready_for_design(understanding)


def test_a_complete_brief_uses_batch_intake():
    assert elicitation.is_complete_brief(SKETCH)
    assert not elicitation.is_complete_brief("I want to study developers")


def test_a_vague_opener_understands_nothing():
    understanding = elicitation.assess_understanding(["help me design a study"])
    assert not elicitation.ready_for_design(understanding)
    assert elicitation.next_question(understanding)


def test_only_the_researchers_own_words_count():
    """
    The platform asking about conditions cannot make the platform better informed  -
    assess_understanding is only ever given researcher turns.
    """
    understanding = elicitation.assess_understanding([])
    assert not any(understanding.values())


def test_an_explicit_request_lowers_the_bar_but_not_to_zero():
    nothing = elicitation.assess_understanding(["hello"])
    assert not elicitation.ready_for_design(nothing, requested=True)
    two = elicitation.assess_understanding(["students writing code"])
    assert sum(two.values()) == 2
    assert elicitation.ready_for_design(two, requested=True)
    assert not elicitation.ready_for_design(two)


def test_next_question_asks_one_thing():
    understanding = elicitation.assess_understanding(["developers"])
    question = elicitation.next_question(understanding)
    assert question.count("?") == 1


def test_a_vague_opener_gets_a_question_not_a_design(client):
    reply = _ask(client, "I want to study AI and productivity")
    assert [m for m in reply["moves"] if m["kind"] == "choose-template"] == []
    assert "?" in reply["text"], "the platform should be asking something"
    assert reply["understanding"]["readyForDesign"] is False
    assert reply["understanding"]["missing"]


def test_scope_gate_allows_students_when_they_are_programming():
    assert elicitation.classify_scope(
        ["Students debug a shared repository with and without an AI coding assistant."]
    ) == "supported"


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


def test_asking_for_a_design_from_nothing_does_not_produce_one(client):
    """The complaint: being boxed in immediately."""
    reply = _ask(client, "what design and statistics should I use?")
    assert reply["turnIntent"] == "design-request"
    assert [m for m in reply["moves"] if m["kind"] == "choose-template"] == []


def test_a_described_study_does_reach_a_design(client):
    """
    The gate must open  -  an elicitation loop with no exit is worse than proposing too
    early.
    """
    _ask(client, SKETCH)
    reply = _ask(client, "what design and statistics should I use?")
    assert reply["understanding"]["readyForDesign"] is True
    assert [m for m in reply["moves"] if m["kind"] == "choose-template"]


def test_why_gets_an_answer_not_new_proposals(client):
    """The reported defect: asked 'why?', the platform proposed new things."""
    _ask(client, SKETCH)
    proposed = _ask(client, "what design and statistics should I use?")
    assert proposed["moves"], "precondition: something was proposed to ask about"

    answer = _ask(client, "why did you give me this?")
    assert answer["turnIntent"] == "followup-question"
    assert [m for m in answer["moves"] if m["kind"] != "caution"] == []
    assert answer["text"]


def test_a_gated_turn_still_keeps_its_safe_moves(client):
    """
    Withholding the design shape is not a reason to withhold a grounded caution  -  the
    turn stays useful while it asks.
    """
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    assert reply["understanding"]["readyForDesign"] is False
    assert reply["moves"], "safe moves should survive the design gate"
    assert all(m["kind"] != "choose-template" for m in reply["moves"])


def test_understanding_accumulates_across_turns(client):
    """Facets are read from the whole conversation, not just this message."""
    first = _ask(client, "my participants are professional developers")
    assert first["understanding"]["readyForDesign"] is False
    later = _ask(client, "they refactor a legacy module, and I'll time them")
    known = later["understanding"]["known"]
    assert "population" in known and "task" in known


def test_stuck_researcher_gets_explanation_and_actionable_measure_card(client):
    _ask(
        client,
        "I want junior engineers to debug code with AI and without AI in a "
        "45-minute lab session.",
    )
    reply = _ask(client, "I don't know you help me")
    assert reply["turnIntent"] == "needs-scaffolding"
    assert "task time" in reply["text"]
    assert "correctness" in reply["text"]
    assert [m["kind"] for m in reply["moves"]] == ["add-measure"]


def test_every_profile_has_distinct_guidance():
    guidances = {k: elicitation.profile_guidance(k) for k in elicitation.PROFILES}
    assert len(set(guidances.values())) == len(elicitation.PROFILES)
    assert "STUDENT" in guidances["student"]
    assert "EXPERIENCED" in guidances["experienced"]
    assert "COMPANY" in guidances["industry"]


def test_an_unknown_profile_falls_back_to_the_default():
    assert elicitation.profile_guidance("chief-scientist") == (
        elicitation.profile_guidance(elicitation.DEFAULT_PROFILE)
    )
    assert elicitation.profile_guidance(None) == (
        elicitation.profile_guidance(elicitation.DEFAULT_PROFILE)
    )


def test_the_profile_catalog_is_served(client):
    body = client.get("/conversation/profiles").json()
    ids = {p["id"] for p in body["profiles"]}
    assert ids == {"student", "new-researcher", "experienced", "industry"}
    assert body["default"] in ids
    assert all(p["label"] and p["description"] for p in body["profiles"])


def test_the_profile_reaches_the_turn_directive(client):
    """
    A saved profile changes how the conversation talks (the directive the model is
    given), without changing what counts as sound method.
    """
    from middleware.db import make_session_factory
    from middleware.design_assistant import _directive, turn_stance

    factory = make_session_factory(client.db_url)
    with factory() as s:
        student = _directive(turn_stance(s, SKETCH, study_id=None, profile="student"))
        expert = _directive(
            turn_stance(s, SKETCH, study_id=None, profile="experienced")
        )
    assert "STUDENT" in student and "STUDENT" not in expert
    assert "EXPERIENCED" in expert
    assert ("enough to design" in student) == ("enough to design" in expert)


def test_a_researcher_naming_a_design_is_not_second_guessed(client):
    """
    The gate stops the *platform* boxing someone in  -  it was never meant to overrule a
    researcher who names the design themselves.
    """
    reply = _ask(client, "let's run a within-subjects crossover study")
    assert reply["understanding"]["readyForDesign"] is False
    assert [m for m in reply["moves"] if m["kind"] == "choose-template"], (
        "a design the researcher named must be recorded, not withheld"
    )


def test_asking_what_design_to_use_is_not_naming_one(client):
    """
    'what design should I use?' must not read as an answer to itself  -  'design' is a
    word in nearly every template's title.
    """
    reply = _ask(client, "what design should I use?")
    assert [m for m in reply["moves"] if m["kind"] == "choose-template"] == []


def test_naming_a_template_id_is_naming_a_design(client):
    """
    The repertoire's "describe your study instead" entry point seeds a study's opening
    turn with the template ids a researcher selected, so the assistant proposes the
    pairing rather than asking which shapes they mean. Naming an id must open the
    design gate  -  an explicit ask is never overruled by the facet gate.
    """
    from middleware.db import make_session_factory
    from middleware.design_assistant import turn_stance

    factory = make_session_factory(client.db_url)
    with factory() as s:
        stance = turn_stance(
            s, "merge metr-rct-v1 with survey-self-report-v1", study_id=None
        )
    assert stance["namedDesign"] is True
    assert stance["mayProposeDesign"] is True


def test_asking_why_about_a_named_design_still_answers(client):
    """
    A follow-up question never opens the gate, or 'why the crossover?' would re-propose
    the crossover instead of explaining it.
    """
    _ask(client, "let's run a within-subjects crossover study")
    reply = _ask(client, "why that crossover design?")
    assert reply["turnIntent"] == "followup-question"
    assert [m for m in reply["moves"] if m["kind"] != "caution"] == []


def test_understanding_summary_carries_the_next_question():
    """The UI shows the researcher what is being asked next."""
    understanding = elicitation.assess_understanding(["I want to study developers"])
    summary = elicitation.understanding_summary(understanding)

    assert summary["nextQuestion"] == elicitation.next_question(understanding)
    assert summary["nextQuestion"], "something is still missing, so something is asked"


def test_understanding_summary_asks_nothing_once_every_facet_is_known():
    understanding = dict.fromkeys(elicitation.FACETS, True)
    assert elicitation.understanding_summary(understanding)["nextQuestion"] == ""


def test_understanding_summary_labels_every_facet_not_just_missing_ones():
    """
    ``missingLabels`` names only what is absent, which is fine for a sentence about what
    is missing and useless for a checklist that has to name the steps already done.
    """
    understanding = elicitation.assess_understanding(["developers refactoring code"])
    summary = elicitation.understanding_summary(understanding)

    assert set(summary["facetLabels"]) == set(elicitation.FACETS)
    for facet, spec in elicitation.FACETS.items():
        assert summary["facetLabels"][facet] == spec["label"]
