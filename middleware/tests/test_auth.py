"""Sign-in provider seam (FR-OPS-5, D29).

The contract under test: zero-config stays open, a configured token keeps
its behavior, Clerk JWTs verify against a JWKS-style key, ingest is
never authenticated in any mode, and /auth/config leaks no secrets.
"""

import datetime as dt

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from middleware.auth import (
    ClerkVerifier,
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


# ------------------------------------------------------------ mode inference


def test_no_config_means_open(tmp_path):
    s = make_settings(tmp_path)
    assert resolve_mode(s) == "none"
    verifier_from_settings(s)("")  # any request passes


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


def test_clerk_mode_without_jwks_fails_loudly(tmp_path):
    s = make_settings(tmp_path, auth="clerk")
    with pytest.raises(ValueError, match="JWKS"):
        verifier_from_settings(s)


# ------------------------------------------------------------ token provider


def test_token_verifier_accepts_and_rejects(tmp_path):
    verify = verifier_from_settings(make_settings(tmp_path, token="sekrit"))
    verify("Bearer sekrit")
    for bad in ("", "Bearer wrong", "sekrit"):
        with pytest.raises(HTTPException) as e:
            verify(bad)
        assert e.value.status_code == 401


# ------------------------------------------------------------ clerk provider


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def clerk_verifier_with_key(key, issuer=None) -> ClerkVerifier:
    v = ClerkVerifier("https://example.test/jwks.json", issuer=issuer)
    v._signing_key = lambda token: key.public_key()  # JWKS fetch stubbed
    return v


def make_jwt(key, *, minutes=5, issuer="https://clerk.example.test", **claims):
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": "user_1",
        "iss": issuer,
        "iat": now,
        "exp": now + dt.timedelta(minutes=minutes),
        **claims,
    }
    return jwt.encode(payload, key, algorithm="RS256")


def test_clerk_accepts_valid_jwt(rsa_key):
    verify = clerk_verifier_with_key(rsa_key)
    verify(f"Bearer {make_jwt(rsa_key)}")


def test_clerk_rejects_expired_jwt(rsa_key):
    verify = clerk_verifier_with_key(rsa_key)
    with pytest.raises(HTTPException) as e:
        verify(f"Bearer {make_jwt(rsa_key, minutes=-5)}")
    assert e.value.status_code == 401


def test_clerk_rejects_wrong_signature(rsa_key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verify = clerk_verifier_with_key(rsa_key)
    with pytest.raises(HTTPException) as e:
        verify(f"Bearer {make_jwt(other)}")
    assert e.value.status_code == 401


def test_clerk_checks_issuer_when_configured(rsa_key):
    verify = clerk_verifier_with_key(rsa_key, issuer="https://good.test")
    verify(f"Bearer {make_jwt(rsa_key, issuer='https://good.test')}")
    with pytest.raises(HTTPException) as e:
        verify(f"Bearer {make_jwt(rsa_key, issuer='https://evil.test')}")
    assert e.value.status_code == 401


def test_clerk_missing_header_is_401(rsa_key):
    verify = clerk_verifier_with_key(rsa_key)
    with pytest.raises(HTTPException) as e:
        verify("")
    assert e.value.status_code == 401


def test_jwks_outage_fails_closed_with_503(rsa_key):
    verify = clerk_verifier_with_key(rsa_key)

    def boom(_token):
        raise OSError("connection refused")

    verify._signing_key = boom
    with pytest.raises(HTTPException) as e:
        verify(f"Bearer {make_jwt(rsa_key)}")
    assert e.value.status_code == 503


# --------------------------------------------------------- app-level wiring


def test_auth_config_shapes(tmp_path):
    assert public_config(make_settings(tmp_path)) == {"mode": "none"}
    assert public_config(make_settings(tmp_path, token="sekrit")) == {"mode": "token"}
    clerk = public_config(
        make_settings(
            tmp_path,
            auth="clerk",
            clerk_jwks_url="https://example.test/jwks.json",
            clerk_publishable_key="pk_test_abc",
        )
    )
    assert clerk == {"mode": "clerk", "clerkPublishableKey": "pk_test_abc"}
    # the secret token never appears in any config payload
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
    # ingest is never authenticated (sensors are fire-and-forget)
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
