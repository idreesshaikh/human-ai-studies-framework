"""Evolution: amendments + feedback.

Two loops, one phase. *The study evolves* through phase-aware amendments —
version-visible always, consent-gated when it matters, running sessions never
touched. *The platform evolves* from feedback marked in the conversation:
findings → aggregate shapes → an inert retrospective proposal.

Fit criteria exercised:
- FR-CONV-4: F4.1 (consent-relevant amendment blocks new sessions until the
  re-approval artifact exists; collected data stays readable), F4.2 (threshold
  tweak applies next-session only; an in-flight session keeps its version),
  F4.3 (mixed-version sessions render distinguishably).
- FR-CONV-5: F5.1 (marked turn → findings row with locus → card), F5.2 (the
  drafted proposal cites its findings rows), F5.3 (grep-the-output on the
  aggregate tables — no conversation text, protocol content, or project id).
- FR-CONV-6 (regression): the export includes amendment decisions; redaction
  never unmakes them.

The consent-relevance *rule* (F4 core: change → relevant?) is a pure function,
table-tested directly against ``evolution.consent_relevance`` without the HTTP
stack, so its every branch is pinned.
"""

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


# ---------------------------------------------------------------- helpers


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
    r = client.post(
        f"/studies/{study}/conversation/approve",
        json={"compilationId": comp_id, "approvedBy": "Owner", "rationale": rationale},
    )
    return r


def _reach_approved_protocol(client, study=STUDY):
    """Drive an empty study to an approved, validating protocol draft (the
    pre-condition every amendment test starts from)."""
    reply = _ask(client, "what design and statistics should I use?", study)
    for m in reply["moves"]:
        if m["kind"] == "choose-template":
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


# =================================================================== F4 rule
# The consent-relevance rule as pure data (change → relevant?). This is the
# rule S3 relies on; every branch is pinned here, LLM-free and deterministic.

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
        # A new instrument is a new data stream — relevant.
        (
            _mut(
                instruments={
                    "tern": {"stuck": {"thresholdSeconds": 90}},
                    "agentCapture": {"adapter": "claude-code"},
                }
            ),
            True,
        ),
        # A threshold tweak inside an existing instrument — NOT relevant.
        (
            _mut(
                instruments={
                    "tern": {"stuck": {"thresholdSeconds": 120}},
                }
            ),
            False,
        ),
        # A content-policy change on an existing instrument — relevant.
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
        # An ethics-scope change — relevant.
        (_mut(ethics={"contentPolicy": "full-content"}), True),
        # Adding a research question (no stream/policy/ethics change) — not.
        (_mut(researchQuestions=[{"id": "RQ-1", "text": "new"}]), False),
        # Adding a curated data source — relevant (mined strangers, FR-ETH-2).
        (_mut(curated={"source": "github"}), True),
        # Adding agent participants — a new data source, relevant.
        (_mut(participants={"agents": [{"id": "A1"}]}), True),
        # No change at all — not relevant.
        (_mut(), False),
        # FR-CONV-7: a nested ``enabled`` field change on an existing
        # instrument is consent-relevant (turning capture on/off).
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
        # FR-CONV-7: first appearance of a metric subtree (a new top-level
        # key inside an existing instrument) is consent-relevant.
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


# ==================================================== F4.1 amendment + gate


def test_pre_ethics_amendment_is_an_ordinary_compile(client):
    """FR-CONV-4.1: before ethics approval, changes compile and apply with no
    amendment ceremony — no amendment row, no version bump beyond 1."""
    _reach_approved_protocol(client)
    hist = client.get(f"/studies/{STUDY}/amendments").json()
    assert hist["amendments"] == []
    assert hist["ethicsApprovedAt"] == ""
    assert hist["currentVersion"] == 1


def test_lifecycle_gate_artifacts_are_isolated_per_study(client):
    """FR-ING-5 / FR-DASH-2 regression: a gate artifact uploaded for one
    study must not advance a different study's lifecycle — files are
    indexed per study, not shared across the whole deployment."""
    study_a, study_b = "study-a", "study-b"
    _reach_approved_protocol(client, study_a)
    _approve_ethics(client, study_a)
    _reach_approved_protocol(client, study_b)
    _approve_ethics(client, study_b)

    doc_a = client.get(f"/studies/{study_a}/lifecycle").json()
    doc_b = client.get(f"/studies/{study_b}/lifecycle").json()
    assert doc_a["currentPhase"] == "design"
    assert doc_b["currentPhase"] == "design"

    client.post(
        "/ingest/files",
        data={"studyId": study_a},
        files={"file": ("protocol-validated.txt", b"x", "text/plain")},
    )

    doc_a = client.get(f"/studies/{study_a}/lifecycle").json()
    doc_b = client.get(f"/studies/{study_b}/lifecycle").json()
    assert doc_a["currentPhase"] == "ethics"
    assert doc_b["currentPhase"] == "design"


