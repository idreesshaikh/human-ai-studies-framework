"""The published schema endpoints."""

import datetime as dt

from fastapi.testclient import TestClient
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
    assert schema["properties"]["protocolVersion"]["enum"] == [1, 2, 3, 4, 5]
