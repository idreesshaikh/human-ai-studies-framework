"""Design-conversation end-to-end tests."""

import io
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
_POST_JSON = assistant._post_json

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


def test_over_trust_moves_are_grounded_only_in_retrieved(client, monkeypatch):
    """F2.1: every card's grounding ref was retrieved this exchange."""
    every_id = [f"P{i}" for i in range(1, 12)]
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: model_double.always(
            model_double.draft(
                sources={"design": every_id, "researchQuestions": [every_id, []]}
            )
        ),
    )
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    assert reply["moves"]
    retrieved = {r["ref"] for r in reply["recommendations"]}
    grounded = {g["ref"] for m in reply["moves"] for g in m["grounding"]}
    assert grounded, "at least one card must be grounded"
    assert grounded <= retrieved
    assert "corpus:trust-in-ai-code-generation" in grounded


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


_STUDY_SKETCH = (
    "I want to see whether developers finish maintenance tasks faster with "
    "an AI assistant than without one, in 45-minute lab sessions, "
    "measuring task completion time and correctness."
)


def _drive_to_valid_draft(client) -> dict:
    """Describe the study, accept the proposed plan: a complete, validating
    protocol draft, all in-conversation (F1.1)."""
    reply = _ask(client, _STUDY_SKETCH)
    assert reply["moves"], "describing the study must produce a plan"
    for m in reply["moves"]:
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
    assert result["templateId"] == "within-subjects-crossover-v1"


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
    Templates-first (P1-2): a study created with a ``protocol`` body starts its
    draft from that protocol, but nothing is the study's protocol until it is
    reviewed and applied, exactly as for a designed study.
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
    assert export["currentDraft"] == ""
    assert export["approvals"] == []
    listed = client.get("/projects/implicit").json()["studies"]
    assert next(st for st in listed if st["id"] == "seeded")["hasProtocol"] is False

    compiled = client.post("/studies/seeded/conversation/compile", json={}).json()
    assert compiled["protocol"]["study"]["id"] == "seeded"
    assert compiled["protocol"]["study"]["title"] == "Seeded"
    assert compiled["protocol"]["researchQuestions"][0]["id"] == "RQ-1"


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
    # Research questions that are not objects would break every compile.
    r = client.post(
        "/projects/implicit/studies",
        json={"name": "Broken", "protocol": {"study": {}, "researchQuestions": ["q"]}},
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


def test_approval_rejects_a_compilation_stale_after_a_move_change(client):
    """Approval verifies the current move ledger rather than trusting an old draft."""
    result = _drive_to_valid_draft(client)
    conversation = client.get(f"/studies/{STUDY}/conversation").json()
    accepted = next(
        move
        for turn in conversation["turns"]
        for move in turn["moves"]
        if move["status"] == "accepted"
    )
    _accept(client, accepted["moveId"], status="rejected")

    r = client.post(
        f"/studies/{STUDY}/conversation/approve",
        json={"compilationId": result["compilationId"], "approvedBy": "Owner"},
    )

    assert r.status_code == 409
    assert "stale" in r.json()["detail"]
    assert "Recompile" in r.json()["detail"]


def test_rejecting_a_move_keeps_it_out_of_the_draft(client):
    """
    F1.2: cards are individually decidable; a rejected card leaves no trace in the
    compiled draft.
    """
    reply = _ask(client, _STUDY_SKETCH)
    questions = next(m for m in reply["moves"] if m["patch"]["part"] == "questions")
    for m in reply["moves"]:
        _accept(
            client, m["moveId"], status="rejected" if m is questions else "accepted"
        )
    result = _compile(client)
    assert not result["valid"]
    assert "the research questions" in result["unresolved"]
    for question in questions["patch"]["plan"]["researchQuestions"]:
        assert question not in result["yaml"]


def test_undoing_a_decision_reopens_the_move(client, tmp_path):
    """
    A decided card can be reopened back to 'proposed'  -  undo, not just accept/reject.
    """
    reply = _ask(client, _STUDY_SKETCH)
    card = next(m for m in reply["moves"] if m["patch"]["part"] == "questions")
    question = card["patch"]["plan"]["researchQuestions"][0]
    move_id = card["moveId"]

    def questions() -> list[str]:
        protocol = _compile(client)["protocol"]
        return [q["text"] for q in protocol.get("researchQuestions") or []]

    _accept(client, move_id, status="accepted")
    assert question in questions()

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
    assert question not in questions()

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
    F2.3: a card the literature can't settle still compiles, and the record marks it
    ungrounded rather than borrowing a citation to look sourced.
    """
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: model_double.always(model_double.draft()),
    )
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    assert reply["moves"] and all(m["grounding"] == [] for m in reply["moves"])
    for m in reply["moves"]:
        _accept(client, m["moveId"])
    assert _compile(client)["valid"]
    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert all(m["grounding"] == [] for t in export["turns"] for m in t["moves"])


def test_invalid_draft_cannot_be_approved(client):
    """
    F3.2/F3.3: a partly accepted plan fails validation and cannot be applied  -  a
    conversation never silently produces (or applies) an invalid draft.
    """
    reply = _ask(client, _STUDY_SKETCH)
    _accept(client, reply["moves"][0]["moveId"])
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


def test_llm_configured_and_healthy_produces_an_llm_sourced_turn(client, monkeypatch):
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: model_double.always(
            model_double.talk("Let's ground this in the corpus.", "Who takes part?")
        ),
    )
    turn = _ask(client, "junior developers over-trust AI code")
    assert turn["source"] == "llm"
    assert turn["text"] == "Let's ground this in the corpus."
    assert turn["questions"] == [{"ask": "Who takes part?", "options": []}]
    assert turn["moves"] == []


def test_card_decision_can_trigger_one_empty_move_followup(client, monkeypatch):
    """The card action is explicit context, answered without a model call."""
    captured: list = []
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: model_double.always(model_double.draft(), captured),
    )
    first = _ask(client, "I want to research how junior engineers use AI")
    move = first["moves"][0]
    _accept(client, move["moveId"])
    calls = len(captured)

    followup = client.post(
        f"/studies/{STUDY}/conversation/turns",
        json={
            "text": f"I accepted: {move['proposal']}",
            "decision": {"moveId": move["moveId"], "action": "accepted"},
        },
    )
    assert followup.status_code == 200, followup.text
    assert followup.json()["moves"] == []
    assert len(captured) == calls


def test_a_provider_outage_yields_a_holding_turn_never_a_fake_one(client, monkeypatch):
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


def test_a_rejected_key_is_named_and_not_retried(client, monkeypatch):
    """A 401 is a configuration fault: say so once instead of retrying a dead key."""
    double = model_double.rejected_key()
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: double)
    r = client.post(
        f"/studies/{STUDY}/conversation/turns",
        json={"text": "I think junior developers over-trust AI-generated code"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "unavailable"
    assert "rejected the server's API key" in body["text"]
    assert double.calls == 1


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


def test_a_holding_turn_is_never_replayed_to_the_model(client, monkeypatch):
    """
    Persisted for display is not the same as part of the design record. A holding
    turn must never reach the model as history on a later, real turn  -  a stored
    "the model did not respond" replayed back in would be a fabricated assistant turn.
    """
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: model_double.outage())
    _ask(client, "a thought about developers and Copilot")
    captured: list = []
    monkeypatch.setattr(
        assistant, "make_client", lambda *a, **k: model_double.silent(captured)
    )
    _ask(client, "a second thought about developers and Copilot")
    sent = json.dumps(captured[-1]["messages"])
    assert "did not respond" not in sent
    roles = [m["role"] for m in captured[-1]["messages"]]
    assert roles == ["system", "user"]


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
    assert "LLM_API_KEY" in body["text"]


def test_a_flaky_provider_is_retried_before_giving_up(client, monkeypatch):
    """
    Short provider outages should recover with bounded exponential backoff before the
    researcher is shown a holding turn.
    """
    calls = {"n": 0}
    delays: list[float] = []
    envelope = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"reply": "Second time lucky.", "changes": {}}
                    )
                }
            }
        ]
    }

    def flaky(request, timeout):
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("one blip")
        return io.BytesIO(json.dumps(envelope).encode())

    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: assistant.MistralProvider("test-key", post=_POST_JSON),
    )
    monkeypatch.setattr(assistant.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(assistant, "_sleep", delays.append)
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    turn = _ask(client, "does a blip lose my turn?")
    assert turn["source"] == "llm"
    assert turn["text"].startswith("Second time lucky.")
    # Two blips, then the recovered call.
    assert calls["n"] == 3
    assert delays == [0.5, 1.0]


def test_accepted_move_is_not_reproposed(client, monkeypatch):
    """
    Server-side guard: even a model that ignores its instructions and re-emits the
    accepted plan verbatim never repeats it to the researcher.
    """
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: model_double.always(model_double.draft()),
    )
    turn = _ask(client, _STUDY_SKETCH)
    for m in turn["moves"]:
        _accept(client, m["moveId"])
    again = _ask(client, "what should we measure?")
    assert again["source"] == "llm"
    assert again["moves"] == []


def _read_move_order(client: TestClient) -> list[str]:
    conv = client.get(f"/studies/{STUDY}/conversation").json()
    return [m["moveId"] for t in conv["turns"] for m in t["moves"]]


def test_moves_keep_proposal_order_across_decisions(client, tmp_path):
    """The one surfaced card keeps its sequence across decisions."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    proposed = [m["moveId"] for m in reply["moves"]]
    assert len(proposed) == 6

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


@pytest.mark.parametrize(
    "table,column,migrate",
    [
        ("studies", "seed_protocol", "_migrate_study_seed_protocol"),
        (
            "enrollment_tokens",
            "protocol_snapshot",
            "_migrate_enrollment_protocol_snapshot",
        ),
    ],
)
def test_new_columns_reach_an_existing_database_when_processes_start_together(
    tmp_path, table, column, migrate
):
    """Several server processes starting on one old database each try to add
    the column; exactly one does, the rest find it, and old rows read as unset."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy import create_engine

    from middleware import db as db_mod

    engine = create_engine(f"sqlite:///{tmp_path / 'old.sqlite3'}")
    with engine.begin() as conn:
        conn.exec_driver_sql(f"CREATE TABLE {table} (id TEXT PRIMARY KEY)")
        conn.exec_driver_sql(f"INSERT INTO {table} (id) VALUES ('old')")  # noqa: S608
    workers = 6
    ready = Barrier(workers, timeout=10)

    def upgrade():
        ready.wait()
        getattr(db_mod, migrate)(engine)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(upgrade) for _ in range(workers)]:
            future.result()

    with engine.connect() as conn:
        query = f"SELECT id, {column} FROM {table}"  # noqa: S608 - fixed test names
        row = conn.exec_driver_sql(query).one()
    assert tuple(row) == ("old", None)