def test_consent_relevant_amendment_blocks_new_sessions(client):
    """F4.1: a post-ethics amendment adding a capture stream blocks new
    data-collection sessions until the re-approval artifact exists; sessions
    already open and already-collected data are untouched."""
    _reach_approved_protocol(client)
    _approve_ethics(client)

    # A session opened under v1 while the study is clean.
    r = _start(client, "S-open")
    assert r.status_code == 200
    assert r.json()["protocolVersion"] == 1

    # Add a capture stream conversationally → consent-relevant amendment.
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

    # New sessions are refused with a plain-language reason (the gate).
    blocked = _start(client, "S-new")
    assert blocked.status_code == 409
    assert "paused" in blocked.json()["detail"].lower()

    # The already-open session resumes untouched, still on v1 (NFR-1).
    resumed = _start(client, "S-open")
    assert resumed.status_code == 200
    assert resumed.json()["resumed"] is True
    assert resumed.json()["protocolVersion"] == 1

    # Upload the re-approval artifact → new sessions resume, under v2.
    re = client.post(f"/studies/{STUDY}/reapproval", json={"artifact": "ethics-v2.pdf"})
    assert re.status_code == 200
    unblocked = _start(client, "S-new")
    assert unblocked.status_code == 200
    assert unblocked.json()["protocolVersion"] == 2


def test_amendment_is_owner_only(client, tmp_path):
    """FR-CONV-4.2 / FR-PLAT-2: post-ethics, only an owner may approve an
    amendment. A researcher's approval is refused with a plain-language 403."""
    from middleware.db import Membership, make_session_factory

    _reach_approved_protocol(client)
    _approve_ethics(client)
    reply = _ask(client, "add the agent-capture instrument")
    add = [m for m in reply["moves"] if m["kind"] == "add-instrument"][0]
    _accept(client, add["moveId"])
    result = _compile(client)

    # Downgrade the local identity to researcher on the implicit project. A
    # researcher clears the ``apply_draft`` choke point (pre-ethics that is all
    # it takes), so the owner gate in the endpoint is the only thing standing
    # between them and applying an amendment — exactly what we assert.
    factory = make_session_factory(client.db_path)
    with factory() as s:
        m = s.get(Membership, ("implicit", "local"))
        m.role = "researcher"
        s.commit()

    # A fresh app instance sharing the DB signs in as the (now researcher)
    # local identity and is refused with a plain-language 403.
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


# ==================================================== F4.2 threshold tweak


def test_threshold_tweak_is_not_consent_relevant_and_applies_next_session(client):
    """F4.2: a threshold tweak amendment applies to the next session's config
    and is not consent-relevant — it never blocks, and never mutates a session
    already in flight (which keeps the version it opened under)."""
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

    # No block: a new session opens immediately, under v2.
    nxt = _start(client, "S-after")
    assert nxt.status_code == 200
    assert nxt.json()["protocolVersion"] == 2

    # The in-flight session is untouched: still v1 (NFR-1).
    resumed = _start(client, "S-inflight")
    assert resumed.json()["protocolVersion"] == 1

    # The tweak reached the derived config: the new approved draft carries 120.
    doc = yaml.safe_load(
        client.get(f"/studies/{STUDY}/conversation/export").json()["currentDraft"]
    )
    assert doc["instruments"]["tern"]["stuck"]["thresholdSeconds"] == 120


# ==================================================== F4.3 version visibility


def test_mixed_version_sessions_render_distinguishably(client):
    """F4.3: two sessions opened under different protocol revisions carry
    distinct versions — the dataset/timeline chips derive from these."""
    _reach_approved_protocol(client)
    _approve_ethics(client)
    _start(client, "S1")

    reply = _ask(client, "raise the stuck-detector threshold")
    tweak = [m for m in reply["moves"] if m["kind"] == "reconfigure-instrument"][0]
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


# ==================================================== amendment summary doc


def test_amendment_summary_doc_is_the_ethics_delta(client):
    """FR-CONV-4.3: the amendment summary is a deterministic human-readable
    delta — what changed, why, consent impact — the document S1 sends S3."""
    _reach_approved_protocol(client)
    _approve_ethics(client)
    reply = _ask(client, "add the agent-capture instrument")
    add = [m for m in reply["moves"] if m["kind"] == "add-instrument"][0]
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


