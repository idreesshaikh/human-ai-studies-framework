"""Design-conversation end-to-end tests.

Drives the whole thesis loop over the HTTP API — idea → conversation →
grounded moves → deterministic compile → approval → validating draft →
elicitation export — against a hermetic, minimally-seeded corpus so grounding
resolves without importing the full 14k-paper index.

Fit criteria exercised: F1.1 (empty → validating draft in-conversation),
F1.2 (individual move cards; reject removes effect), F1.3 (evasive → named
unresolved slots), F2.1 (grep-the-output: no move cites an unretrieved
source), F2.2 (self-report draws the METR caution), F2.3 (unsourced compiles
with grounding recorded), F3.1 (byte-identical replay), F3.2 (schema-break
bounces, not applied), F3.3 (no apply without a recorded approval),
F6.1 (the full chain exports both directions).
"""

import json
from pathlib import Path

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

#: The demo seeds the scripted assistant cites, seeded directly so grounding
#: resolves without a full corpus import (each with the "why" the README holds).
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


@pytest.fixture()
def client(tmp_path) -> TestClient:
    # No protocol loaded: the middleware is a permissive single-facilitator
    # sink, so any study id resolves through the implicit project (owner),
    # exactly the "empty project" F1.1 starts from.
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


# --------------------------------------------------------------- F2.1 / F2.2


def test_over_trust_moves_are_grounded_only_in_retrieved(client):
    """F2.1: every move's grounding ref was retrieved this exchange."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    assert reply["moves"], "the over-trust script must propose moves"
    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    # The turn records what its tools retrieved; no move may cite outside it.
    # (Server also asserts this on append — here we verify it in the record.)
    grounded = [
        g for turn in export["turns"] for m in turn["moves"] for g in m["grounding"]
    ]
    assert grounded, "at least one move must be grounded"
    refs = {g["ref"] for g in grounded if g["ref"] != "none"}
    assert "corpus:trust-in-ai-code-generation" in refs
    assert "corpus:insecure-code-with-ai-assistants" in refs


def test_recommendations_surface_the_two_demo_papers(client):
    """F9.1 at the conversation layer: both demo papers among the cards."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    rec_refs = {r["ref"] for r in reply["recommendations"]}
    assert "corpus:trust-in-ai-code-generation" in rec_refs
    assert "corpus:insecure-code-with-ai-assistants" in rec_refs


def test_recommendations_survive_a_conversation_reload(client):
    """A tab switch / remount re-reads the conversation via GET rather than
    trusting client state — the literature rail must not go blank on that
    re-read (it used to: recommendations were only ever returned inline on
    the turn reply, never persisted)."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    sent_refs = {r["ref"] for r in reply["recommendations"]}
    assert sent_refs

    reloaded = client.get(f"/studies/{STUDY}/conversation").json()
    platform_turn = next(t for t in reloaded["turns"] if t["role"] == "platform")
    reloaded_refs = {r["ref"] for r in platform_turn["recommendations"]}
    assert reloaded_refs == sent_refs


def test_self_report_draws_metr_caution(client):
    """F2.2: measuring productivity by self-report alone gets the METR caution."""
    reply = _ask(client, "I'll measure productivity by self-report survey")
    cautions = [m for m in reply["moves"] if m["kind"] == "caution"]
    assert cautions, "a self-report-only claim must draw a caution"
    refs = {g["ref"] for m in cautions for g in m["grounding"]}
    assert "corpus:metr-early-2025-dev-productivity" in refs


# ------------------------------------------------------------- F1.1 / F3.1 / F3.3


#: A study described the way a researcher would. The platform withholds a
#: design shape until it understands the study (FR-CONV-10), so a helper that
#: drives to a draft has to hold the conversation a researcher would hold.
_STUDY_SKETCH = (
    "I want to see whether developers finish maintenance tasks faster with "
    "an AI assistant than without one, in 45-minute lab sessions, "
    "measuring task completion time and correctness."
)


def _drive_to_valid_draft(client) -> dict:
    """Accept the template-choice move the design script proposes → a
    complete, validating protocol draft, all in-conversation (F1.1)."""
    _ask(client, _STUDY_SKETCH)
    reply = _ask(client, "what design and statistics should I use?")
    template_moves = [m for m in reply["moves"] if m["kind"] == "choose-template"]
    assert template_moves, "the design script must propose a template"
    for m in template_moves:
        _accept(client, m["moveId"])
    return _compile(client)


def test_empty_to_validating_draft_in_conversation(client):
    """F1.1: from an empty study, reach a draft that passes validation
    without leaving the conversation surface."""
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
    """A study with design moves and an approved compilation has rows that
    reference each other (design_moves.turn_id -> conversation_turns.id,
    approvals.compilation_id -> compilations.id) - deleting them in the
    wrong order is invisible on SQLite (no FK enforcement by default) but
    fails outright on Postgres, the production default, leaving the study
    stuck and the delete button looking like a no-op. Turn FK enforcement on
    for this test so a regression here fails loudly instead of only in
    production."""
    from sqlalchemy import event

    from middleware import db as db_mod

    def _enable_fk(dbapi_connection, connection_record, connection_proxy):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(db_mod._engine, "checkout", _enable_fk)
    try:
        # The other tests in this file write straight to study_id-scoped
        # tables without a reified ``Study`` row (the permissive implicit
        # project doesn't require one to hold a conversation) - but delete
        # looks the row up, so this one needs it to exist first.
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


def test_no_draft_applies_without_approval(client):
    """F3.3: the current draft is empty until an approval is recorded; the
    approval carries the approver's role (audit)."""
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
    assert after["approvals"][0]["role"] in ("owner", "researcher")


