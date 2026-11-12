"""Fault/replay QA for durable ingestion and researcher exports."""

import csv
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"
FROZEN_NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def make_event(seq: int) -> dict:
    return {
        "v": 2,
        "ts": f"2026-11-11T11:00:{seq:02d}.000Z",
        "mono": float(seq * 1000),
        "sessionId": "qa-replay-session",
        "participantId": "P01",
        "condition": "ai-assisted",
        "taskId": "",
        "seq": seq,
        "type": "fatigue_response",
        "payload": {"answer": seq + 1},
    }


def test_concurrent_event_replays_converge_and_exports_have_one_copy(tmp_path):
    app = create_app(
        Settings(
            db_path=tmp_path / "replays.sqlite3",
            data_dir=tmp_path / "data",
            protocol_path=PILOT,
            port=8000,
            spa_dist=tmp_path / "no-dist",
        ),
        clock=lambda: FROZEN_NOW,
    )
    batch = [make_event(i) for i in range(3)]

    with TestClient(app) as client:

        def replay(_index: int) -> dict:
            response = client.post("/ingest/events", json=batch)
            assert response.status_code == 200, response.text
            return response.json()

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(replay, range(8)))

        assert sum(result["inserted"] for result in results) == 3
        assert sum(result["duplicates"] for result in results) == 21
        assert len(client.get("/sessions/qa-replay-session/events").json()) == 3

        metric = {
            "file": "task.py",
            "indentation_variance": 2.5,
            "metricId": "qa-stable-metric",
            "participantId": "P01",
            "condition": "ai-assisted",
            "sessionId": "qa-replay-session",
            "timestamp": "2026-11-11T11:00:03+00:00",
            "schemaVersion": 1,
        }

        def replay_metric(_index: int) -> dict:
            response = client.post("/ingest/metrics", json=[metric])
            assert response.status_code == 200, response.text
            return response.json()

        with ThreadPoolExecutor(max_workers=8) as pool:
            metric_results = list(pool.map(replay_metric, range(8)))

        assert sum(result["inserted"] for result in metric_results) == 1
        assert sum(result["duplicates"] for result in metric_results) == 7

        csv_response = client.get(
            "/studies/pilot-2026/dataset?format=csv&includeSynthetic=true"
        )
        assert csv_response.status_code == 200
        csv_rows = list(csv.DictReader(csv_response.text.splitlines()))
        assert len(csv_rows) == 4
        assert [row["source"] for row in csv_rows].count("metrics") == 1
        assert [row["seq"] for row in csv_rows if row["source"] == "tern"] == [
            "0",
            "1",
            "2",
        ]

        bundle = client.get("/studies/pilot-2026/data-bundle")
        assert bundle.status_code == 200
        with zipfile.ZipFile(BytesIO(bundle.content)) as archive:
            rows = json.loads(archive.read("events/all.json"))["rows"]
        assert len(rows) == 4
        assert [row["source"] for row in rows].count("metrics") == 1
        assert [row["seq"] for row in rows if row["source"] == "tern"] == [0, 1, 2]


def test_reordered_delivery_is_complete_and_malformed_event_batch_is_atomic(tmp_path):
    app = create_app(
        Settings(
            db_path=tmp_path / "reordered.sqlite3",
            data_dir=tmp_path / "data",
            protocol_path=PILOT,
            port=8000,
            spa_dist=tmp_path / "no-dist",
        ),
        clock=lambda: FROZEN_NOW,
    )
    with TestClient(app) as client:
        reordered = client.post(
            "/ingest/events", json=[make_event(i) for i in (2, 0, 1)]
        )
        assert reordered.status_code == 200, reordered.text
        assert reordered.json()["inserted"] == 3
        gap_report = client.get("/sessions/qa-replay-session/gaps").json()
        assert gap_report["complete"] is True
        assert gap_report["gaps"] == []

        malformed = make_event(3)
        malformed["seq"] = "not-a-sequence-number"
        rejected = client.post("/ingest/events", json=[make_event(4), malformed])
        assert rejected.status_code == 422
        events = client.get("/sessions/qa-replay-session/events").json()
        assert [row["seq"] for row in events] == [0, 1, 2]
