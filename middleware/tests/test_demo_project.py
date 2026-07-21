"""GET /demo (FR-PLAT-4): the shared public demo project pointer.

Only seed_on_start=True (the public-demo posture start_with_seed.sh sets)
creates/repoints the demo project — a self-hosted researcher's real study
must never be silently exposed as the public demo.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"
FROZEN_NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=UTC)


def _client(tmp_path, seed_on_start: bool) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        port=8000,
        spa_dist=tmp_path / "no-dist",
        seed_on_start=seed_on_start,
    )
    app = create_app(settings, clock=lambda: FROZEN_NOW)
    return TestClient(app)


def test_demo_project_seeded_when_seed_on_start(tmp_path):
    c = _client(tmp_path, seed_on_start=True)
    r = c.get("/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["projectSlug"] == "demo"
    assert body["projectName"] == "Demo"
    assert body["studyId"] == "pilot-2026"


def test_demo_project_not_seeded_without_the_flag(tmp_path):
    c = _client(tmp_path, seed_on_start=False)
    r = c.get("/demo")
    assert r.status_code == 404
    assert "demo project not seeded" in r.json()["detail"]


def test_demo_project_seeding_is_idempotent(tmp_path):
    # A second app instance against the same fresh sqlite file, both seeded
    # (start_with_seed.sh reseeds on every boot) — must not error or
    # duplicate the project row.
    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        port=8000,
        spa_dist=tmp_path / "no-dist",
        seed_on_start=True,
    )
    create_app(settings, clock=lambda: FROZEN_NOW)
    app2 = create_app(settings, clock=lambda: FROZEN_NOW)
    r = TestClient(app2).get("/demo")
    assert r.status_code == 200
    assert r.json()["projectSlug"] == "demo"


@pytest.mark.parametrize("seed_on_start", [True, False])
def test_settings_reads_the_env_var(monkeypatch, seed_on_start):
    monkeypatch.setenv("MIDDLEWARE_SEED_ON_START", "1" if seed_on_start else "0")
    assert Settings().seed_on_start is seed_on_start