# --------------------------------------------------------------- F1.2 / F1.3


def test_rejecting_a_move_keeps_it_out_of_the_draft(client):
    """F1.2: moves are individually decidable; a rejected move leaves no
    trace in the compiled draft."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    rq_moves = [m for m in reply["moves"] if m["kind"] == "add-rq"]
    assert rq_moves
    _accept(client, rq_moves[0]["moveId"], status="rejected")
    result = _compile(client)
    assert rq_moves[0]["patch"]["value"] not in result["yaml"]


def test_undoing_a_decision_reopens_the_move(client, tmp_path):
    """A decided move can be reopened back to 'proposed' — undo, not just
    accept/reject. A reopened move drops back out of the compiled draft,
    same as one that was never decided."""
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
    assert r.json() == {"moveId": move_id, "status": "proposed"}

    reopened = _compile(client)
    assert rq_moves[0]["patch"]["value"] not in reopened["yaml"]

    factory = make_session_factory(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    with factory() as s:
        mv = s.get(DesignMoveRow, move_id)
        assert mv.decided_by == ""
        assert mv.decided_at == ""


def test_evasive_conversation_names_unresolved_slots(client):
    """F1.3: a vague opener that accepts no structural moves ends with named
    unresolved slots, not silent gaps."""
    _ask(client, "hmm, I'm not sure what I want to study yet")
    result = _compile(client)
    assert not result["valid"]
    assert result["unresolved"], "empty draft must name its unresolved slots"


# --------------------------------------------------------------- F2.3 / F3.2


def test_unsourced_move_compiles_with_grounding_recorded(client):
    """F2.3: the over-trust script's experience-level move is unsourced; it
    still compiles, and the elicitation record marks it grounding 'none'."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    unsourced = [m for m in reply["moves"] if not m["grounding"]]
    assert unsourced, "the experience-level scoping move should be unsourced"
    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    all_moves = [m for t in export["turns"] for m in t["moves"]]
    assert any(m["grounding"] == [] for m in all_moves)


def test_invalid_draft_cannot_be_approved(client):
    """F3.2/F3.3: a scaffold that fails validation returns errors/unresolved
    and cannot be applied — a conversation never silently produces (or
    applies) an invalid draft."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    for m in reply["moves"]:
        _accept(client, m["moveId"])
    result = _compile(client)  # free-text only, no template → incomplete
    assert not result["valid"]
    r = client.post(
        f"/studies/{STUDY}/conversation/approve",
        json={"compilationId": result["compilationId"], "approvedBy": "Owner"},
    )
    assert r.status_code == 409


# --------------------------------------------------------------- F6.1


def test_export_renders_the_full_chain(client):
    """F6.1: the elicitation export carries the chain — turns → moves →
    grounding → compilation → approval — navigable in both directions."""
    result = _drive_to_valid_draft(client)
    client.post(
        f"/studies/{STUDY}/conversation/approve",
        json={"compilationId": result["compilationId"], "approvedBy": "Owner"},
    )
    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert export["turns"] and export["compilations"] and export["approvals"]
    # Forward: a compilation references the move ids it folded.
    comp = export["compilations"][-1]
    assert comp["moveIds"]
    move_ids = {m["moveId"] for t in export["turns"] for m in t["moves"]}
    assert set(comp["moveIds"]) <= move_ids
    # Backward: the approval references that compilation.
    assert export["approvals"][-1]["compilationId"] == comp["compilationId"]


def test_reloading_the_conversation_recomputes_understanding(client):
    """A reload used to blank the understanding line until the next turn was
    sent — `understanding` was only ever set from a turn's own reply, never
    recomputed from the stored history. `GET .../conversation` must carry the
    same summary a fresh turn would, straight from what's already on record."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    conversation = client.get(f"/studies/{STUDY}/conversation").json()
    assert conversation["understanding"] == reply["understanding"]