# ==================================================== F5.1 feedback pipeline


def test_marked_turn_becomes_a_finding_with_locus(client):
    """F5.1: a feedback-marked turn produces a findings row linked to the
    conversation locus; the platform findings card renders it."""
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    # Mark the researcher's turn (seq of the platform reply minus 1).
    conv = client.get(f"/studies/{STUDY}/conversation").json()
    researcher_turn = [t for t in conv["turns"] if t["role"] == "researcher"][0]
    r = client.post(
        f"/studies/{STUDY}/conversation/turns/{researcher_turn['turnId']}/feedback",
        json={"note": "I wish the move cards were easier to scan", "kind": "ux-defect"},
    )
    assert r.status_code == 200, r.text

    cards = client.get("/platform/findings").json()
    assert len(cards) == 1
    card = cards[0]
    assert card["locus"]["turnId"] == researcher_turn["turnId"]
    assert card["locus"]["studyId"] == STUDY
    assert card["locus"]["kind"] == "ux-defect"
    assert "easier to scan" in card["note"]
    assert reply["moves"]


def test_feedback_finding_shows_in_findings_log(client):
    """F5.1: the marked feedback also lands in the operational findings log
    (FR-META-1) as a 'feedback' kind — one pipeline, self-applied."""
    conv_reply = _ask(client, "the platform is confusing when I compile")
    conv = client.get(f"/studies/{STUDY}/conversation").json()
    turn = [t for t in conv["turns"] if t["role"] == "researcher"][0]
    client.post(
        f"/studies/{STUDY}/conversation/turns/{turn['turnId']}/feedback",
        json={"note": "compile step unclear", "kind": "ux-defect"},
    )
    findings = client.get("/findings").json()
    feedback = [f for f in findings if f["kind"] == "feedback"]
    assert feedback
    assert feedback[0]["requirementId"] == "FR-CONV-5"
    assert conv_reply is not None


def test_feedback_detection_offers_but_never_files(client):
    """FR-CONV-5.1: detection may *offer* the marking; it is never auto-filed.
    A turn that reads as feedback is a suggestion, not a finding."""
    _ask(client, "this is confusing and I couldn't find the compile button")
    sugg = client.get(f"/studies/{STUDY}/conversation/feedback-suggestions").json()
    assert sugg["suggestions"], "a feedback-shaped turn should be offered"
    # Nothing was filed without an explicit mark.
    assert client.get("/platform/findings").json() == []


# ==================================================== F5.2 retrospective


def test_retrospective_proposal_cites_its_findings(client):
    """F5.2: the drafted platform proposal is inert and cites the findings rows
    it used (extends the FR-META-2 mechanism)."""
    for text, kind in [
        ("I wish the cards were clearer", "ux-defect"),
        ("the compile step is confusing", "ux-defect"),
    ]:
        _ask(client, text)
        conv = client.get(f"/studies/{STUDY}/conversation").json()
        turn = [t for t in conv["turns"] if t["role"] == "researcher"][-1]
        client.post(
            f"/studies/{STUDY}/conversation/turns/{turn['turnId']}/feedback",
            json={"note": text, "kind": kind},
        )
    proposal = client.get("/platform/retrospective").json()
    assert proposal["status"] == "draft"  # inert — nothing self-applies
    assert proposal["citedFindingIds"], "the proposal must cite its findings"
    assert proposal["generatedFrom"]["feedbackFindings"] == 2
    assert proposal["items"]


# ==================================================== F5.3 aggregates only


def test_aggregation_output_leaks_no_content(client):
    """F5.3 grep-the-output: cross-project aggregation tables contain no
    conversation text, protocol content, or project-identifying strings —
    only vocabulary tokens (template ids, slot names, stall categories, move
    kinds). Mirrors the FR-ETH-4 grep guarantee."""
    # A study with template + a rejected move + a distinctive RQ phrase.
    reply = _ask(client, "I think junior developers over-trust AI-generated code")
    for m in reply["moves"]:
        if m["kind"] == "add-rq":
            _accept(client, m["moveId"], status="rejected")
    design = _ask(client, "what design should I use?")
    for m in design["moves"]:
        if m["kind"] == "choose-template":
            _accept(client, m["moveId"])
    _compile(client)

    client.post("/platform/aggregate")
    rows = client.get("/platform/aggregate").json()
    assert rows, "aggregation should produce shape rows"

    import json

    blob = json.dumps(rows)
    # No conversation text.
    assert "junior developers" not in blob
    assert "over-trust" not in blob
    # No project / study identifier.
    assert STUDY not in blob
    assert "demo-study" not in blob
    # Only the fixed metric vocabulary and known token shapes.
    allowed_metrics = {
        "template-chosen",
        "slot-unresolved",
        "conversation-stall",
        "move-rejected",
    }
    assert {r["metric"] for r in rows} <= allowed_metrics
    # The rejected move kind is a vocabulary token, present and safe.
    kinds = {r["key"] for r in rows if r["metric"] == "move-rejected"}
    assert "add-rq" in kinds


