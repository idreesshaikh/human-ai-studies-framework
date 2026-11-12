"""Chat and checklist edit one study plan; the compiler gates every draft."""

from __future__ import annotations

import json
import urllib.error

import pytest
import yaml
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

from middleware import assistant, compiler, study_plan

BRIEF = (
    "Does GitHub Copilot make professional developers faster at fixing bugs in an "
    "unfamiliar Java codebase, and does it change their perceived workload?"
)

PLAN = {
    "title": "Copilot and bug fixing",
    "researchQuestions": [
        "Does Copilot shorten the time to fix bugs in unfamiliar Java code?",
        "Does Copilot change developers' perceived workload?",
    ],
    "design": "within-subjects",
    "conditions": ["without AI", "with Copilot"],
    "participantDescription": "Professional Java developers",
    "plannedParticipants": 24,
    "taskDescription": "Fix two seeded bugs in an unfamiliar Java service.",
    "sessionMinutes": 60,
    "measureIds": ["E1", "S8"],
}


def _reply(plan=PLAN, **extra) -> dict:
    return {
        "reply": "Done.",
        "plan": plan,
        "assumed": ["plannedParticipants", "sessionMinutes"],
        "caution": "Order effects can remain after counterbalancing.",
        **extra,
    }


class _Model:
    """A scripted provider: replies in order, repeating the last one."""

    model = "test"
    api_key = "k"
    base_url = "https://example.invalid/chat/completions"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.bodies: list[dict] = []

    def post(self, url, body, headers):
        self.bodies.append(body)
        reply = self.replies[min(len(self.bodies), len(self.replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        content = reply if isinstance(reply, str) else json.dumps(reply)
        return {"choices": [{"message": {"content": content}}]}


def _built(turn: dict, base: list[dict] | None = None) -> compiler.CompileResult:
    return compiler.compile_moves(
        [*(base or []), *({**m, "status": "accepted"} for m in turn["moves"])]
    )


def _draft(plan=PLAN) -> dict:
    return _built(study_plan.propose(_Model(_reply(plan)), BRIEF, "s")).draft


# ------------------------------------------------------------------ opening brief


def test_a_brief_becomes_a_valid_v6_protocol_in_the_researchers_terms():
    built = _built(study_plan.propose(_Model(_reply()), BRIEF, "copilot-study"))
    assert built.valid, (built.errors, built.unresolved)
    protocol = yaml.safe_load(built.yaml)
    assert protocol["protocolVersion"] == 6
    assert protocol["study"]["title"] == "Copilot and bug fixing"
    assert protocol["conditions"] == ["without AI", "with Copilot"]
    assert protocol["participants"]["planned"] == 24
    assert [q["text"] for q in protocol["researchQuestions"]] == (
        PLAN["researchQuestions"]
    )
    constructs = {m["construct"] for m in protocol["measures"]}
    assert {"time to first green", "overall workload"} <= constructs


def test_the_opening_reply_names_what_was_assumed_and_the_validity_threat():
    text = study_plan.propose(_Model(_reply()), BRIEF, "s")["text"]
    assert "the number of participants" in text
    assert "the session length" in text
    assert "suggestions: the design" not in text
    assert "Order effects" in text


def test_the_model_sees_the_catalog_the_current_plan_and_the_message_verbatim():
    model = _Model(_reply())
    study_plan.propose(model, BRIEF, "s", current=_draft())
    system, user = model.bodies[0]["messages"]
    assert "E1: time to first green" in system["content"]
    assert BRIEF in user["content"]
    assert '"plannedParticipants": 24' in user["content"]


# -------------------------------------------------------------------- later turns


def test_plan_of_round_trips_a_built_draft():
    assert study_plan.plan_of(_draft()) == {**PLAN, "measureIds": ["E1", "S8"]}


def test_a_later_message_changes_only_what_was_asked():
    current = _draft()
    revised = {**PLAN, "plannedParticipants": 40}
    turn = study_plan.propose(
        _Model(_reply(revised, assumed=[])), "Make it 40 people.", "s", current=current
    )
    assert "Changed: the number of participants." in turn["text"]
    built = _built(turn)
    assert built.valid, (built.errors, built.unresolved)
    after = study_plan.plan_of(built.draft)
    assert after == {**study_plan.plan_of(current), "plannedParticipants": 40}


def test_a_question_is_answered_without_cards():
    answer = _reply(reply="Counterbalancing spreads order effects across arms.")
    turn = study_plan.propose(
        _Model(answer), "Why counterbalance?", "s", current=_draft()
    )
    assert turn == {
        "text": "Counterbalancing spreads order effects across arms.",
        "moves": [],
    }


def test_switching_design_re_derives_each_measures_analysis():
    turn = study_plan.propose(
        _Model(_reply({**PLAN, "design": "between-subjects"}, assumed=[])),
        "Use two separate groups instead.",
        "s",
        current=_draft(),
    )
    built = _built(turn)
    assert built.valid, (built.errors, built.unresolved)
    recipes = {m["id"]: m["analysisRecipe"] for m in built.draft["measures"]}
    assert recipes["E1"] == "two-group-nonparametric"


def test_measures_the_design_cannot_analyse_are_dropped():
    # Test success (E2) has no within-subjects analysis; it must not be offered.
    plan = {**PLAN, "measureIds": ["E2", "E1", "not-a-measure", "E1"]}
    turn = study_plan.propose(_Model(_reply(plan)), BRIEF, "s")
    measure = next(m for m in turn["moves"] if m["kind"] == "add-measure")
    assert measure["patch"]["value"] == [{"catalogId": "E1"}]


# ------------------------------------------------------------- hostile model output


@pytest.mark.parametrize(
    "reply",
    ["not json", ["a", "list"], {"text": "Noted.", "moves": []}, {"plan": "x"}, 7],
)
def test_output_that_is_not_a_plan_declines(reply):
    assert study_plan.propose(_Model(reply), BRIEF, "s") is None


@pytest.mark.parametrize(
    "envelope",
    [
        None,
        [],
        {},
        {"choices": {"0": {"message": {"content": "{}"}}}},
        {"choices": "not a list"},
        {"choices": [None]},
        {"choices": [{"message": []}]},
        {"choices": [{"message": {"content": {"plan": PLAN}}}]},
    ],
)
def test_malformed_provider_envelopes_decline_without_crashing(envelope):
    class EnvelopeModel(_Model):
        def post(self, url, body, headers):
            return envelope

    assert study_plan.propose(EnvelopeModel(), BRIEF, "s") is None


@pytest.mark.parametrize(
    "failure,reason",
    [
        (TimeoutError("down"), "down"),
        (ConnectionError("reset"), "down"),
        (
            urllib.error.HTTPError("https://x.invalid", 429, "Limited", {}, None),
            "limited",
        ),
    ],
)
def test_a_provider_outage_is_classified_without_multiplying_transport_retries(
    failure, reason
):
    model = _Model(failure)
    with pytest.raises(study_plan.Unreachable) as down:
        study_plan.propose(model, BRIEF, "s")
    assert down.value.reason == reason
    assert len(model.bodies) == 1


def test_a_retry_after_a_provider_outage_can_recover():
    model = _Model(TimeoutError("blip"), _reply())
    with pytest.raises(study_plan.Unreachable):
        study_plan.propose(model, BRIEF, "s")
    assert study_plan.propose(model, BRIEF, "s")["moves"]


@pytest.mark.parametrize("code", [401, 403])
def test_a_rejected_key_is_not_retried(code):
    refused = urllib.error.HTTPError("https://x.invalid", code, "Refused", {}, None)
    model = _Model(refused)
    with pytest.raises(study_plan.Unreachable) as down:
        study_plan.propose(model, BRIEF, "s")
    assert down.value.reason == "rejected" and len(model.bodies) == 1


@pytest.mark.parametrize(
    "broken",
    [
        {"design": "factorial"},
        {"design": {"name": "within-subjects"}},
        {"design": ["within-subjects"]},
        {"conditions": ["with AI", "With AI"]},
        {"conditions": ["only one"]},
        {"conditions": "AB"},
        {"conditions": 42},
        {"conditions": {"A": "with AI", "B": "without AI"}},
        {"measureIds": []},
        {"measureIds": "E1"},
        {"measureIds": 42},
        {"measureIds": {"E1": True}},
        {"measureIds": [{"id": "E1"}]},
        {"plannedParticipants": "many"},
        {"plannedParticipants": float("inf")},
        {"plannedParticipants": float("nan")},
        {"plannedParticipants": 24.5},
        {"plannedParticipants": -5},
        {"plannedParticipants": 10**9},
        {"sessionMinutes": 0},
        {"sessionMinutes": float("inf")},
        {"sessionMinutes": 45.5},
        {"sessionMinutes": {"value": 45}},
        {"researchQuestions": ["Why?"]},
        {"researchQuestions": []},
        {"researchQuestions": "Does AI change task completion time?"},
        {"researchQuestions": 42},
        {"title": ""},
        {"title": None},
        {"taskDescription": {"nested": "object"}},
    ],
)
def test_an_unusable_plan_is_explained_and_never_offered(broken):
    turn = study_plan.propose(_Model(_reply({**PLAN, **broken})), BRIEF, "s")
    assert turn["moves"] == []
    assert turn["text"]


@pytest.mark.parametrize("assumed", [42, "plannedParticipants", {"title": True}, None])
def test_malformed_optional_metadata_does_not_break_a_valid_plan(assumed):
    turn = study_plan.propose(_Model(_reply(assumed=assumed)), BRIEF, "s")
    assert _built(turn).valid
    assert "suggestions:" not in turn["text"]


def test_overlong_and_odd_strings_are_clipped_not_fatal():
    plan = {
        **PLAN,
        "title": "T" * 5000,
        "taskDescription": "Fix bugs \x00‮" + "x" * 5000,
        "participantDescription": "  developers\n\n\twith   spaces  ",
        "conditions": ["<script>alert(1)</script>", "with Copilot"],
    }
    built = _built(study_plan.propose(_Model(_reply(plan)), BRIEF, "s"))
    assert built.valid, (built.errors, built.unresolved)
    assert len(built.draft["study"]["title"]) <= 160
    assert built.draft["participants"]["description"] == "developers with spaces"
    # Stored as data; the web app renders text, never HTML.
    assert built.draft["conditions"][0] == "<script>alert(1)</script>"


def test_broken_unicode_from_a_model_cannot_poison_the_saved_reply(api):
    client, _ = api(
        _reply({**PLAN, "title": "Debugging \ud800 🔬"}, reply="A draft \udfff 🔬")
    )
    turn = _say(client, BRIEF)
    assert "🔬" in turn["text"]
    _accept_all(client, turn)
    compiled = _compile(client)
    assert compiled["valid"], compiled["errors"]
    assert "🔬" in compiled["protocol"]["study"]["title"]
    assert client.get("/studies/s1/conversation").status_code == 200


# ------------------------------------------------------ chat and checklist together


@pytest.fixture()
def api(tmp_path, monkeypatch):
    def make(*replies) -> tuple[TestClient, _Model]:
        model = _Model(*replies)
        monkeypatch.setattr(assistant, "make_client", lambda *a, **k: model)
        settings = Settings(
            db_path=tmp_path / "t.sqlite3",
            data_dir=tmp_path / "data",
            port=8000,
            spa_dist=tmp_path / "no-dist",
        )
        return TestClient(create_app(settings)), model

    return make


def _say(client: TestClient, text: str, **extra) -> dict:
    r = client.post("/studies/s1/conversation/turns", json={"text": text, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _accept_all(client: TestClient, turn: dict) -> None:
    for move in turn["moves"]:
        r = client.post(
            f"/studies/s1/conversation/moves/{move['moveId']}/decision",
            json={"status": "accepted", "decidedBy": "Researcher"},
        )
        assert r.status_code == 200, r.text


def _compile(client: TestClient) -> dict:
    r = client.post("/studies/s1/conversation/compile", json={})
    assert r.status_code == 200, r.text
    return r.json()


CHECKLIST = {
    "title": "Checklist study",
    "researchQuestions": ["Does an AI assistant change time to a passing test?"],
    "design": "within-subjects",
    "conditions": ["no assistant", "assistant"],
    "participantDescription": "Professional developers",
    "plannedParticipants": 20,
    "taskDescription": "Fix a failing test in a small Python service.",
    "sessionMinutes": 45,
    "measures": ["time to first green"],
    "measureIds": ["E1"],
    "typedMeasures": True,
    "counterbalanced": True,
}


def test_the_first_turn_offers_the_whole_draft_and_nothing_applies_unaccepted(api):
    client, model = api(_reply())
    turn = _say(client, BRIEF)
    assert turn["source"] == "llm"
    assert {m["status"] for m in turn["moves"]} == {"proposed"}
    assert not _compile(client)["valid"]  # nothing accepted yet

    _accept_all(client, turn)
    compiled = _compile(client)
    assert compiled["valid"], (compiled["errors"], compiled["unresolved"])
    assert compiled["protocol"]["protocolVersion"] == 6

    # Completing the draft points at the review, with no model call.
    calls = len(model.bodies)
    done = _say(
        client,
        "Accepted all proposals.",
        decision={"moveId": turn["moves"][-1]["moveId"], "action": "accepted"},
    )
    assert "Review draft" in done["text"] and done["moves"] == []
    assert len(model.bodies) == calls


def test_chat_continues_a_study_started_in_the_checklist(api):
    client, model = api(_reply())
    assert client.post("/studies/s1/quick-protocol", json=CHECKLIST).status_code == 200
    model.replies = [
        {
            "reply": "Raised to 36.",
            "plan": {
                **study_plan.plan_of(_compile(client)["protocol"]),
                "plannedParticipants": 36,
            },
            "assumed": [],
        }
    ]
    turn = _say(client, "Plan for 36 participants instead.")
    # The model was shown the checklist's plan, not an empty one.
    assert '"title": "Checklist study"' in model.bodies[-1]["messages"][-1]["content"]
    assert "Changed: the number of participants." in turn["text"]
    _accept_all(client, turn)
    protocol = _compile(client)["protocol"]
    assert protocol["participants"]["planned"] == 36
    assert protocol["study"]["title"] == "Checklist study"
    assert protocol["conditions"] == ["no assistant", "assistant"]


def test_the_checklist_continues_a_study_started_in_chat(api):
    client, _ = api(_reply())
    _accept_all(client, _say(client, BRIEF))
    plan = study_plan.plan_of(_compile(client)["protocol"])
    form = {
        **{k: v for k, v in plan.items() if k != "measureIds"},
        "sessionMinutes": 90,
        "measures": ["time to first green", "overall workload"],
        "measureIds": plan["measureIds"],
        "typedMeasures": True,
        "counterbalanced": True,
    }
    r = client.post("/studies/s1/quick-protocol", json=form)
    assert r.status_code == 200, r.text
    assert r.json()["valid"], (r.json()["errors"], r.json()["unresolved"])
    assert study_plan.plan_of(r.json()["protocol"]) == {**plan, "sessionMinutes": 90}


def test_a_new_message_refines_the_plan_still_awaiting_a_decision(api):
    client, model = api(_reply(), _reply({**PLAN, "plannedParticipants": 30}))
    _say(client, BRIEF)  # cards left undecided
    second = _say(client, "Actually 30 participants.")
    assert '"plannedParticipants": 24' in model.bodies[-1]["messages"][-1]["content"]
    _accept_all(client, second)
    assert _compile(client)["protocol"]["participants"]["planned"] == 30


def test_partial_acceptance_is_reported_not_papered_over(api):
    client, model = api(_reply())
    turn = _say(client, BRIEF)
    first = turn["moves"][0]["moveId"]
    client.post(
        f"/studies/s1/conversation/moves/{first}/decision",
        json={"status": "accepted", "decidedBy": "Researcher"},
    )
    calls = len(model.bodies)
    note = _say(client, "Accepted.", decision={"moveId": first, "action": "accepted"})
    assert "still waiting for your decision" in note["text"]
    assert len(model.bodies) == calls


# ------------------------------------------------------------- QA regressions


def test_a_declined_question_stays_out_of_the_protocol():
    turn = study_plan.propose(_Model(_reply()), BRIEF, "s")
    second = PLAN["researchQuestions"][1]
    decided = [
        {**m, "status": "rejected" if m["proposal"] == second else "accepted"}
        for m in turn["moves"]
    ]
    built = compiler.compile_moves(decided)
    assert built.valid, (built.errors, built.unresolved)
    assert [rq["text"] for rq in built.draft["researchQuestions"]] == [
        PLAN["researchQuestions"][0]
    ]
    # Accepting the card keeps it.
    assert len(_built(turn).draft["researchQuestions"]) == 2


def test_every_research_question_is_its_own_card_not_part_of_the_design():
    """The Design card used to end with "Research question: ...", so accepting
    it read as accepting a question while it filled five protocol sections."""
    turn = study_plan.propose(_Model(_reply()), BRIEF, "s")
    design = turn["moves"][0]
    assert design["kind"] == "choose-template"
    assert "Research question" not in design["proposal"]
    cards = [m["proposal"] for m in turn["moves"] if m["kind"] == "add-rq"]
    assert cards == PLAN["researchQuestions"]
    only_design = compiler.compile_moves(
        [
            {**m, "status": "accepted" if m is design else "proposed"}
            for m in turn["moves"]
        ]
    )
    assert not only_design.draft.get("researchQuestions")
    assert "the research question" in only_design.unresolved


def test_the_design_card_states_every_value_it_commits():
    plan = {**PLAN, "plannedParticipants": 24, "sessionMinutes": 45}
    turn = study_plan.propose(_Model(_reply(plan)), BRIEF, "s")
    card = turn["moves"][0]["proposal"]
    for fragment in ("without AI", "with Copilot", "24 participants", "45-minute"):
        assert fragment in card
    assert PLAN["title"] in card


def test_a_stated_45_minute_session_is_not_reported_as_assumed():
    plan = {**PLAN, "sessionMinutes": 45}
    built = _built(study_plan.propose(_Model(_reply(plan)), BRIEF, "s"))
    assert built.valid
    assert not any("not stated" in warning for warning in built.warnings)


def test_outcomes_the_plan_could_not_include_are_named_in_the_reply():
    plan = {**PLAN, "measureIds": ["E1", "E2"]}
    reply = {**_reply(plan), "reply": "I added E1 (time to first green) and E2."}
    turn = study_plan.propose(_Model(reply), BRIEF, "s")
    assert "Not added:" in turn["text"]
    assert "E1" not in turn["text"] and "E2 " not in turn["text"]


def test_long_model_prose_is_cut_at_a_sentence_not_mid_word():
    prose = "First sentence is here. " + "word " * 300
    clipped = study_plan._clip_reply(prose, 700)
    assert clipped.endswith(("…", "."))
    assert len(clipped) <= 701
    assert study_plan._clip_reply("One. Two three.", 700) == "One. Two three."


def test_a_plan_turn_still_recommends_literature(api, tmp_path):
    """The plan path used to return before retrieval, so chat turns that produced
    a plan carried no literature at all."""
    from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory

    from middleware import paper_index

    client, _ = api(_reply())
    factory = make_session_factory(f"sqlite:///{tmp_path / 't.sqlite3'}")
    with factory() as s:
        ref = "corpus:copilot-bug-fixing"
        title = "Copilot and bug fixing in unfamiliar Java code"
        why = "Developers fixing bugs with Copilot in an unfamiliar codebase."
        s.add(
            Paper(
                study_id=CORPUS_STUDY_ID,
                paper_ref=ref,
                title=title,
                abstract=why,
                tier="A",
                added_at="",
            )
        )
        paper_index.index_paper(s, ref, title, why)
        s.commit()

    turn = _say(client, BRIEF)
    assert turn["moves"], "the brief must still produce plan cards"
    refs = {r["ref"] for r in turn["recommendations"]}
    assert "corpus:copilot-bug-fixing" in refs
    # Recommendations persist with the turn, like the conversational path.
    stored = client.get("/studies/s1/conversation").json()["turns"]
    assert any(
        r["ref"] == "corpus:copilot-bug-fixing"
        for t in stored
        for r in t.get("recommendations") or []
    )


@pytest.mark.parametrize(
    ("prose", "plain"),
    [
        ("**E1** (time to first green) first", "**time to first green** first"),
        ("**E1 (time to first green)** first", "**time to first green** first"),
        ("E1 alone", "time to first green alone"),
        ("Z9 stays", "Z9 stays"),
    ],
)
def test_catalog_codes_become_plain_names_once(prose, plain):
    assert study_plan._plain_measure_names(prose) == plain


# ------------------------------------------------------------- cited literature

PAPERS = [
    {"ref": "corpus:copilot-speed", "title": "Copilot and developer speed"}
    | {"year": 2023},
    {"ref": "corpus:workload-ai", "title": "AI assistants and workload", "year": 2024},
]


def test_the_model_sees_the_retrieved_papers_by_id():
    model = _Model(_reply())
    study_plan.propose(model, BRIEF, "s", papers=PAPERS)
    prompt = model.bodies[0]["messages"][-1]["content"]
    assert "P1. Copilot and developer speed (2023)" in prompt
    assert "P2. AI assistants and workload (2024)" in prompt


def test_cards_cite_only_retrieved_papers():
    reply = _reply(
        sources={
            "design": ["P1", "P9"],
            "researchQuestions": [["P1"], ["P2", "invented"]],
            "measures": ["P2"],
            "task": [],
            "participants": "P1",
        }
    )
    turn = study_plan.propose(_Model(reply), BRIEF, "s", papers=PAPERS)
    cites = {
        (m["kind"], m["proposal"][:20]): m.get("cites") for m in turn["moves"]
    }
    by_kind = {}
    for (kind, _), refs in cites.items():
        by_kind.setdefault(kind, []).append(refs)
    assert by_kind["choose-template"] == [["corpus:copilot-speed"]]
    assert by_kind["add-rq"] == [["corpus:copilot-speed"], ["corpus:workload-ai"]]
    assert by_kind["add-measure"] == [["corpus:workload-ai"]]
    assert by_kind["declare-task"] == [[]]
    assert by_kind["set-field"] == [[]]  # a bare string is not a list of ids


def test_no_papers_means_no_citations_and_no_prompt_section():
    model = _Model(_reply(sources={"design": ["P1"]}))
    turn = study_plan.propose(model, BRIEF, "s")
    assert "P1." not in model.bodies[0]["messages"][-1]["content"]
    assert all(not m.get("cites") for m in turn["moves"])


def test_cited_papers_become_card_grounding(api, tmp_path):
    from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory

    from middleware import paper_index

    client, model = api(_reply())
    factory = make_session_factory(f"sqlite:///{tmp_path / 't.sqlite3'}")
    with factory() as s:
        ref = "corpus:copilot-bug-fixing"
        title = "Copilot and bug fixing in unfamiliar Java code"
        why = "Developers fixing bugs with Copilot in an unfamiliar codebase."
        s.add(
            Paper(
                study_id=CORPUS_STUDY_ID,
                paper_ref=ref,
                title=title,
                abstract=why,
                tier="A",
                added_at="",
            )
        )
        paper_index.index_paper(s, ref, title, why)
        s.commit()
    model.replies = [_reply(sources={"researchQuestions": [["P1"], []]})]
    turn = _say(client, BRIEF)
    first_rq = next(m for m in turn["moves"] if m["kind"] == "add-rq")
    assert [g["ref"] for g in first_rq["grounding"]] == ["corpus:copilot-bug-fixing"]
    assert "cites" not in first_rq


def test_answers_only_never_turns_a_message_into_plan_cards(api):
    """The plan path used to ignore the assistant style, so "Checks only" still
    received a full set of cards."""
    client, _ = api(_reply())
    turn = _say(client, BRIEF, steer="checks")
    assert turn["moves"] == []
    drafting = _say(client, BRIEF, steer="leads")
    assert drafting["moves"], "the default style still drafts the plan"
