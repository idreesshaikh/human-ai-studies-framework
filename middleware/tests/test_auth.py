"""Sign-in provider seam (FR-OPS-5, D29)."""

import pytest
from fastapi import HTTPException
from middleware.auth import (
    public_config,
    resolve_mode,
    verifier_from_settings,
)
from middleware.settings import Settings


def make_settings(tmp_path, **kw) -> Settings:
    defaults = {
        "db_path": tmp_path / "db.sqlite3",
        "data_dir": tmp_path / "data",
        "protocol_path": None,
        "spa_dist": tmp_path / "nodist",
    }
    defaults.update(kw)
    return Settings(**defaults)


def test_no_config_means_open(tmp_path):
    s = make_settings(tmp_path)
    assert resolve_mode(s) == "none"
    verifier_from_settings(s)("")


def test_token_set_means_token_mode(tmp_path):
    s = make_settings(tmp_path, token="sekrit")
    assert resolve_mode(s) == "token"


def test_unknown_mode_fails_loudly(tmp_path):
    s = make_settings(tmp_path, auth="oauth2")
    with pytest.raises(ValueError, match="oauth2"):
        resolve_mode(s)


def test_token_mode_without_token_fails_loudly(tmp_path):
    s = make_settings(tmp_path, auth="token")
    with pytest.raises(ValueError, match="MIDDLEWARE_TOKEN"):
        verifier_from_settings(s)


def test_removed_clerk_mode_fails_with_a_clear_reason(tmp_path):
    """An old deployment .env may still say clerk; it must not start silently
    open or with a generic error."""
    s = make_settings(tmp_path, auth="clerk")
    with pytest.raises(ValueError, match="no longer supported"):
        verifier_from_settings(s)


def test_token_verifier_accepts_and_rejects(tmp_path):
    verify = verifier_from_settings(make_settings(tmp_path, token="sekrit"))
    verify("Bearer sekrit")
    for bad in ("", "Bearer wrong", "sekrit"):
        with pytest.raises(HTTPException) as e:
            verify(bad)
        assert e.value.status_code == 401


def test_auth_config_shapes(tmp_path):
    assert public_config(make_settings(tmp_path)) == {"mode": "none"}
    assert public_config(make_settings(tmp_path, token="sekrit")) == {"mode": "token"}
    # the secret token never appears in any config payload.
    assert "sekrit" not in str(public_config(make_settings(tmp_path, token="sekrit")))


def test_views_gated_but_ingest_open_in_token_mode(tmp_path):
    from fastapi.testclient import TestClient
    from middleware.app import create_app

    app = create_app(make_settings(tmp_path, token="sekrit"))
    client = TestClient(app)

    assert client.get("/auth/config").json() == {"mode": "token"}
    assert client.get("/files").status_code == 401
    assert (
        client.get("/files", headers={"Authorization": "Bearer sekrit"}).status_code
        == 200
    )
    # ingest is never authenticated (sensors are fire-and-forget).
    batch = {
        "source": "tern",
        "events": [
            {
                "sessionId": "S-auth-1",
                "seq": 1,
                "participantId": "P1",
                "condition": "ai-assisted",
                "v": 4,
                "type": "heartbeat",
                "ts": "2026-07-16T12:00:00.000Z",
                "payload": {},
            }
        ],
    }
    assert client.post("/ingest/events", json=batch).status_code == 200
