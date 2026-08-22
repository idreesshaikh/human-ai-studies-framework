"""Design-conversation end-to-end tests."""

import json
from pathlib import Path

import model_double
import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.db import (
    CORPUS_STUDY_ID,
    ConversationTurn,
    DesignMoveRow,
    Paper,
    make_session_factory,
)
from middleware.settings import Settings

from middleware import assistant, paper_index

REPO_ROOT = Path(__file__).resolve().parents[2]

_SEEDS = [
    (
        "corpus:trust-in-ai-code-generation",
        "Investigating and Designing for Trust in AI-powered Code Generation",
        "Documents developer over-reliance on and trust in AI-generated code.",
    ),
    (
        "corpus:insecure-code-with-ai-assistants",
        "Do Users Write More Insecure Code with AI Assistants?",
        "Accepted AI code carries security defects users do not catch.",
    ),
    (
        "corpus:metr-early-2025-dev-productivity",
        "Measuring the Impact of Early-2025 AI on Developer Productivity",
        "Developers felt faster with AI while measurably slower.",
    ),
    (
        "corpus:guidelines-empirical-llm-se",
        "Guidelines for Empirical Studies of LLMs in SE",
        "Within-subjects plus counterbalancing for small-N developer studies.",
    ),
    ("corpus:realhumaneval", "RealHumanEval", "Benchmark score is not human utility."),
]

STUDY = "demo-study"


@pytest.fixture(autouse=True)
def _model(monkeypatch):
    """
    Every conversation test runs through the model path, because that is the only path:
    the design conversation requires a model and says so when it has none
    (``design_assistant.ModelUnavailable``).
    """
    monkeypatch.setattr(
        assistant, "make_client", lambda *a, **k: model_double.plausible()
    )


@pytest.fixture()
def client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    factory = make_session_factory(f"sqlite:///{settings.db_path}")
    with factory() as s:
        for ref, title, why in _SEEDS:
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
    return TestClient(create_app(settings))


