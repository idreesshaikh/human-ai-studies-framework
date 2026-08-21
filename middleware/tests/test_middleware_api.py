"""API tests: idempotency, gap detection, one-timeline join, flagging."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"

FROZEN_NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        port=8000,
        # Hermetic: a platform build in the working copy must not add routes.
        spa_dist=tmp_path / "no-dist",
    )
    app = create_app(settings, clock=lambda: FROZEN_NOW)
    return TestClient(app)


def event(
    seq: int,
    session="S1",
    participant="P01",
    condition="ai-assisted",
    type_="fatigue_response",
    ts=None,
) -> dict:
    return {
        "v": 2,
        "ts": ts or f"2026-07-11T10:00:{seq:02d}.000Z",
        "mono": seq * 1000.0,
        "sessionId": session,
        "participantId": participant,
        "condition": condition,
        "seq": seq,
        "type": type_,
        "payload": {"answer": 3},
    }


def metric_row(
    file="detect.py",
    function=None,
    ts="2026-07-11T10:00:05+00:00",
    participant="P01",
    condition="ai-assisted",
    session="S1",
) -> dict:
    row = {
        "file": file,
        "indentation_variance": 9.6,
        "participantId": participant,
        "condition": condition,
        "sessionId": session,
        "timestamp": ts,
        "schemaVersion": 1,
    }
    if function:
        row["function"] = function
        row["parameter_count"] = 3
    return row


def test_health_reports_protocol(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["studyId"] == "pilot-2026"
    assert body["protocolLoaded"] is True


def test_ingest_is_idempotent_on_session_and_seq(client):
    batch = {"source": "tern", "events": [event(i) for i in range(5)]}
    first = client.post("/ingest/events", json=batch).json()
    assert first == {"received": 5, "inserted": 5, "duplicates": 0, "flagged": 0}

    replay = client.post("/ingest/events", json=batch).json()
    assert replay["inserted"] == 0
    assert replay["duplicates"] == 5

    events = client.get("/sessions/S1/events").json()
    assert len(events) == 5


def test_legacy_source_name_folds_into_one_stream(client):
    """An un-upgraded editor still reports "cognitive-overlay"."""
    client.post(
        "/ingest/events",
        json={"source": "cognitive-overlay", "events": [event(i) for i in range(3)]},
    )
    client.post(
        "/ingest/events",
        json={"source": "tern", "events": [event(i) for i in range(3, 6)]},
    )

    report = client.get("/sessions/S1/gaps").json()
    assert [s["source"] for s in report["sources"]] == ["tern"]
    assert report["complete"] is True

    replay = client.post(
        "/ingest/events",
        json={"source": "cognitive-overlay", "events": [event(0)]},
    ).json()
    assert replay["duplicates"] == 1


def test_bare_event_array_is_accepted(client):
    res = client.post("/ingest/events", json=[event(0)])
    assert res.status_code == 200
    assert res.json()["inserted"] == 1


def test_gap_report(client):
    seqs = [0, 1, 2, 5, 6, 9]
    client.post("/ingest/events", json=[event(i) for i in seqs])
    report = client.get("/sessions/S1/gaps").json()
    assert report["received"] == 6
    assert report["expected"] == 10
    assert report["complete"] is False
    assert report["gaps"] == [
        {"afterSeq": 2, "beforeSeq": 5, "missing": 2},
        {"afterSeq": 6, "beforeSeq": 9, "missing": 2},
    ]


def test_complete_session_has_no_gaps(client):
    client.post("/ingest/events", json=[event(i) for i in range(4)])
    report = client.get("/sessions/S1/gaps").json()
    assert report["gaps"] == []
    assert report["complete"] is True


def test_gaps_404_for_unknown_session(client):
    assert client.get("/sessions/nope/gaps").status_code == 404


def test_unknown_condition_is_stored_and_flagged_not_dropped(client):
    res = client.post("/ingest/events", json=[event(0, condition="with-ai")]).json()
    assert res["inserted"] == 1
    assert res["flagged"] == 1
    stored = client.get("/sessions/S1/events").json()[0]
    assert "unknown-condition" in stored["flags"]
    findings = client.get("/findings").json()
    assert any(f["requirementId"] == "FR-ING-6" for f in findings)


def test_unknown_participant_is_flagged(client):
    res = client.post("/ingest/events", json=[event(0, participant="P99")]).json()
    assert res["inserted"] == 1
    stored = client.get("/sessions/S1/events").json()[0]
    assert "unknown-participant" in stored["flags"]


def test_unknown_schema_version_is_flagged(client):
    bad = event(0)
    bad["v"] = 99
    client.post("/ingest/events", json=[bad])
    stored = client.get("/sessions/S1/events").json()[0]
    assert "unknown-schema-version" in stored["flags"]


def test_metrics_ingest_is_idempotent(client):
    rows = [metric_row(), metric_row(function="apply")]
    first = client.post("/ingest/metrics", json=rows).json()
    assert first["inserted"] == 2
    replay = client.post("/ingest/metrics", json=rows).json()
    assert replay["inserted"] == 0
    assert replay["duplicates"] == 2


def test_dataset_joins_legs_on_one_timeline(client):
    client.post(
        "/ingest/events",
        json=[
            event(0, ts="2026-07-11T10:00:00.000Z"),
            event(1, ts="2026-07-11T10:00:10.000Z"),
        ],
    )
    client.post("/ingest/metrics", json=[metric_row(ts="2026-07-11T10:00:05+00:00")])
    rows = client.get("/studies/pilot-2026/dataset").json()["rows"]
    assert [r["source"] for r in rows] == [
        "tern",
        "metrics",
        "tern",
    ]
    assert all(
        r["participantId"] == "P01" and r["condition"] == "ai-assisted" for r in rows
    )

    csv_text = client.get("/studies/pilot-2026/dataset?format=csv").text
    header, *lines = csv_text.strip().splitlines()
    assert header.startswith("source,ts,sessionId,participantId,condition")
    assert len(lines) == 3


def test_dataset_rejects_unknown_study(client):
    assert client.get("/studies/other-study/dataset").status_code == 404


def test_session_listing_merges_legs(client):
    client.post("/ingest/events", json=[event(0)])
    client.post("/ingest/metrics", json=[metric_row()])
    sessions = client.get("/studies/pilot-2026/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["events"] == 1
    assert sessions[0]["metricRows"] == 1


def test_event_type_filter(client):
    client.post("/ingest/events", json=[event(0), event(1, type_="stuck_response")])
    only = client.get("/sessions/S1/events?type=stuck_response").json()
    assert [e["seq"] for e in only] == [1]


def test_file_upload_is_content_addressed(client, tmp_path):
    upload = {"file": ("consent-form.pdf", b"pdf-bytes", "application/pdf")}
    first = client.post(
        "/ingest/files", data={"sessionId": "S1", "studyId": "pilot-2026"}, files=upload
    )
    assert first.status_code == 200
    assert first.json()["duplicate"] is False
    again = client.post(
        "/ingest/files", data={"studyId": "pilot-2026"}, files=upload
    ).json()
    assert again["duplicate"] is True
    assert again["sha256"] == first.json()["sha256"]


def upload(
    client, filename: str, content: bytes = b"x", study: str = "pilot-2026"
) -> dict:
    return client.post(
        "/ingest/files",
        data={"studyId": study},
        files={"file": (filename, content, "text/plain")},
    ).json()


def test_protocol_summary_merges_analysis_plan(client):
    doc = client.get("/studies/pilot-2026/protocol").json()
    assert doc["studyId"] == "pilot-2026"
    assert doc["protocolVersion"] == 4
    assert doc["conditions"] == ["ai-assisted", "unassisted"]
    assert doc["participants"]["planned"] == 6
    rqs = {rq["id"]: rq["recipes"] for rq in doc["researchQuestions"]}
    assert len(rqs) == 5
    assert rqs["RQ-P1"] == ["fatigue-by-condition", "stuck-episodes", "tlx-debrief"]
    assert [p["name"] for p in doc["phases"]][:2] == ["design", "ethics"]


def test_status_document_reports_sessions_gaps_and_rq_coverage(client):
    client.post("/ingest/events", json=[event(i) for i in [0, 1, 4]])
    client.post("/ingest/metrics", json=[metric_row()])
    doc = client.get("/studies/pilot-2026/status").json()

    assert doc["plannedParticipants"] == 6
    assert doc["plannedSessionsPerParticipant"] == 2
    (session,) = doc["sessions"]
    assert session["sessionId"] == "S1"
    assert session["events"] == 3
    assert session["metricRows"] == 1
    assert session["gapCount"] == 1
    assert session["missingEvents"] == 2
    assert session["complete"] is False

    rqs = {rq["id"]: rq for rq in doc["researchQuestions"]}
    assert rqs["RQ-P5"]["recipes"] == [
        "agent-interaction-dynamics",
        "task-outcome-by-condition",
    ]
    assert all(rq["recipeRuns"] == [] for rq in rqs.values())


def test_status_flags_surface_per_session(client):
    client.post("/ingest/events", json=[event(0, participant="P99")])
    (session,) = client.get("/studies/pilot-2026/status").json()["sessions"]
    assert session["flaggedEvents"] == 1
    assert session["flagKinds"] == ["unknown-participant"]


def test_recipe_runs_flow_into_status_rq_coverage(client):
    res = client.post(
        "/studies/pilot-2026/recipe-runs",
        json={"recipeId": "fatigue-by-condition", "answers": ["RQ-P1"]},
    )
    assert res.status_code == 200
    runs = client.get("/studies/pilot-2026/recipe-runs").json()
    assert runs[0]["recipeId"] == "fatigue-by-condition"
    assert runs[0]["status"] == "ok"

    doc = client.get("/studies/pilot-2026/status").json()
    rqs = {rq["id"]: rq for rq in doc["researchQuestions"]}
    assert rqs["RQ-P1"]["recipeRuns"] == ["fatigue-by-condition"]
    assert rqs["RQ-P2"]["recipeRuns"] == []


def test_live_reports_recent_sessions_with_rate_buckets(client):
    client.post("/ingest/events", json=[event(i) for i in range(3)])
    doc = client.get("/studies/pilot-2026/live").json()
    (live,) = doc["sessions"]
    assert live["sessionId"] == "S1"
    assert live["eventsInWindow"] == 3
    assert live["lastEventType"] == "fatigue_response"
    assert sum(live["rate"]) == 3
    assert len(live["rate"]) == 30
    assert live["gapCount"] == 0


def test_live_survives_a_session_whose_received_at_is_in_the_future(client, tmp_path):
    """
    Regression: a synthetic dry run schedules sessions across a realistic span rather
    than bunching them at one instant (simulation.py), so some events' received_at
    legitimately lands after "now" at query time.
    """
    from datetime import timedelta

    from middleware.db import Event, make_session_factory

    factory = make_session_factory(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    future = (FROZEN_NOW + timedelta(minutes=5)).isoformat(timespec="milliseconds")
    with factory() as s:
        s.add(
            Event(
                session_id="S-future",
                source="tern",
                seq=0,
                participant_id="P01",
                condition="ai-assisted",
                v=4,
                ts=future,
                mono=0.0,
                type="session_start",
                payload={},
                flags=[],
                received_at=future,
            )
        )
        s.commit()

    res = client.get("/studies/pilot-2026/live")
    assert res.status_code == 200, res.text
    (live,) = [x for x in res.json()["sessions"] if x["sessionId"] == "S-future"]
    assert live["rate"][-1] >= 1


def test_bearer_token_gates_views_but_not_ingest(tmp_path):
    settings = Settings(
        db_path=tmp_path / "t.sqlite3",
        data_dir=tmp_path,
        protocol_path=PILOT,
        spa_dist=tmp_path / "no-dist",
        token="s3cret",
    )
    client = TestClient(create_app(settings, clock=lambda: FROZEN_NOW))
    # Sensors keep working unauthenticated (NFR-1: never block a session).
    assert client.post("/ingest/events", json=[event(0)]).status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/studies/pilot-2026/sessions").status_code == 401
    ok = client.get(
        "/studies/pilot-2026/sessions", headers={"Authorization": "Bearer s3cret"}
    )
    assert ok.status_code == 200


def test_cors_is_off_by_default_and_opt_in_per_origin(tmp_path):
    """FR-OPS-6: same-origin only unless an origin is explicitly allowed."""
    base = {
        "db_path": tmp_path / "t.sqlite3",
        "data_dir": tmp_path,
        "protocol_path": PILOT,
        "spa_dist": tmp_path / "no-dist",
    }
    closed = TestClient(create_app(Settings(**base), clock=lambda: FROZEN_NOW))
    res = closed.get("/health", headers={"Origin": "https://preview.example"})
    assert "access-control-allow-origin" not in res.headers

    open_ = TestClient(
        create_app(
            Settings(**base, cors_origins=("https://preview.example",)),
            clock=lambda: FROZEN_NOW,
        )
    )
    res = open_.get("/health", headers={"Origin": "https://preview.example"})
    assert res.headers["access-control-allow-origin"] == "https://preview.example"
    res = open_.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in res.headers


def test_spa_is_served_when_built(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>mission control</html>")
    (dist / "assets" / "app.js").write_text("//js")
    settings = Settings(
        db_path=tmp_path / "t.sqlite3",
        data_dir=tmp_path,
        protocol_path=PILOT,
        spa_dist=dist,
    )
    client = TestClient(create_app(settings, clock=lambda: FROZEN_NOW))
    res = client.get("/")
    assert "mission control" in res.text
    assert res.headers["cache-control"] == "no-cache"
    deep = client.get("/p/my-lab/studies/pilot-2026")
    assert "mission control" in deep.text
    assert deep.headers["cache-control"] == "no-cache"
    assert "mission control" in client.get("/invitations/abc123").text
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/health").json()["status"] == "ok"

    # Every top-level client route App.tsx renders must be enumerated here too —
    # a route missing from this allowlist is invisible to the SPA fallback and a
    # direct navigation, refresh, or bookmark 404s on the *server*, even though
    # the client-side router would have handled it fine from a soft navigation.
    for route in ("/home", "/start", "/settings", "/repertoire", "/submissions"):
        res = client.get(route)
        assert res.status_code == 200, f"{route} should serve the SPA shell"
        assert "mission control" in res.text, route


def test_no_protocol_means_accept_all(tmp_path):
    settings = Settings(
        db_path=tmp_path / "t.sqlite3", data_dir=tmp_path, protocol_path=None
    )
    client = TestClient(create_app(settings, clock=lambda: FROZEN_NOW))
    res = client.post(
        "/ingest/events", json=[event(0, participant="X", condition="weird")]
    ).json()
    assert res["flagged"] == 0
    assert client.get("/studies/anything/dataset").status_code == 200


def test_stale_database_schema_fails_loudly_at_startup(tmp_path):
    """
    A database created by an older middleware (e.g. a compose volume from before
    events.source existed) must be rejected AT STARTUP with a remediation message - not
    pass /health and then 500 on the first ingest (NFR-1/NFR-2: sensor-facing failures
    are never quiet).
    """
    import sqlite3

    db = tmp_path / "stale.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, session_id TEXT)")
    con.commit()
    con.close()

    settings = Settings(db_path=db, data_dir=tmp_path, protocol_path=None)
    with pytest.raises(RuntimeError, match=r"source.*docker compose down -v|predates"):
        create_app(settings, clock=lambda: FROZEN_NOW)
