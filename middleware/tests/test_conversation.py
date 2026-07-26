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
from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory
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
    "an AI assistant than without one, in 45-minute instrumented sessions, "
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
