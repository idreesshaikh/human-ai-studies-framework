"""Agent-friendliness: the platform manifest.

Everything an agent needs to discover the platform is generated from
documents of record - no hand-written manifest content.

This file used to cover a generated ``AGENTS.md`` and a discovery demo as
well. Both read their content from ``requirements/`` and ``CLAUDE.md``,
documents that described a far wider platform than the one being built and
were removed rather than rewritten; a generator with no sources generates
nothing, so the feature went with them.
"""

import datetime as dt
import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

from middleware import manifest as manifest_mod

FROZEN_NOW = dt.datetime(2026, 7, 18, 12, 0, tzinfo=dt.UTC)
REPO = Path(__file__).resolve().parents[2]


def _client(tmp_path, **kw) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "m.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        spa_dist=tmp_path / "nd",
        **kw,
    )
    manifest_mod.refresh_manifest()  # clear the module cache between tests
    return TestClient(create_app(settings, clock=lambda: FROZEN_NOW))


# ---------------------------------------------------------------- manifest


def test_manifest_served_and_generated(tmp_path):
    m = _client(tmp_path).get("/.well-known/platform-manifest").json()
    assert m["platform"]["name"]
    assert m["capabilities"]
    # Schemas report the real, current versions (protocol now supports v3).
    assert 3 in m["schemas"]["protocol"]["versions"]
    assert 5 in m["schemas"]["event"]["versions"]
    assert m["templates"]["count"] >= 1
    assert m["corpus"]["count"] >= 1000


def test_manifest_reports_real_auth_mode(tmp_path):
    # The manifest reflects what the deployment actually enforces, not a guess.
    m = _client(tmp_path, token="sekrit").get("/.well-known/platform-manifest").json()
    assert m["api"]["auth"]["mode"] == "token"


def test_manifest_links_resolve(tmp_path):
    # Every link the manifest advertises must actually answer (an agent
    # following the manifest can't hit a 404).
    c = _client(tmp_path)
    m = c.get("/.well-known/platform-manifest").json()
    for url in (
        m["api"]["openapi"],
        m["schemas"]["protocol"]["url"],
        m["schemas"]["event"]["url"],
        m["templates"]["index"],
        m["corpus"]["index"],
    ):
        assert c.get(url).status_code == 200, url


def test_schema_endpoint_serves_the_real_schema(tmp_path):
    # Regression: the schema endpoints must serve the real files, not a
    # hardcoded fallback stub (the parent-count path bug).
    c = _client(tmp_path)
    schema = c.get("/schemas/protocol").json()
    assert schema["properties"]["protocolVersion"]["enum"] == [1, 2, 3, 4, 5]


def test_capabilities_are_feature_derived_not_hand_written(tmp_path):
    # FR-AGF-1 F1.1: the manifest's capabilities are *derived* from what the
    # deployment actually has, not a hand-maintained list. Pointing the
    # generator at an empty repo yields a strictly smaller capability set —
    # proving the values are computed from documents of record, not fixed.
    full = set(
        manifest_mod.generate_manifest(repo=REPO, deployment="hosted").capabilities
    )
    empty_repo = tmp_path  # no templates/, no corpus, no analysis/
    bare = set(
        manifest_mod.generate_manifest(
            repo=empty_repo, deployment="hosted"
        ).capabilities
    )
    assert bare < full  # feature detection removed the absent capabilities
    assert "templates" in full and "templates" not in bare
    assert "corpus" in full and "corpus" not in bare


# -------------------------------------------------------------- AGENTS.md


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_agents_md", REPO / "scripts" / "generate_agents_md.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