# ---------------------------------------------------------- FR-CONV-1.4 (LLM)


def _fake_llm(reply_json: dict):
    """A provider whose ``post`` returns ``reply_json`` verbatim, wired in
    place of ``assistant.make_client`` — no network, no real key."""

    def post(url, body, headers):
        return {"choices": [{"message": {"content": json.dumps(reply_json)}}]}

    return assistant.MistralProvider("test-key", post=post)


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


def test_llm_failure_falls_back_to_the_unchanged_scripted_path(client, monkeypatch):
    """NFR-4/5: a configured-but-failing provider degrades exactly to
    today's scripted behavior — never a partial/hybrid turn."""

    def raising_client(*a, **k):
        class _Raises:
            model = "test"
            api_key = "k"
            base_url = "https://example.invalid/chat/completions"

            def post(self, *a, **k):
                raise TimeoutError("simulated provider outage")

        return _Raises()

    monkeypatch.setattr(assistant, "make_client", raising_client)
    turn = _ask(client, "I think junior developers over-trust AI-generated code")
    assert turn["source"] == "scripted"
    refs = {g["ref"] for m in turn["moves"] for g in m["grounding"]}
    assert "corpus:trust-in-ai-code-generation" in refs


def test_no_llm_key_configured_is_unaffected_by_the_new_seam(client):
    """The default test environment has no MISTRAL_API_KEY / LLM_BASE_URL —
    confirms the common case is untouched by this change."""
    turn = _ask(client, "I think junior developers over-trust AI-generated code")
    assert turn["source"] == "scripted"


# ------------------------------------------- repetition + coverage steering


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
    """A ``_fake_llm`` that also records every request body sent."""

    def post(url, body, headers):
        captured.append(body)
        return {"choices": [{"message": {"content": json.dumps(reply_json)}}]}

    return assistant.MistralProvider("test-key", post=post)


def test_accepted_move_is_not_reproposed(client, monkeypatch):
    """Server-side guard: even an LLM that ignores its instructions and
    re-emits an accepted move verbatim never repeats it to the researcher."""
    reply = {"text": "A grounded measure.", "moves": [_LATENCY_MOVE]}
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _fake_llm(reply))
    turn = _ask(client, "junior developers over-trust AI code")
    assert len(turn["moves"]) == 1
    _accept(client, turn["moves"][0]["moveId"])
    again = _ask(client, "what should we measure?")
    assert again["source"] == "llm"
    assert again["moves"] == []


def test_design_state_reaches_the_llm(client, monkeypatch):
    """The second turn's request carries the structured design state: the
    accepted and rejected moves by name, and the still-empty sections."""
    reply = {
        "text": "Two moves.",
        "moves": [_LATENCY_MOVE, _CONDITIONS_MOVE],
    }
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _fake_llm(reply))
    turn = _ask(client, "junior developers over-trust AI code")
    _accept(client, turn["moves"][0]["moveId"])
    _accept(client, turn["moves"][1]["moveId"], status="rejected")

    captured: list = []
    monkeypatch.setattr(
        assistant,
        "make_client",
        lambda *a, **k: _capturing_llm({"text": "Noted.", "moves": []}, captured),
    )
    _ask(client, "what next?")
    # The client also serves matching's query-expansion call — pick the
    # design-conversation request (the one carrying the candidate menu).
    user = next(
        body["messages"][-1]["content"]
        for body in captured
        if "Candidate menu this turn:" in body["messages"][-1]["content"]
    )
    assert "Design state so far:" in user
    assert "Accepted (already in the draft — do not re-propose):" in user
    assert "Measure review latency." in user
    assert "Rejected (the researcher said no — do not re-pitch):" in user
    assert "Run a three-arm condition split." in user
    assert "participants" in user.split("Empty:")[-1]


