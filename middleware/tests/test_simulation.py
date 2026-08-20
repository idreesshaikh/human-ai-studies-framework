"""
Synthetic dry-run simulation: generators, the route, and the CLI. The acceptance bar: a
seeded run is reproducible; every profile produces a plausible, complete session
schedule (per-session blocks, timestamps, join keys); a simulated study lands rows
through the real ingest path (idempotent helpers, server-stamped join keys); and the
analysis plan runs on the synthetic data, so a dry run proves the protocol produces data
its own recipes can consume.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from middleware.simulation import (
    PROFILES,
    profile_for,
    required_event_types,
    requires_metrics,
    simulate,
)

_STUDY = "pilot"

_STUDY_SKETCH = (
    "I want to see whether developers finish maintenance tasks faster with "
    "an AI assistant than without one, in 45-minute lab sessions, "
    "measuring task completion time and correctness."
)


def _ask(client, text, study=_STUDY):
    r = client.post(f"/studies/{study}/conversation/turns", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def _accept(client, move_id, study=_STUDY, status="accepted"):
    r = client.post(
        f"/studies/{study}/conversation/moves/{move_id}/decision",
        json={"status": status, "decidedBy": "Owner"},
    )
    assert r.status_code == 200, r.text


def _compile(client, study=_STUDY):
    r = client.post(f"/studies/{study}/conversation/compile", json={})
    assert r.status_code == 200, r.text
    return r.json()


def _approve(client, comp_id, study=_STUDY, rationale=""):
    return client.post(
        f"/studies/{study}/conversation/approve",
        json={"compilationId": comp_id, "approvedBy": "Owner", "rationale": rationale},
    )


def _frozen_client(tmp_path) -> TestClient:

    from middleware.app import create_app
    from middleware.settings import Settings

    frozen = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    return TestClient(create_app(settings, clock=lambda: frozen))


def _design_and_approve(client: TestClient) -> dict:
    """
    Drive the real design conversation to an approved protocol, then return the full
    protocol document.
    """
    import yaml

    _ask(client, _STUDY_SKETCH)
    reply = _ask(
        client,
        "what design and statistics should I use? I was thinking within-subjects, "
        "with each developer doing both conditions counterbalanced",
    )
    for m in reply["moves"]:
        _accept(client, m["moveId"])
    result = _compile(client)
    assert result["valid"], result["errors"]
    r = _approve(client, result["compilationId"])
    assert r.status_code == 200, r.text
    export = client.get("/studies/pilot/conversation/export")
    assert export.status_code == 200, export.text
    protocol = yaml.safe_load(export.json()["currentDraft"])
    assert protocol.get("analysisPlan"), "approved protocol should carry a plan"
    return protocol


def test_simulate_needs_a_protocol(client_no_protocol: TestClient):
    r = client_no_protocol.post("/studies/pilot/simulate", json={"count": 2})
    assert r.status_code == 409


def _normalize(row: dict) -> tuple:
    """
    A hashable projection with the per-run nonce stripped from every session id —
    top-level and the one nested inside metric payloads — so rows from two runs compare.
    """
    session = row["sessionId"].rsplit("-", 1)[0]
    payload = row["payload"]
    if isinstance(payload, dict):
        payload = dict(payload)
        if "sessionId" in payload:
            payload["sessionId"] = payload["sessionId"].rsplit("-", 1)[0]
        payload = json.dumps(payload, sort_keys=True)
    return (
        row["source"],
        row["ts"],
        session,
        row["participantId"],
        row["condition"],
        row["type"],
        row["seq"],
        json.dumps(row.get("flags") or [], sort_keys=True),
        payload,
    )


def test_seeded_run_is_reproducible(tmp_path):
    """
    Same seed, same frozen clock, same synthetic rows: only the per-run session nonce
    and the token credentials differ, never the data.
    """
    client = _frozen_client(tmp_path)
    _design_and_approve(client)

    def run_and_rows():
        r = client.post("/studies/pilot/simulate", json={"count": 6, "seed": 7})
        assert r.status_code == 200, r.text
        assert r.json()["participants"] == 6
        assert r.json()["sessions"] >= 6
        assert r.json()["events"] > 0
        assert r.json()["tokensMinted"] == 6
        doc = client.get("/studies/pilot/dataset?format=json")
        assert doc.status_code == 200, doc.text
        return Counter(_normalize(row) for row in doc.json()["rows"])

    first = run_and_rows()
    second = run_and_rows()
    assert second == first + first


def test_count_must_be_sane(client_designed: TestClient):
    r = client_designed.post("/studies/pilot/simulate", json={"count": 0})
    assert r.status_code == 400
    r = client_designed.post("/studies/pilot/simulate", json={"count": 101})
    assert r.status_code == 400


def test_unknown_profile_rejected(client_designed: TestClient):
    r = client_designed.post(
        "/studies/pilot/simulate", json={"count": 2, "profile": "wizard"}
    )
    assert r.status_code == 400


def test_simulated_data_drives_the_analysis_plan(client_designed: TestClient):
    """The whole point: after a dry run, the dataset's planned recipes run."""
    from analysis.dataset import Dataset
    from analysis.runner import run_plan

    protocol = _design_and_approve(client_designed)
    r = client_designed.post(
        "/studies/pilot/simulate", json={"count": 8, "profile": "mixed", "seed": 3}
    )
    assert r.status_code == 200, r.text
    doc = client_designed.get("/studies/pilot/dataset?format=json")
    assert doc.status_code == 200, doc.text
    dataset = Dataset(rows=doc.json()["rows"], study_id="pilot")
    plan = protocol.get("analysisPlan", [])
    assert plan, "the designed study should carry an analysis plan"
    out_root = Path(__import__("tempfile").mkdtemp())
    outcome = run_plan(protocol, dataset, "pilot", out_root=out_root)
    assert not outcome.failed_validation, [
        c.describe() for c in outcome.failed_validation
    ]
    assert outcome.executed, "at least one recipe should run on simulated data"