def _ask(client: TestClient, text: str) -> dict:
    r = client.post(f"/studies/{STUDY}/conversation/turns", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def _accept(client: TestClient, move_id: str, status: str = "accepted") -> None:
    r = client.post(
        f"/studies/{STUDY}/conversation/moves/{move_id}/decision",
        json={"status": status, "decidedBy": "Researcher"},
    )
    assert r.status_code == 200, r.text


def _compile(client: TestClient) -> dict:
    r = client.post(f"/studies/{STUDY}/conversation/compile", json={})
    assert r.status_code == 200, r.text
    return r.json()


def test_design_turn_uses_the_single_mistral_route(client, monkeypatch):
    """Protocol-shaping replies do not select a provider tier at the call site."""
    requested: list[str | None] = []

    def capture_model(model=None):
        requested.append(model)
        return model_double.plausible()

    monkeypatch.setattr(assistant, "make_client", capture_model)
    _ask(client, "I want to study how developers review AI-generated code")
    assert requested
    assert all(model is None for model in requested)


def test_over_trust_moves_are_grounded_only_in_retrieved(client):
    """F2.1: every move's grounding ref was retrieved this exchange."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    assert reply["moves"], "the over-trust script must propose moves"
    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    grounded = [
        g for turn in export["turns"] for m in turn["moves"] for g in m["grounding"]
    ]
    assert grounded, "at least one move must be grounded"
    refs = {g["ref"] for g in grounded if g["ref"] != "none"}
    assert "corpus:trust-in-ai-code-generation" in refs
    assert len(reply["moves"]) == 1


def test_recommendations_surface_the_two_demo_papers(client):
    """F9.1 at the conversation layer: both demo papers among the cards."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    rec_refs = {r["ref"] for r in reply["recommendations"]}
    assert "corpus:trust-in-ai-code-generation" in rec_refs
    assert "corpus:insecure-code-with-ai-assistants" in rec_refs


def test_recommendations_survive_a_conversation_reload(client):
    """
    A tab switch / remount re-reads the conversation via GET rather than trusting client
    state  -  the literature rail must not go blank on that re-read (it used to:
    recommendations were only ever returned inline on the turn reply, never persisted).
    """
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    sent_refs = {r["ref"] for r in reply["recommendations"]}
    assert sent_refs

    reloaded = client.get(f"/studies/{STUDY}/conversation").json()
    platform_turn = next(t for t in reloaded["turns"] if t["role"] == "platform")
    reloaded_refs = {r["ref"] for r in platform_turn["recommendations"]}
    assert reloaded_refs == sent_refs


def test_recommendation_in_study_state_is_recomputed_after_add(client):
    """A stored recommendation reflects the current Library after a reload."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    recommendation = reply["recommendations"][0]
    assert recommendation["inStudy"] is False

    added = client.post(
        f"/studies/{STUDY}/papers/from-match",
        json={"ref": recommendation["ref"], "matchReason": "test"},
    )
    assert added.status_code == 200, added.text

    reloaded = client.get(f"/studies/{STUDY}/conversation").json()
    platform_turn = next(t for t in reloaded["turns"] if t["role"] == "platform")
    current = next(
        r for r in platform_turn["recommendations"] if r["ref"] == recommendation["ref"]
    )
    assert current["inStudy"] is True


def test_self_report_draws_metr_caution(client):
    """F2.2: measuring productivity by self-report alone gets the METR caution."""
    reply = _ask(client, "I'll measure productivity by self-report survey")
    cautions = [m for m in reply["moves"] if m["kind"] == "caution"]
    assert cautions, "a self-report-only claim must draw a caution"
    refs = {g["ref"] for m in cautions for g in m["grounding"]}
    assert "corpus:metr-early-2025-dev-productivity" in refs


_STUDY_SKETCH = (
    "I want to see whether developers finish maintenance tasks faster with "
    "an AI assistant than without one, in 45-minute lab sessions, "
    "measuring task completion time and correctness."
)


def _drive_to_valid_draft(client) -> dict:
    """
    Accept the template-choice move the design script proposes → a complete, validating
    protocol draft, all in-conversation (F1.1).
    """
    _ask(client, _STUDY_SKETCH)
    reply = _ask(client, (
        "what design and statistics should I use? I was thinking "
        "within-subjects, with each developer doing both conditions "
        "counterbalanced"
    ))
    template_moves = [m for m in reply["moves"] if m["kind"] == "choose-template"]
    assert template_moves, "the design script must propose a template"
    for m in template_moves:
        _accept(client, m["moveId"])
    return _compile(client)


def test_empty_to_validating_draft_in_conversation(client):
    """
    F1.1: from an empty study, reach a draft that passes validation without leaving the
    conversation surface.
    """
    result = _drive_to_valid_draft(client)
    assert result["valid"], result["errors"]
    assert result["unresolved"] == []
    assert result["templateId"] == "metr-rct-v1"


def test_compile_is_deterministic(client):
    """F3.1: replaying the same accepted moves yields byte-identical YAML."""
    first = _drive_to_valid_draft(client)
    second = _compile(client)
    assert first["yaml"] == second["yaml"]


def test_delete_removes_a_study_with_moves_and_an_approval(client):
    """
    A study with design moves and an approved compilation has rows that reference each
    other (design_moves.turn_id -> conversation_turns.id, approvals.compilation_id ->
    compilations.id) - deleting them in the wrong order is invisible on SQLite (no FK
    enforcement by default) but fails outright on Postgres, the production default,
    leaving the study stuck and the delete button looking like a no-op.
    """
    from sqlalchemy import event

    from middleware import db as db_mod

    def _enable_fk(dbapi_connection, connection_record, connection_proxy):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(db_mod._engine, "checkout", _enable_fk)
    try:
        created = client.post("/projects/implicit/studies", json={"name": STUDY})
        assert created.status_code == 200, created.text
        assert created.json()["id"] == STUDY

        result = _drive_to_valid_draft(client)
        approved = client.post(
            f"/studies/{STUDY}/conversation/approve",
            json={"compilationId": result["compilationId"], "approvedBy": "Owner"},
        )
        assert approved.status_code == 200, approved.text

        deleted = client.delete(f"/studies/{STUDY}")
        assert deleted.status_code == 200, deleted.text
    finally:
        event.remove(db_mod._engine, "checkout", _enable_fk)


def test_study_created_with_seeded_protocol_draft(client):
    """
    Templates-first (P1-2): creating a study with a ``protocol`` body lands that
    protocol as the draft, so the design conversation continues from a merged template
    instead of a blank page (compiles take the current draft as their base).
    """
    protocol = {
        "study": {"title": "Seeded", "design": "within-subjects"},
        "researchQuestions": [{"id": "RQ-1", "text": "A question?"}],
    }
    r = client.post(
        "/projects/implicit/studies", json={"name": "Seeded", "protocol": protocol}
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == "seeded"

    export = client.get("/studies/seeded/conversation/export").json()
    assert "Seeded" in export["currentDraft"]
    assert "RQ-1" in export["currentDraft"]


def test_study_rejects_non_protocol_seed(client):
    """
    A seed that is not a compiled protocol (no study/researchQuestions) is a 422 naming
    the shape  -  and leaves no half-created study row.
    """
    r = client.post(
        "/projects/implicit/studies",
        json={"name": "Broken", "protocol": {"foo": "bar"}},
    )
    assert r.status_code == 422, r.text
    retry = client.post("/projects/implicit/studies", json={"name": "Broken"})
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == "broken"


def test_no_draft_applies_without_approval(client):
    """
    F3.3: the current draft is empty until an approval is recorded; the approval carries
    the approver's role (audit).
    """
    result = _drive_to_valid_draft(client)
    before = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert before["currentDraft"] == ""
    assert before["approvals"] == []

    r = client.post(
        f"/studies/{STUDY}/conversation/approve",
        json={"compilationId": result["compilationId"], "approvedBy": "Owner"},
    )
    assert r.status_code == 200, r.text
    after = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert after["currentDraft"] == result["yaml"]
    assert len(after["approvals"]) == 1
    assert after["approvals"][0]["role"] in ("owner", "member")


def test_rejecting_a_move_keeps_it_out_of_the_draft(client):
    """
    F1.2: moves are individually decidable; a rejected move leaves no trace in the
    compiled draft.
    """
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    rq_moves = [m for m in reply["moves"] if m["kind"] == "add-rq"]
    assert rq_moves
    _accept(client, rq_moves[0]["moveId"], status="rejected")
    result = _compile(client)
    assert rq_moves[0]["patch"]["value"] not in result["yaml"]


def test_undoing_a_decision_reopens_the_move(client, tmp_path):
    """
    A decided move can be reopened back to 'proposed'  -  undo, not just accept/reject.
    """
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    rq_moves = [m for m in reply["moves"] if m["kind"] == "add-rq"]
    assert rq_moves
    move_id = rq_moves[0]["moveId"]

    _accept(client, move_id, status="accepted")
    compiled = _compile(client)
    assert rq_moves[0]["patch"]["value"] in compiled["yaml"]

    r = client.post(
        f"/studies/{STUDY}/conversation/moves/{move_id}/decision",
        json={"status": "proposed", "decidedBy": "Researcher"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {
        "moveId": move_id,
        "status": "proposed",
        "papersAdded": [],
    }

    reopened = _compile(client)
    assert rq_moves[0]["patch"]["value"] not in reopened["yaml"]

    factory = make_session_factory(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    with factory() as s:
        mv = s.get(DesignMoveRow, move_id)
        assert mv.decided_by == ""
        assert mv.decided_at == ""


def test_evasive_conversation_names_unresolved_slots(client):
    """
    F1.3: a vague opener that accepts no structural moves ends with named unresolved
    slots, not silent gaps.
    """
    _ask(client, "hmm, I'm not sure what I want to study yet")
    result = _compile(client)
    assert not result["valid"]
    assert result["unresolved"], "empty draft must name its unresolved slots"
    # The scaffold's errors must name only real, currently-satisfiable gaps  -  'kite'
    # was
    # the pre-rename instrument key (v1/v2 schema branch); nothing has written it since
    # 'tern', so it must never appear as an error a researcher is asked to resolve.
    assert not any("kite" in e for e in result["errors"])


def test_unsourced_move_compiles_with_grounding_recorded(client, monkeypatch):
    """
    F2.3: a move the literature can't settle - a scoping decision that is the
    researcher's own - still compiles, and the record marks it ungrounded rather than
    borrowing a citation to look sourced.
    """
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: model_double.always(
            {
                "text": "Your call, not the literature's.",
                "moves": [
                    model_double.move(
                        "set-parameter",
                        "conditions",
                        "Experience level: junior vs. senior",
                    )
                ],
            }
        ),
    )
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    unsourced = [m for m in reply["moves"] if not m["grounding"]]
    assert unsourced, "a researcher-judgment move should be unsourced"
    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    all_moves = [m for t in export["turns"] for m in t["moves"]]
    assert any(m["grounding"] == [] for m in all_moves)


def test_invalid_draft_cannot_be_approved(client):
    """
    F3.2/F3.3: a scaffold that fails validation returns errors/unresolved and cannot be
    applied  -  a conversation never silently produces (or applies) an invalid draft.
    """
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    for m in reply["moves"]:
        _accept(client, m["moveId"])
    result = _compile(client)
    assert not result["valid"]
    r = client.post(
        f"/studies/{STUDY}/conversation/approve",
        json={"compilationId": result["compilationId"], "approvedBy": "Owner"},
    )
    assert r.status_code == 409


def test_export_renders_the_full_chain(client):
    """
    F6.1: the elicitation export carries the chain  -  turns → moves → grounding →
    compilation → approval  -  navigable in both directions.
    """
    result = _drive_to_valid_draft(client)
    client.post(
        f"/studies/{STUDY}/conversation/approve",
        json={"compilationId": result["compilationId"], "approvedBy": "Owner"},
    )
    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert export["turns"] and export["compilations"] and export["approvals"]
    comp = export["compilations"][-1]
    assert comp["moveIds"]
    move_ids = {m["moveId"] for t in export["turns"] for m in t["moves"]}
    assert set(comp["moveIds"]) <= move_ids
    assert export["approvals"][-1]["compilationId"] == comp["compilationId"]


def test_reloading_the_conversation_recomputes_understanding(client):
    """
    A reload used to blank the understanding line until the next turn was sent  -
    `understanding` was only ever set from a turn's own reply, never recomputed from the
    stored history.
    """
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    conversation = client.get(f"/studies/{STUDY}/conversation").json()
    assert conversation["understanding"] == reply["understanding"]


def _fake_llm(reply_json: dict):
    """A model that gives one fixed reply (``model_double.always``)."""
    return model_double.always(reply_json)


def test_llm_configured_and_healthy_produces_an_llm_sourced_turn(client, monkeypatch):
    reply = {
        "text": "Let's ground this in the corpus.",
        "moves": [
            {
                "kind": "add-measure",
                "target": "measures[]",
                "proposal": "Measure review latency.",
                "patch": {
                    "section": "measures",
                    "op": "append",
                    "value": "Review latency",
                },
                "refs": ["corpus:trust-in-ai-code-generation"],
            }
        ],
    }
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _fake_llm(reply))
    turn = _ask(client, "junior developers over-trust AI code")
    assert turn["source"] == "llm"
    assert turn["text"] == "Let's ground this in the corpus."
    assert len(turn["moves"]) == 1
    assert turn["moves"][0]["kind"] == "add-measure"
    grounded_refs = {g["ref"] for g in turn["moves"][0]["grounding"]}
    assert grounded_refs == {"corpus:trust-in-ai-code-generation"}


def test_prose_only_model_turn_gets_one_guided_decision_card(client, monkeypatch):
    """A model's prose must still resolve into the platform's next decision."""
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: model_double.silent())

    turn = _ask(client, "I want to research how junior engineers use AI")

    assert turn["source"] == "llm"
    assert len(turn["moves"]) == 1
    assert turn["moves"][0]["kind"] == "declare-task"
    assert turn["moves"][0]["grounding"] == []


def test_rejected_guided_card_turns_into_a_concrete_choice(client, monkeypatch):
    """Rejecting a default must change the next turn instead of replaying it."""
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: model_double.silent())

    first = _ask(client, "I want to research how junior engineers use AI")
    move = first["moves"][0]
    _accept(client, move["moveId"], status="rejected")

    next_turn = _ask(client, "what?")

    assert next_turn["moves"] == []
    assert "actual work" in next_turn["text"]
    assert move["proposal"] not in next_turn["text"]


def test_a_provider_outage_yields_a_holding_turn_never_a_fake_one(
    client, monkeypatch
):
    """A failing provider ends the turn honestly, without ending the session."""
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: model_double.outage())
    r = client.post(
        f"/studies/{STUDY}/conversation/turns",
        json={"text": "I think junior developers over-trust AI-generated code"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "unavailable"
    assert body["moves"] == []
    assert body["recommendations"] == []
    assert body["text"]


def test_a_holding_turn_survives_a_reload(client, monkeypatch):
    """
    The explanation of why nothing answered matters most exactly when the researcher
    comes back to a silent thread  -  so it has to still be there after a reload, not
    just for the one browser session that happened to be open when it failed.
    """
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: model_double.outage())
    client.post(f"/studies/{STUDY}/conversation/turns", json={"text": "a thought"})

    turns = client.get(f"/studies/{STUDY}/conversation").json()["turns"]
    assert [t["role"] for t in turns] == ["researcher", "platform"]
    assert turns[0]["text"] == "a thought"
    assert turns[1]["source"] == "unavailable"
    assert turns[1]["text"]


def test_a_holding_turn_is_never_replayed_to_the_model(tmp_path, monkeypatch):
    """
    Persisted for display is not the same as part of the design record. A holding
    turn still must never reach the model as history on a later, real turn  -  a stored
    "I couldn't reach the model" replayed back in would be a fabricated assistant turn,
    and the model would answer as though it had said that itself.
    """
    from middleware import design_assistant as da

    settings = Settings(
        db_path=tmp_path / "replay.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    factory = make_session_factory(f"sqlite:///{settings.db_path}")
    local_client = TestClient(create_app(settings))

    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: model_double.outage())
    local_client.post(
        f"/studies/{STUDY}/conversation/turns", json={"text": "a thought"}
    )

    with factory() as s:
        history = da._load_history(s, STUDY)
    assert all("couldn't reach" not in h["content"].lower() for h in history)
    assert all(h["role"] == "user" for h in history), (
        "the only turn on record is the researcher's own  -  the holding turn must "
        "not surface as a fabricated assistant message"
    )


def test_the_researchers_own_turn_survives_a_model_outage(client, monkeypatch):
    """They should never have to retype what they said because the model was down."""
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: model_double.outage())
    client.post(
        f"/studies/{STUDY}/conversation/turns", json={"text": "a thought I typed once"}
    )
    turns = client.get(f"/studies/{STUDY}/conversation").json()["turns"]
    assert any(t["text"] == "a thought I typed once" for t in turns)


def test_no_model_configured_names_the_setting_that_fixes_it(client, monkeypatch):
    """
    No key at all is a different cause from an outage, so it gets a different sentence:
    the one that says what to do about it.
    """
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: None)
    r = client.post(
        f"/studies/{STUDY}/conversation/turns", json={"text": "anything at all"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "unavailable"
    assert "MISTRAL_API_KEY" in body["text"]


def test_a_flaky_provider_is_retried_before_giving_up(client, monkeypatch):
    """
    A blip - a 429, a truncated body - is the common failure and is usually gone by the
    next call, so one retry saves the turn.
    """
    calls = {"n": 0}
    good = model_double.always(
        {"text": "Second time lucky.", "moves": []}
    )

    def flaky(url, body, headers):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("one blip")
        return good.post(url, body, headers)

    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: assistant.MistralProvider("test-key", post=flaky),
    )
    turn = _ask(client, "does a blip lose my turn?")
    assert turn["source"] == "llm"
    assert turn["text"] == "Second time lucky."
    assert calls["n"] > 1, "the first attempt must have been retried"


_LATENCY_MOVE = {
    "kind": "add-measure",
    "target": "measures[]",
    "proposal": "Measure review latency.",
    "patch": {"section": "measures", "op": "append", "value": "Review latency"},
    "refs": ["corpus:trust-in-ai-code-generation"],
}
_CONDITIONS_MOVE = {
    "kind": "set-parameter",
    "target": "conditions",
    "proposal": "Run a three-arm condition split.",
    "patch": {"section": "conditions", "op": "set", "value": "three arms"},
    "refs": [],
}


def _capturing_llm(reply_json: dict, captured: list):
    """A fixed-reply model that also records every request body sent."""

    def post(url, body, headers):
        captured.append(body)
        return {"choices": [{"message": {"content": json.dumps(reply_json)}}]}

    return assistant.MistralProvider("test-key", post=post)


def test_accepted_move_is_not_reproposed(client, monkeypatch):
    """
    Server-side guard: even an LLM that ignores its instructions and re-emits an
    accepted move verbatim never repeats it to the researcher.
    """
    reply = {"text": "A grounded measure.", "moves": [_LATENCY_MOVE]}
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _fake_llm(reply))
    turn = _ask(client, "junior developers over-trust AI code")
    assert len(turn["moves"]) == 1
    _accept(client, turn["moves"][0]["moveId"])
    again = _ask(client, "what should we measure?")
    assert again["source"] == "llm"
    assert again["moves"] == []


def test_design_state_reaches_the_llm(client, monkeypatch):
    """
    The second turn's request carries the structured design state: the accepted and
    rejected moves by name, and the still-empty sections.
    """
    reply = {"text": "One measure.", "moves": [_LATENCY_MOVE]}
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _fake_llm(reply))
    turn = _ask(client, "junior developers over-trust AI code")
    _accept(client, turn["moves"][0]["moveId"])

    comparison_reply = {"text": "One condition choice.", "moves": [_CONDITIONS_MOVE]}
    monkeypatch.setattr(
        assistant, "make_client", lambda *a, **k: _fake_llm(comparison_reply)
    )
    comparison = _ask(client, "what should we compare?")
    _accept(client, comparison["moves"][0]["moveId"], status="rejected")

    captured: list = []
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: _capturing_llm({"text": "Noted.", "moves": []}, captured),
    )
    _ask(client, "what next?")
    user = next(
        body["messages"][-1]["content"]
        for body in captured
        if "Candidate menu this turn:" in body["messages"][-1]["content"]
    )
    assert "Design state so far:" in user
    assert "Accepted (already in the draft, do not re-propose):" in user
    assert "Measure review latency." in user
    assert "Rejected (the researcher said no, do not re-pitch):" in user
    assert "Run a three-arm condition split." in user
    assert "participants" in user.split("Empty:")[-1]


def test_a_re_proposed_move_never_reaches_the_researcher_twice(client, monkeypatch):
    """
    Enforcement, not instruction: the prompt asks the model not to repeat itself, and
    this guarantees it regardless of whether the model complies.
    """
    reply = {
        "text": "Here's a measure.",
        "moves": [
            model_double.move(
                "add-measure",
                "measures",
                "Review latency before accept/reject",
                refs=("corpus:trust-in-ai-code-generation",),
            )
        ],
    }
    monkeypatch.setattr(
        assistant, "make_client", lambda *a, **k: model_double.always(reply)
    )
    first = _ask(client, "how should I measure review depth?")
    assert len(first["moves"]) == 1
    _accept(client, first["moves"][0]["moveId"])

    second = _ask(client, "how should I measure review depth?")
    assert second["moves"] == [], "an accepted move must never be re-pitched"


def _conversation_request(captured: list) -> str:
    """
    The design-conversation user message among captured LLM request bodies (the same
    client also serves matching's query-expansion call).
    """
    return next(
        body["messages"][-1]["content"]
        for body in captured
        if "Candidate menu this turn:" in body["messages"][-1]["content"]
    )


def test_template_leaves_statistical_plan_and_ethics_open(client, monkeypatch):
    """
    An accepted template fills only the design slot (mirroring the researcher-visible
    meter)  -  statisticalPlan and ethics stay listed as empty, and the state invites
    recording the template's prescription instead of forbidding statisticalPlan moves.
    """
    template_move = {
        "kind": "choose-template",
        "target": "design",
        "proposal": "Adopt the METR paired-RCT design.",
        "patch": {"templateId": "metr-rct-v1", "parameters": {}},
        "refs": [],
    }
    reply = {"text": "A design.", "moves": [template_move]}
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _fake_llm(reply))
    turn = _ask(client, "let's run a paired RCT design like the METR study")
    assert turn["moves"], "the choose-template move must survive"
    _accept(client, turn["moves"][0]["moveId"])

    captured: list = []
    ethics_move = {
        "kind": "set-parameter",
        "target": "ethics",
        "proposal": "Consent covers behavioral capture; aggregates only.",
        "patch": {
            "section": "ethics",
            "op": "append",
            "value": "Consent covers behavioral capture; aggregates only",
        },
        "refs": [],
    }
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: _capturing_llm(
            {"text": "An ethics posture.", "moves": [ethics_move]}, captured
        ),
    )
    turn2 = _ask(client, "what about the ethics posture?")
    user = _conversation_request(captured)
    filled_part = user.split("Draft coverage  -  filled:")[-1].split("Empty:")[0]
    empty_part = user.split("Empty:")[-1]
    assert "design" in filled_part
    assert "statisticalPlan" in empty_part
    assert "ethics" in empty_part
    assert "record or refine that prescription" in user
    assert "do not propose a standalone statisticalPlan move" not in user

    _accept(client, turn2["moves"][0]["moveId"])
    captured.clear()
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: _capturing_llm({"text": "Noted.", "moves": []}, captured),
    )
    _ask(client, "what next?")
    user = _conversation_request(captured)
    filled_part = user.split("Draft coverage  -  filled:")[-1].split("Empty:")[0]
    assert "ethics" in filled_part


def test_accepted_ethics_caution_does_not_block_the_ethics_move(client, monkeypatch):
    """
    Regression: after accepting an ethics caution, the pairing ethics append/set move
    (which restates the caution's concern, as the prompt asks) must still reach the
    researcher  -  not be dropped as a repeat.
    """
    caution_move = {
        "kind": "caution",
        "target": "ethics",
        "proposal": "Workspace snapshots may include personal or sensitive data.",
        "patch": None,
        "refs": [],
    }
    reply = {"text": "One caution.", "moves": [caution_move]}
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _fake_llm(reply))
    turn = _ask(client, "we'll capture workspace snapshots")
    _accept(client, turn["moves"][0]["moveId"])

    ethics_move = {
        "kind": "set-parameter",
        "target": "ethics",
        "proposal": (
            "Add an ethics posture: workspace snapshots may include personal "
            "data, so consent must cover snapshot content."
        ),
        "patch": {
            "section": "ethics",
            "op": "append",
            "value": "Consent covers snapshot content; personal data included",
        },
        "refs": [],
    }
    reply2 = {"text": "The posture.", "moves": [ethics_move]}
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _fake_llm(reply2))
    turn2 = _ask(client, "cover that in the ethics posture")
    assert turn2["source"] == "llm"
    assert [m["kind"] for m in turn2["moves"]] == ["set-parameter"]


def _read_move_order(client: TestClient) -> list[str]:
    conv = client.get(f"/studies/{STUDY}/conversation").json()
    return [m["moveId"] for t in conv["turns"] for m in t["moves"]]


def test_moves_keep_proposal_order_across_decisions(client, tmp_path):
    """The one surfaced card keeps its sequence across decisions."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    proposed = [m["moveId"] for m in reply["moves"]]
    assert len(proposed) == 1

    middle = proposed[len(proposed) // 2]
    _accept(client, middle, status="accepted")
    assert _read_move_order(client) == proposed
    _accept(client, middle, status="proposed")
    assert _read_move_order(client) == proposed

    factory = make_session_factory(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    with factory() as s:
        seqs = [s.get(DesignMoveRow, mid).seq for mid in proposed]
    assert seqs == list(range(1, len(proposed) + 1))


def test_conversation_read_orders_moves_by_seq_not_row_order(client, tmp_path):
    """
    Directly prove the ORDER BY: rows inserted out of seq order come back in seq order
    (SQLite returns insertion order for an unordered scan, so without the ORDER BY this
    read returns 103, 101, 102).
    """
    _ask(client, "I think junior developers over-trust AI-generated code")
    conv = client.get(f"/studies/{STUDY}/conversation").json()
    turn_id = next(t["turnId"] for t in conv["turns"] if t["role"] == "platform")

    factory = make_session_factory(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    with factory() as s:
        for seq in (103, 101, 102):
            s.add(
                DesignMoveRow(
                    id=f"{turn_id}:t1-m{seq}",
                    study_id=STUDY,
                    turn_id=turn_id,
                    seq=seq,
                    kind="add-rq",
                )
            )
        s.commit()

    tail = _read_move_order(client)[-3:]
    assert tail == [f"{turn_id}:t1-m{n}" for n in (101, 102, 103)]


def test_conversation_read_round_trips_move_targets(client):
    """
    The re-read every remote change triggers must return the same move the turn reply
    carried  -  `target` used to be dropped, blanking the finish review's target lines
    after any decision.
    """
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    sent = {m["moveId"]: m["target"] for m in reply["moves"]}
    assert any(sent.values()), "at least one scripted move must carry a target"
    conv = client.get(f"/studies/{STUDY}/conversation").json()
    got = {m["moveId"]: m["target"] for t in conv["turns"] for m in t["moves"]}
    assert got == sent


def test_compile_applies_moves_in_conversation_order(client, tmp_path):
    """The compiler must fold moves in conversation order."""
    factory = make_session_factory(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    with factory() as s:
        for turn_id, seq, value in (
            ("zzzz-turn", 1, "first-question"),
            ("aaaa-turn", 2, "second-question"),
        ):
            s.add(
                ConversationTurn(
                    id=turn_id,
                    study_id=STUDY,
                    seq=seq,
                    role="platform",
                    created_at="",
                )
            )
            s.add(
                DesignMoveRow(
                    id=f"{turn_id}:t{seq}-m1",
                    study_id=STUDY,
                    turn_id=turn_id,
                    seq=1,
                    kind="add-rq",
                    status="accepted",
                    patch={"section": "researchQuestions", "op": "set", "value": value},
                )
            )
        s.commit()

    result = _compile(client)
    assert "second-question" in result["yaml"]
    assert "first-question" not in result["yaml"]


def test_design_move_seq_migration_backfills_from_id(tmp_path):
    """
    A pre-seq database gets the column added and backfilled from the ``-m{i}`` id
    suffix, so existing moves keep their proposal order; the migration is idempotent.
    """
    from middleware.db import _migrate_design_move_seq
    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.sqlite3'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE design_moves ("
                "id VARCHAR PRIMARY KEY, study_id VARCHAR, turn_id VARCHAR, "
                "kind VARCHAR, target VARCHAR, proposal TEXT, patch JSON, "
                "grounding JSON, status VARCHAR, decided_by VARCHAR, "
                "decided_at VARCHAR)"
            )
        )
        for move_id in ("abc123:t2-m3", "abc123:t2-m12", "not-a-move-id"):
            conn.execute(
                text("INSERT INTO design_moves (id) VALUES (:id)"), {"id": move_id}
            )

    _migrate_design_move_seq(engine)
    _migrate_design_move_seq(engine)

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT id, seq FROM design_moves")).all())
    assert rows == {"abc123:t2-m3": 3, "abc123:t2-m12": 12, "not-a-move-id": 0}


def test_merge_templates_move_flows_end_to_end(client, tmp_path, monkeypatch):
    """
    Phase 5: a merge-templates move survives the whole wire  -  persisted with its
    patch,
    reloaded with mergeData reconstructed, compiled into a merged protocol on accept.
    """
    import model_double as md

    merge_ids = ("metr-rct-v1", "survey-self-report-v1")
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: md.always(
            {
                "text": "Combine behaviour telemetry with the survey shape.",
                "moves": [
                    md.merge(
                        merge_ids,
                        "Objective behaviour data plus self-report perception.",
                        refs=("corpus:metr-early-2025-dev-productivity",),
                    )
                ],
            }
        ),
    )

    reply = _ask(client, "design a study with telemetry and a self-report survey")
    merges = [m for m in reply["moves"] if m["kind"] == "merge-templates"]
    assert merges, "the merge proposal must reach the wire"
    assert merges[0]["mergeData"] == {
        "templateIds": list(merge_ids),
        "reason": "Objective behaviour data plus self-report perception.",
    }

    # Reload: mergeData is reconstructed from the stored patch, not just echoed inline.
    reloaded = client.get(f"/studies/{STUDY}/conversation").json()
    platform_turn = next(t for t in reloaded["turns"] if t["role"] == "platform")
    stored_merges = [
        m for m in platform_turn["moves"] if m["kind"] == "merge-templates"
    ]
    assert stored_merges
    assert stored_merges[0]["mergeData"]["templateIds"] == list(merge_ids)
    assert stored_merges[0]["patch"]["templateIds"] == list(merge_ids)

    # Accepting compiles the merged protocol into the draft.
    _accept(client, stored_merges[0]["moveId"])
    compiled = _compile(client)
    assert compiled["valid"], compiled["errors"]
    assert compiled["templateId"] is None
    assert compiled["protocol"]["study"]["title"].startswith("Merged design")
    refs = {lit["paperRef"] for lit in compiled["protocol"]["literature"]}
    assert "arxiv:2507.09089" in refs  # the METR paper the merge drew from