def test_scripted_repeat_swaps_to_coverage_followup(client):
    """No LLM key: repeating a prompt doesn't re-run the same script — the
    second reply proposes nothing and names the draft's actual gaps."""
    first = _ask(client, "I think junior developers over-trust AI-generated code")
    assert first["moves"], "the over-trust script must propose moves"
    second = _ask(client, "I think junior developers over-trust AI-generated code")
    assert second["source"] == "scripted"
    assert second["moves"] == []
    assert "still empty" in second["text"]
    assert "participants" in second["text"]


def _conversation_request(captured: list) -> str:
    """The design-conversation user message among captured LLM request
    bodies (the same client also serves matching's query-expansion call)."""
    return next(
        body["messages"][-1]["content"]
        for body in captured
        if "Candidate menu this turn:" in body["messages"][-1]["content"]
    )


def test_template_leaves_statistical_plan_and_ethics_open(client, monkeypatch):
    """An accepted template fills only the design slot (mirroring the
    researcher-visible meter) — statisticalPlan and ethics stay listed as
    empty, and the state invites recording the template's prescription
    instead of forbidding statisticalPlan moves. An accepted ethics
    append/set move then flips ethics to filled."""
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
    filled_part = user.split("Draft coverage — filled:")[-1].split("Empty:")[0]
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
    filled_part = user.split("Draft coverage — filled:")[-1].split("Empty:")[0]
    assert "ethics" in filled_part


def test_accepted_ethics_caution_does_not_block_the_ethics_move(client, monkeypatch):
    """Regression: after accepting an ethics caution, the pairing ethics
    append/set move (which restates the caution's concern, as the prompt
    asks) must still reach the researcher — not be dropped as a repeat."""
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


# ------------------------------------------------------- move-order stability


def _read_move_order(client: TestClient) -> list[str]:
    conv = client.get(f"/studies/{STUDY}/conversation").json()
    return [m["moveId"] for t in conv["turns"] for m in t["moves"]]


def test_moves_keep_proposal_order_across_decisions(client, tmp_path):
    """Accepting or undoing a card must not reorder the turn's cards. The
    conversation read used to return moves in physical row order (no ORDER
    BY) — stable on SQLite, but on Postgres the UPDATE a decision makes
    relocates the row, shuffling the cards under the researcher."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    proposed = [m["moveId"] for m in reply["moves"]]
    assert len(proposed) >= 2

    middle = proposed[len(proposed) // 2]
    _accept(client, middle, status="accepted")
    assert _read_move_order(client) == proposed
    _accept(client, middle, status="proposed")
    assert _read_move_order(client) == proposed

    # The persisted seq is the proposal order, 1..n within the turn.
    factory = make_session_factory(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    with factory() as s:
        seqs = [s.get(DesignMoveRow, mid).seq for mid in proposed]
    assert seqs == list(range(1, len(proposed) + 1))


def test_conversation_read_orders_moves_by_seq_not_row_order(client, tmp_path):
    """Directly prove the ORDER BY: rows inserted out of seq order come back
    in seq order (SQLite returns insertion order for an unordered scan, so
    without the ORDER BY this read returns 103, 101, 102)."""
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
    """The re-read every remote change triggers must return the same move
    the turn reply carried — `target` used to be dropped, blanking the
    finish review's target lines after any decision."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    sent = {m["moveId"]: m["target"] for m in reply["moves"]}
    assert any(sent.values()), "at least one scripted move must carry a target"
    conv = client.get(f"/studies/{STUDY}/conversation").json()
    got = {m["moveId"]: m["target"] for t in conv["turns"] for m in t["moves"]}
    assert got == sent


def test_compile_applies_moves_in_conversation_order(client, tmp_path):
    """The compiler must fold moves in conversation order. It used to order
    by id — a random hex turn prefix — so which of two conflicting accepted
    moves won depended on a coin flip at turn creation. The turn ids here
    reverse-sort lexicographically to pin the regression."""
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
    """A pre-seq database gets the column added and backfilled from the
    ``-m{i}`` id suffix, so existing moves keep their proposal order; the
    migration is idempotent."""
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
    _migrate_design_move_seq(engine)  # second run must be a no-op

    with engine.connect() as conn:
        rows = dict(conn.execute(text("SELECT id, seq FROM design_moves")).all())
    assert rows == {"abc123:t2-m3": 3, "abc123:t2-m12": 12, "not-a-move-id": 0}