def test_all_profiles_generate_full_sessions():
    protocol = {
        "conditions": ["ai-assisted", "unassisted"],
        "tasks": [{"id": "fix", "title": "Fix"}] * 1,
        "analysisPlan": [
            {
                "id": "RQ-1",
                "recipes": ["task-outcome-by-condition"],
            }
        ],
        "participants": {"planned": 4, "design": "within-subjects"},
    }
    for profile in PROFILES:
        parts = simulate(protocol, count=2, profile=profile, seed=1)
        for p in parts:
            assert p["sessions"], profile
            for session in p["sessions"]:
                assert session["events"], profile
                kinds = {e["type"] for e in session["events"]}
                assert "task_outcome" in kinds
                assert "end_survey" not in kinds
                for e in session["events"]:
                    assert e["participant_id"] == p["participantId"]
                    assert e["condition"] == session["condition"]
                    assert e["session_id"] == session["sessionId"]
                    assert e["ts"]


def test_profile_for_cycles_mixed():
    labels = [profile_for(i, "mixed") for i in range(8)]
    assert set(labels) == set(PROFILES)
    assert labels[0] == "fast" and labels[4] == "fast"


def test_required_types_follows_the_plan():
    protocol = {
        "analysisPlan": [
            {"id": "RQ-1", "recipes": ["fatigue-by-condition"]},
            {"id": "RQ-2", "recipes": ["task-outcome-by-condition"]},
        ]
    }
    types = required_event_types(protocol)
    assert {"fatigue_response", "task_outcome"} <= types
    assert requires_metrics(protocol) is False

    protocol["analysisPlan"].append(
        {"id": "RQ-3", "recipes": ["code-quality-by-condition"]}
    )
    assert requires_metrics(protocol) is True


def test_events_are_time_ordered_within_a_session():
    protocol = {
        "conditions": ["a", "b"],
        "tasks": [{"id": "t1", "title": "T1"}],
        "analysisPlan": [
            {
                "id": "RQ-1",
                "recipes": ["fatigue-by-condition", "task-outcome-by-condition"],
            }
        ],
        "participants": {"planned": 2, "design": "within-subjects"},
    }
    parts = simulate(protocol, count=1, profile="struggling", seed=9)
    for session in parts[0]["sessions"]:
        stamps = [e["ts"] for e in session["events"]]
        assert stamps == sorted(stamps)


def test_struggling_profile_is_visibly_different_from_fast():
    protocol = {
        "conditions": ["a"],
        "tasks": [{"id": "t1", "title": "T1"}],
        "analysisPlan": [{"id": "RQ-1", "recipes": ["stuck-episodes"]}],
        "participants": {"planned": 2, "design": "between-subjects"},
    }
    fast = simulate(protocol, count=1, profile="fast", seed=1)
    struggling = simulate(protocol, count=1, profile="struggling", seed=1)
    fast_kinds = [e["type"] for s in fast[0]["sessions"] for e in s["events"]]
    slow_kinds = [e["type"] for s in struggling[0]["sessions"] for e in s["events"]]
    assert fast_kinds.count("stuck_response") == 0
    assert slow_kinds.count("stuck_response") >= 2


def test_cli_command_runs_over_http(client_designed: TestClient, tmp_path, monkeypatch):
    """
    The CLI is the E2E proof: HTTP protocol fetch, POST simulate, dataset fetch, then
    the analysis plan against the synthetic rows.
    """
    from middleware import __main__ as cli

    _design_and_approve(client_designed)

    calls: list[str] = []

    def _fake_request(req, timeout=60):
        server = "http://testserver"
        url = req if isinstance(req, str) else req.full_url
        calls.append(url)
        import json as _json

        class _Resp:
            def __init__(self, payload):
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return _json.dumps(self._payload).encode()

        if url == f"{server}/studies/pilot/conversation/export":
            return _Resp(
                client_designed.get("/studies/pilot/conversation/export").json()
            )
        if url == f"{server}/studies/pilot/simulate":
            return _Resp(
                client_designed.post(
                    "/studies/pilot/simulate", json=_json.loads(req.data)
                ).json()
            )
        if url == f"{server}/studies/pilot/dataset?format=json":
            return _Resp(
                client_designed.get("/studies/pilot/dataset?format=json").json()
            )
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(cli.urllib.request, "urlopen", _fake_request)
    monkeypatch.setattr(cli.urllib.request, "Request", lambda *a, **k: _FakeReq(a, k))

    class _FakeReq:
        def __init__(self, args, kwargs):
            self.full_url = args[0]
            self.data = kwargs.get("data")
            self.headers = kwargs.get("headers", {})
            self.method = kwargs.get("method")

    code = cli.cmd_simulate(
        "pilot", server="http://testserver", count=4, profile="mixed", seed=2
    )
    assert code == 0, calls
    assert len(calls) == 3
