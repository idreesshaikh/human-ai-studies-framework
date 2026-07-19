"""The curated-mining leg wired into the middleware.

Offline end to end: a mining job runs against the committed cassette, lands
events in the one-timeline shape, and the validity-threats record gates
analysis. No tokens, no network.
"""

import datetime as dt
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

FROZEN_NOW = dt.datetime(2026, 7, 18, 12, 0, tzinfo=dt.UTC)
REPO = Path(__file__).resolve().parents[2]
DEMO_PROTOCOL = REPO / "protocol/examples/cursor-mining-2026.yaml"
CASSETTE = REPO / "curated/src/curated/cassettes/cursor-mining-demo.json"
STUDY = "cursor-mining-2026"


@pytest.fixture()
def client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "curated.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=DEMO_PROTOCOL,
        mining_cassette=CASSETTE,
        spa_dist=tmp_path / "no-dist",
    )
    return TestClient(create_app(settings, clock=lambda: FROZEN_NOW))


def _start(client) -> dict:
    res = client.post(f"/studies/{STUDY}/mining-jobs")
    assert res.status_code == 200, res.text
    return res.json()


def test_mining_job_runs_to_gate_and_lands_events(client):
    job = _start(client)
    assert job["state"] == "gated"
    assert job["coverage"]["retrieved"] >= 4
    # Events landed in the one-timeline shape via /ingest — the dataset export
    # sees them like any live rows.
    ds = client.get(f"/studies/{STUDY}/dataset").json()
    kinds = {r["type"] for r in ds["events"]} if "events" in ds else set()
    # The dataset export groups by session; just assert mined types are present
    # through the curated-dataset browser instead.
    browser = client.get(f"/studies/{STUDY}/curated-datasets/{job['id']}").json()
    counts = browser["eventCounts"]
    assert counts.get("mined_pull_request", 0) >= 4
    assert counts.get("mined_commit", 0) >= 1
    assert "mined_review" in counts
    _ = kinds


def test_events_are_content_free_no_raw_identities(client):
    job = _start(client)
    # Grep the stored payloads: no raw login/handle survives (F1.3).
    ds = client.get(f"/studies/{STUDY}/dataset").json()
    blob = repr(ds).lower()
    for raw in ("dana", "cursor[bot]", "devin-ai"):
        assert raw not in blob
    assert job["state"] == "gated"


def test_remining_is_idempotent_no_duplicates(client):
    first = _start(client)
    before = client.get(f"/studies/{STUDY}/curated-datasets/{first['id']}").json()[
        "eventCounts"
    ]
    # A second job over the same cassette must not double the rows.
    second = _start(client)
    after = client.get(f"/studies/{STUDY}/curated-datasets/{second['id']}").json()[
        "eventCounts"
    ]
    assert before == after  # same (session, source, seq) keys → replay dropped


def test_frame_refusal_without_curated_section(tmp_path):
    # A live protocol (no curated: section) refuses to mine, plain-language.
    settings = Settings(
        db_path=tmp_path / "c.sqlite3",
        data_dir=tmp_path / "d",
        protocol_path=REPO / "protocol/examples/pilot-study.yaml",
        mining_cassette=CASSETTE,
        spa_dist=tmp_path / "nd",
    )
    c = TestClient(create_app(settings, clock=lambda: FROZEN_NOW))
    res = c.post("/studies/pilot-2026/mining-jobs")
    assert res.status_code == 422
    assert "curated:" in res.json()["detail"]


def test_analysis_gate_blocked_until_threats_record(client):
    job = _start(client)
    # Before the record: the analysis gate artifact is absent.
    life = client.get(f"/studies/{STUDY}/lifecycle").json()
    analysis = next(p for p in life["phases"] if p["name"] == "analysis")
    threats_gate = next(
        g for g in analysis["gates"] if g["artifact"] == "validity-threats.yaml"
    )
    assert threats_gate["satisfied"] is False

    # A record missing biases is refused (never silently accepted).
    bad = client.put(
        f"/studies/{STUDY}/curated-datasets/{job['id']}/threats",
        json={
            "threatsRecord": {
                "samplingFrame": {"query": "x"},
                "biases": [],
                "coverage": {"requested": 1, "retrieved": 1, "dropped": {}},
            }
        },
    )
    assert bad.status_code == 422

    # The generated draft record is valid (starter biases) → finalizing opens
    # the gate.
    draft = client.get(f"/studies/{STUDY}/curated-datasets/{job['id']}").json()[
        "threatsRecord"
    ]
    ok = client.put(
        f"/studies/{STUDY}/curated-datasets/{job['id']}/threats",
        json={"threatsRecord": draft},
    )
    assert ok.status_code == 200 and ok.json()["finalized"]

    life2 = client.get(f"/studies/{STUDY}/lifecycle").json()
    analysis2 = next(p for p in life2["phases"] if p["name"] == "analysis")
    threats_gate2 = next(
        g for g in analysis2["gates"] if g["artifact"] == "validity-threats.yaml"
    )
    assert threats_gate2["satisfied"] is True


def test_threats_record_has_heuristics_and_coverage(client):
    job = _start(client)
    rec = client.get(f"/studies/{STUDY}/curated-datasets/{job['id']}").json()[
        "threatsRecord"
    ]
    assert rec["heuristics"]  # heuristics that fired are named + cited
    assert rec["heuristics"][0]["cite"]
    assert rec["coverage"]["retrieved"] >= 4
    assert rec["coverage"]["dropped"].get("excluded-by-inclusion-rule", 0) >= 1
    assert rec["biases"]  # starter biases present


def test_stop_then_resume_completes_without_duplicates(client):
    # Run to gate, then simulate a resume (idempotent: re-running from a
    # persisted cursor lands no duplicate rows). A full stop mid-fetch isn't
    # reachable synchronously against an instant cassette, so this exercises
    # the resume path's idempotency, which is the property F2.1 protects.
    job = _start(client)
    counts_before = client.get(f"/studies/{STUDY}/curated-datasets/{job['id']}").json()[
        "eventCounts"
    ]
    resumed = client.post(f"/studies/{STUDY}/mining-jobs/{job['id']}/resume")
    assert resumed.status_code == 200
    counts_after = client.get(f"/studies/{STUDY}/curated-datasets/{job['id']}").json()[
        "eventCounts"
    ]
    assert counts_before == counts_after


def test_schema_v5_events_are_known(client):
    # The curated vocabulary registers as schema v5; ingested mined rows are
    # not flagged as unknown-version.
    _start(client)
    health = client.get("/health").json()
    assert 5 in health["knownEventSchemaVersions"]