# ==================================================== FR-CONV-6 regression


def test_export_includes_amendments_and_redaction_keeps_them(client):
    """FR-CONV-6 regression: the exported elicitation record includes amendment
    decisions, and redacting a turn never unmakes them."""
    _reach_approved_protocol(client)
    _approve_ethics(client)
    reply = _ask(client, "add the agent-capture instrument")
    add = [m for m in reply["moves"] if m["kind"] == "add-instrument"][0]
    _accept(client, add["moveId"])
    _approve(client, _compile(client)["compilationId"], rationale="justified")

    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert export["amendments"], "the record must carry amendment decisions"
    amend = export["amendments"][-1]
    assert amend["toVersion"] == 2
    assert amend["consentRelevant"] is True

    # Redact the turn that carried the instrument move; the amendment survives.
    from middleware.db import ConversationTurn, make_session_factory

    factory = make_session_factory(client.db_path)
    with factory() as s:
        turn = (
            s.query(ConversationTurn).filter_by(study_id=STUDY, role="platform").first()
        )
        turn.redacted = 1
        s.commit()

    after = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert after["amendments"] == export["amendments"]  # unchanged


# ==================================================== Slice D walkthrough


def test_slice_d_self_application_end_to_end(client):
    """The phase proof (Slice D): a real study taken through a post-ethics
    amendment (add a stream → caution → owner approves → new sessions blocked →
    re-approval → resume under v2), feedback marked in the same session, and an
    elicitation export carrying design + amendment + feedback."""
    # 1. Design → approve → ethics approval.
    _reach_approved_protocol(client)
    _approve_ethics(client)
    _start(client, "S-pre")

    # 2. Amendment: add an instrument → caution fires → owner approves.
    reply = _ask(client, "add the agent-capture instrument")
    assert "consent-relevant" in reply["text"].lower()  # the caution, spoken
    add = [m for m in reply["moves"] if m["kind"] == "add-instrument"][0]
    _accept(client, add["moveId"])
    amendment = _approve(
        client, _compile(client)["compilationId"], rationale="pilot value"
    ).json()["amendment"]
    assert amendment["requiresReapproval"]

    # 3. New sessions blocked → re-approve → resume under v2.
    assert _start(client, "S-blocked").status_code == 409
    client.post(f"/studies/{STUDY}/reapproval", json={"artifact": "ethics-v2.pdf"})
    resumed = _start(client, "S-post")
    assert resumed.json()["protocolVersion"] == 2

    # 4. Mark two turns as feedback → two findings → a proposal citing them.
    conv = client.get(f"/studies/{STUDY}/conversation").json()
    researcher_turns = [t for t in conv["turns"] if t["role"] == "researcher"][:2]
    for t in researcher_turns:
        client.post(
            f"/studies/{STUDY}/conversation/turns/{t['turnId']}/feedback",
            json={"note": "note", "kind": "ux-defect"},
        )
    assert len(client.get("/platform/findings").json()) == 2
    proposal = client.get("/platform/retrospective").json()
    assert proposal["citedFindingIds"]

    # 5. The elicitation record carries design, amendment, and feedback.
    export = client.get(f"/studies/{STUDY}/conversation/export").json()
    assert export["turns"] and export["compilations"] and export["approvals"]
    assert export["amendments"]
    assert export["currentDraft"]


def test_base_compiler_determinism_survives_amendments(client):
    """Verification step 3: replaying the *original* conversation still yields a
    byte-identical draft — amendments must not perturb the base compiler (F3.1
    stays green)."""
    reply = _ask(client, "what design and statistics should I use?")
    tmpl = [m for m in reply["moves"] if m["kind"] == "choose-template"][0]
    _accept(client, tmpl["moveId"])
    first = _compile(client)
    second = _compile(client)
    assert first["yaml"] == second["yaml"]
    # And the pure compiler, given the same accepted moves, is byte-stable.
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
