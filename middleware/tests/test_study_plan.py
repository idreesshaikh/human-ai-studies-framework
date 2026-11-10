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
