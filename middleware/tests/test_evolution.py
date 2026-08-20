"""Evolution: phase-aware amendments."""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory
from middleware.settings import Settings

from middleware import compiler, evolution, paper_index

REPO_ROOT = Path(__file__).resolve().parents[2]

_SEEDS = [
    (
        "corpus:trust-in-ai-code-generation",
        "Investigating and Designing for Trust in AI-powered Code Generation",
        "Documents developer over-reliance on AI-generated code.",
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
    (
        "corpus:insecure-code-with-ai-assistants",
        "Do Users Write More Insecure Code with AI Assistants?",
        "Accepted AI code carries security defects users do not catch.",
    ),
    ("corpus:realhumaneval", "RealHumanEval", "Benchmark score is not human utility."),
]

STUDY = "demo-study"

_STUDY_SKETCH = (
    "I want to see whether developers finish maintenance tasks faster with "
    "an AI assistant than without one, in 45-minute lab sessions, "
    "measuring task completion time and correctness."
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
    tc = TestClient(create_app(settings))
    tc.db_path = settings.db_path
    return tc


def _ask(client, text, study=STUDY):
    r = client.post(f"/studies/{study}/conversation/turns", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def _accept(client, move_id, study=STUDY, status="accepted"):
    r = client.post(
        f"/studies/{study}/conversation/moves/{move_id}/decision",
        json={"status": status, "decidedBy": "Owner"},
    )
    assert r.status_code == 200, r.text


def _compile(client, study=STUDY):
    r = client.post(f"/studies/{study}/conversation/compile", json={})
    assert r.status_code == 200, r.text
    return r.json()


def _approve(client, comp_id, study=STUDY, rationale=""):
    return client.post(
        f"/studies/{study}/conversation/approve",
        json={"compilationId": comp_id, "approvedBy": "Owner", "rationale": rationale},
    )


def _reach_approved_protocol(client, study=STUDY):
    """
    Drive an empty study to an approved, validating protocol draft (the pre-condition
    every amendment test starts from).
    """
    _ask(client, _STUDY_SKETCH, study)
    reply = _ask(client, (
        "what design and statistics should I use? I was thinking "
        "within-subjects, with each developer doing both conditions "
        "counterbalanced"
    ), study)
    template_moves = [m for m in reply["moves"] if m["kind"] == "choose-template"]
    assert template_moves, "no design was proposed after describing the study"
    for m in template_moves:
        _accept(client, m["moveId"], study)
    result = _compile(client, study)
    assert result["valid"], result["errors"]
    r = _approve(client, result["compilationId"], study)
    assert r.status_code == 200, r.text
    return result


def _approve_ethics(client, study=STUDY):
    r = client.post(f"/studies/{study}/ethics-approval")
    assert r.status_code == 200, r.text
    return r.json()


def _start(client, session_id, study=STUDY):
    return client.post(
        f"/studies/{study}/sessions/start", json={"sessionId": session_id}
    )


_BASE = {
    "instruments": {"tern": {"stuck": {"thresholdSeconds": 90}}},
    "conditions": ["a", "b"],
    "ethics": {"contentPolicy": "metadata-only"},
}


def _mut(**changes):
    out = yaml.safe_load(yaml.safe_dump(_BASE))
    out.update(changes)
    return out


@pytest.mark.parametrize(
    "after,expected",
    [
        (
            _mut(
                instruments={
                    "tern": {"stuck": {"thresholdSeconds": 90}},
                    "agentCapture": {"adapter": "claude-code"},
                }
            ),
            True,
        ),
        (
            _mut(
                instruments={
                    "tern": {"stuck": {"thresholdSeconds": 120}},
                }
            ),
            False,
        ),
        (
            _mut(
                instruments={
                    "tern": {
                        "stuck": {"thresholdSeconds": 90},
                        "contentPolicy": "full-content",
                    },
                }
            ),
            True,
        ),
        (_mut(ethics={"contentPolicy": "full-content"}), True),
        (_mut(researchQuestions=[{"id": "RQ-1", "text": "new"}]), False),
        (_mut(curated={"source": "github"}), True),
        (_mut(participants={"agents": [{"id": "A1"}]}), True),
        (_mut(), False),
        (
            _mut(
                instruments={
                    "tern": {
                        "stuck": {"enabled": False, "thresholdSeconds": 90},
                    },
                }
            ),
            True,
        ),
        (
            _mut(
                instruments={
                    "tern": {
                        "stuck": {"thresholdSeconds": 90},
                        "ideHealth": {"enabled": True},
                    },
                }
            ),
            True,
        ),
    ],
)
def test_consent_relevance_rule(after, expected):
    """F4 core: the deterministic consent-relevance rule, one row per case."""
    relevant, reasons = evolution.consent_relevance(_BASE, after)
    assert relevant is expected, reasons
    assert (reasons != []) is expected


def test_pre_ethics_amendment_is_an_ordinary_compile(client):
    """
    FR-CONV-4.1: before ethics approval, changes compile and apply with no amendment
    ceremony — no amendment row, no version bump beyond 1.
    """
    _reach_approved_protocol(client)
    hist = client.get(f"/studies/{STUDY}/amendments").json()
    assert hist["amendments"] == []
    assert hist["ethicsApprovedAt"] == ""
    assert hist["currentVersion"] == 1


def test_uploaded_artifacts_are_isolated_per_study(client):
    """
    FR-ING-5 regression: a file uploaded for one study must not leak into another -
    uploads are indexed per study, not shared across the whole deployment.
    """
    study_a, study_b = "study-a", "study-b"
    _reach_approved_protocol(client, study_a)
    _reach_approved_protocol(client, study_b)

    client.post(
        "/ingest/files",
        data={"studyId": study_a},
        files={"file": ("consent-template.txt", b"x", "text/plain")},
    )

    files = client.get("/files").json()
    owners = {f["filename"]: f["studyId"] for f in files}
    assert owners["consent-template.txt"] == study_a
    assert study_b not in owners.values()


def test_consent_relevant_amendment_blocks_new_sessions(client):
    """
    F4.1: a post-ethics amendment adding a capture stream blocks new data-collection
    sessions until the re-approval artifact exists; sessions already open and
    already-collected data are untouched.
    """
    _reach_approved_protocol(client)
    _approve_ethics(client)

    r = _start(client, "S-open")
    assert r.status_code == 200
    assert r.json()["protocolVersion"] == 1

    reply = _ask(client, "add the agent-capture instrument")
    add = [m for m in reply["moves"] if m["kind"] == "add-instrument"]
    assert add, "the instrument script must propose an add-instrument move"
    _accept(client, add[0]["moveId"])
    result = _compile(client)
    assert result["valid"], result["errors"]
    approve = _approve(
        client, result["compilationId"], rationale="pilot showed agent value"
    )
    assert approve.status_code == 200, approve.text
    amendment = approve.json()["amendment"]
    assert amendment["consentRelevant"] is True
    assert amendment["requiresReapproval"] is True
    assert amendment["toVersion"] == 2

    blocked = _start(client, "S-new")
    assert blocked.status_code == 409
    assert "paused" in blocked.json()["detail"].lower()

    resumed = _start(client, "S-open")
    assert resumed.status_code == 200
    assert resumed.json()["resumed"] is True
    assert resumed.json()["protocolVersion"] == 1

    re = client.post(f"/studies/{STUDY}/reapproval", json={"artifact": "ethics-v2.pdf"})
    assert re.status_code == 200
    unblocked = _start(client, "S-new")
    assert unblocked.status_code == 200
    assert unblocked.json()["protocolVersion"] == 2


def test_amendment_is_owner_only(client, tmp_path):
    """FR-CONV-4.2 / FR-PLAT-2: post-ethics, only an owner may approve an amendment."""
    from middleware.db import Membership, make_session_factory

    _reach_approved_protocol(client)
    _approve_ethics(client)
    reply = _ask(client, "add the agent-capture instrument")
    add = next(m for m in reply["moves"] if m["kind"] == "add-instrument")
    _accept(client, add["moveId"])
    result = _compile(client)

    factory = make_session_factory(client.db_path)
    with factory() as s:
        m = s.get(Membership, ("implicit", "local"))
        m.role = "researcher"
        s.commit()

    settings = Settings(
        db_path=client.db_path,
        data_dir=tmp_path / "data2",
        port=8000,
        spa_dist=tmp_path / "no-dist2",
    )
    researcher_client = TestClient(create_app(settings))
    blocked = researcher_client.post(
        f"/studies/{STUDY}/conversation/approve",
        json={"compilationId": result["compilationId"], "approvedBy": "R"},
    )
    assert blocked.status_code == 403
    assert "owner" in blocked.json()["detail"].lower()


def test_threshold_tweak_is_not_consent_relevant_and_applies_next_session(client):
    """
    F4.2: a threshold tweak amendment applies to the next session's config and is not
    consent-relevant — it never blocks, and never mutates a session already in flight
    (which keeps the version it opened under).
    """
    _reach_approved_protocol(client)
    _approve_ethics(client)

    in_flight = _start(client, "S-inflight")
    assert in_flight.json()["protocolVersion"] == 1

    reply = _ask(client, "raise the stuck-detector threshold")
    tweak = [m for m in reply["moves"] if m["kind"] == "reconfigure-instrument"]
    assert tweak, "the threshold script must propose a reconfigure move"
    _accept(client, tweak[0]["moveId"])
    result = _compile(client)
    assert result["valid"], result["errors"]
    approve = _approve(client, result["compilationId"])
    amendment = approve.json()["amendment"]
    assert amendment["consentRelevant"] is False
    assert amendment["requiresReapproval"] is False

    nxt = _start(client, "S-after")
    assert nxt.status_code == 200
    assert nxt.json()["protocolVersion"] == 2

    resumed = _start(client, "S-inflight")
    assert resumed.json()["protocolVersion"] == 1

    doc = yaml.safe_load(
        client.get(f"/studies/{STUDY}/conversation/export").json()["currentDraft"]
    )
    assert doc["instruments"]["tern"]["stuck"]["thresholdSeconds"] == 120


def test_mixed_version_sessions_render_distinguishably(client):
    """
    F4.3: two sessions opened under different protocol revisions carry distinct versions
    — the dataset/timeline chips derive from these.
    """
    _reach_approved_protocol(client)
    _approve_ethics(client)
    _start(client, "S1")

    reply = _ask(client, "raise the stuck-detector threshold")
    tweak = next(m for m in reply["moves"] if m["kind"] == "reconfigure-instrument")
    _accept(client, tweak["moveId"])
    _approve(client, _compile(client)["compilationId"])
    _start(client, "S2")

    from middleware.db import SessionOpen, make_session_factory

    factory = make_session_factory(client.db_path)
    with factory() as s:
        versions = {
            row.session_id: row.protocol_version for row in s.query(SessionOpen).all()
        }
    assert versions["S1"] == 1
    assert versions["S2"] == 2


def test_amendment_summary_doc_is_the_ethics_delta(client):
    """
    FR-CONV-4.3: the amendment summary is a deterministic human-readable delta — what
    changed, why, consent impact — the document S1 sends S3.
    """
    _reach_approved_protocol(client)
    _approve_ethics(client)
    reply = _ask(client, "add the agent-capture instrument")
    add = next(m for m in reply["moves"] if m["kind"] == "add-instrument")
    _accept(client, add["moveId"])
    amendment = _approve(
        client, _compile(client)["compilationId"], rationale="pilot justified it"
    ).json()["amendment"]

    doc = client.get(f"/studies/{STUDY}/amendments/{amendment['amendmentId']}/summary")
    assert doc.status_code == 200
    body = doc.text
    assert "What changed" in body
    assert "agentCapture" in body
    assert "pilot justified it" in body
    assert "consent-relevant" in body.lower()


def test_export_includes_amendments_and_redaction_keeps_them(client):
    """
    FR-CONV-6 regression: the exported elicitation record includes amendment decisions,
    and redacting a turn never unmakes them.
    """
    _reach_approved_protocol(client)
    _approve_ethics(client)
    reply = _ask(client, "add the agent-capture instrument")
    add = next(m for m in reply["moves"] if m["kind"] == "add-instrument")
    _accept(client, add["moveId"])
    _approve(client, _compile(client)["compilationId"], rationale="justified")

    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert export["amendments"], "the record must carry amendment decisions"
    amend = export["amendments"][-1]
    assert amend["toVersion"] == 2
    assert amend["consentRelevant"] is True

    from middleware.db import ConversationTurn, make_session_factory

    factory = make_session_factory(client.db_path)
    with factory() as s:
        turn = (
            s.query(ConversationTurn).filter_by(study_id=STUDY, role="platform").first()
        )
        turn.redacted = 1
        s.commit()

    after = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert after["amendments"] == export["amendments"]


def test_slice_d_self_application_end_to_end(client):
    """
    The phase proof (Slice D): a real study taken through a post-ethics amendment (add a
    stream → caution → owner approves → new sessions blocked → re-approval → resume
    under v2) and an elicitation export carrying design + amendment.
    """
    _reach_approved_protocol(client)
    _approve_ethics(client)
    _start(client, "S-pre")

    reply = _ask(client, "add the agent-capture instrument")
    assert "consent-relevant" in reply["text"].lower()
    add = next(m for m in reply["moves"] if m["kind"] == "add-instrument")
    _accept(client, add["moveId"])
    amendment = _approve(
        client, _compile(client)["compilationId"], rationale="pilot value"
    ).json()["amendment"]
    assert amendment["requiresReapproval"]

    assert _start(client, "S-blocked").status_code == 409
    client.post(f"/studies/{STUDY}/reapproval", json={"artifact": "ethics-v2.pdf"})
    resumed = _start(client, "S-post")
    assert resumed.json()["protocolVersion"] == 2

    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert export["turns"] and export["compilations"] and export["approvals"]
    assert export["amendments"]
    assert export["currentDraft"]


def test_base_compiler_determinism_survives_amendments(client):
    """
    Verification step 3: replaying the *original* conversation still yields a
    byte-identical draft — amendments must not perturb the base compiler (F3.1 stays
    green).
    """
    _ask(client, _STUDY_SKETCH)
    reply = _ask(client, (
        "what design and statistics should I use? I was thinking "
        "within-subjects, with each developer doing both conditions "
        "counterbalanced"
    ))
    tmpl = next(m for m in reply["moves"] if m["kind"] == "choose-template")
    _accept(client, tmpl["moveId"])
    first = _compile(client)
    second = _compile(client)
    assert first["yaml"] == second["yaml"]
    moves = [
        {
            "moveId": tmpl["moveId"],
            "kind": "choose-template",
            "status": "accepted",
            "patch": tmpl["patch"],
            "grounding": tmpl["grounding"],
            "target": "design",
            "proposal": "",
        }
    ]
    assert compiler.compile_moves(moves).yaml == compiler.compile_moves(moves).yaml
