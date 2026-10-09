"""The published schema endpoints."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from middleware.app import create_app
from middleware.settings import Settings

FROZEN_NOW = dt.datetime(2026, 7, 18, 12, 0, tzinfo=dt.UTC)


def _client(tmp_path, **kw) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "m.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        spa_dist=tmp_path / "nd",
        **kw,
    )
    return TestClient(create_app(settings, clock=lambda: FROZEN_NOW))


def test_schema_endpoint_serves_the_real_schema(tmp_path):
    c = _client(tmp_path)
    schema = c.get("/schemas/protocol").json()
    assert schema["properties"]["protocolVersion"]["enum"] == [1, 2, 3, 4, 5, 6]


def test_event_schema_includes_the_archive_version(tmp_path):
    c = _client(tmp_path)
    schema = c.get("/schemas/event").json()
    version = schema["properties"]["v"]
    assert version["minimum"] == 2
    assert version["maximum"] >= 5
    assert "archive vocabulary" in version["description"]


@pytest.mark.parametrize(
    "version,condition", [(5, "unassisted"), (6, "unassisted"), (6, "manual-control")]
)
def test_event_schema_accepts_current_capture_and_protocol_condition_names(
    tmp_path, version, condition
):
    schema = _client(tmp_path).get("/schemas/event").json()
    event = {
        "v": version,
        "ts": "2026-10-08T12:00:00Z",
        "mono": 0,
        "sessionId": "S1",
        "participantId": "P01",
        "condition": condition,
        "seq": 0,
        "type": "survey_response",
        "payload": {"responses": {"mental_demand": 25}},
    }
    assert list(Draft202012Validator(schema).iter_errors(event)) == []
