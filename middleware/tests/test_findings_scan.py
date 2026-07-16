"""Operational-findings log + integrity scan (FR-META-1, MP-11 Part B).

A seq gap and a recipe requires-failure must each become a findings row (and,
via the status doc / findings feed, a task-board card). These rows are then
the retrospective's cited evidence (Part C, tested in analysis)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

REPO = Path(__file__).resolve().parents[2]
PILOT = REPO / "protocol" / "examples" / "pilot-study.yaml"
FROZEN = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "f.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        dashboard_dist=tmp_path / "no-dist",
    )
    return TestClient(create_app(settings, clock=lambda: FROZEN))


def event(seq: int, session="S1", condition="ai-assisted", participant="P01") -> dict:
    return {
        "v": 3, "ts": f"2026-07-11T10:00:{seq:02d}.000Z", "sessionId": session,
        "seq": seq, "participantId": participant, "condition": condition,
        "type": "fatigue_response", "payload": {"score": 3},
    }


def test_scan_writes_a_seq_gap_finding(client):
    # Ingest a session with a deliberate gap (seq 2 missing).
    client.post("/ingest/events", json=[event(i) for i in (0, 1, 3)])
    written = client.post("/studies/pilot-2026/findings/scan").json()
    assert written["written"] >= 1

    findings = client.get("/findings").json()
    gaps = [f for f in findings if f["kind"] == "seq-gap"]
    assert len(gaps) == 1
    assert gaps[0]["requirementId"] == "FR-ING-3"
    assert gaps[0]["context"]["session"] == "S1"
    assert gaps[0]["status"] == "open"


def test_scan_is_idempotent(client):
    client.post("/ingest/events", json=[event(i) for i in (0, 1, 3)])
    client.post("/studies/pilot-2026/findings/scan")
    second = client.post("/studies/pilot-2026/findings/scan").json()
    assert second["written"] == 0  # the same gap is not re-logged
    gaps = [f for f in client.get("/findings").json() if f["kind"] == "seq-gap"]
    assert len(gaps) == 1


def test_scan_writes_gate_block_findings(client):
    # A fresh study sits at the design phase with its gates unsatisfied.
    written = client.post("/studies/pilot-2026/findings/scan").json()
    blocks = [f for f in client.get("/findings").json() if f["kind"] == "gate-block"]
    assert blocks and written["written"] >= len(blocks)
    assert all(f["requirementId"] == "FR-PROT-3" for f in blocks)


def test_requires_fail_finding_round_trips(client):
    """What the analysis runner posts on a failed requires-check (FR-ANA-2):
    a requires-fail finding, which the retrospective later cites."""
    res = client.post(
        "/findings",
        json={
            "source": "analysis/run", "kind": "requires-fail",
            "requirementId": "FR-ANA-2",
            "message": "agent-interaction-dynamics (RQ-P5): MISSING DATA - "
            "requires event type 'agent_turn'",
            "context": {"recipe": "agent-interaction-dynamics", "rq": "RQ-P5"},
        },
    )
    assert res.json() == {"ok": True}
    findings = client.get("/findings").json()
    fails = [f for f in findings if f["kind"] == "requires-fail"]
    assert len(fails) == 1 and fails[0]["requirementId"] == "FR-ANA-2"


def test_gap_and_requires_fail_yield_two_findings(client):
    """Acceptance (MP-11): a fake seq gap + a failed requires-check yield two
    findings rows - and the status doc surfaces the gap so the dashboard
    cards it, while /findings surfaces the requires-fail."""
    client.post("/ingest/events", json=[event(i) for i in (0, 1, 3)])
    client.post("/studies/pilot-2026/findings/scan")
    client.post(
        "/findings",
        json={"source": "analysis/run", "kind": "requires-fail",
              "requirementId": "FR-ANA-2", "message": "recipe X: MISSING DATA",
              "context": {"recipe": "X", "rq": "RQ-P5"}},
    )
    kinds = {f["kind"] for f in client.get("/findings").json()}
    assert {"seq-gap", "requires-fail"} <= kinds

    # The gap is a card source: the status doc reports it per session.
    (session,) = [
        s for s in client.get("/studies/pilot-2026/status").json()["sessions"]
        if s["sessionId"] == "S1"
    ]
    assert session["gapCount"] >= 1
