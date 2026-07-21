"""Per-user profile preferences (FR-OPS-7) over the Clerk auth seam.

Uses a generated RS256 key to mint a Clerk-style session JWT and stubs the
JWKS fetch, so the /me + /me/preferences round-trip is exercised exactly as
a hosted Clerk deployment would reach it. Membership resolution in clerk mode
is also checked: the JWT ``sub`` becomes the join key for project membership,
and two distinct Clerk identities keep separate profiles.
"""

import datetime as dt

import jwt
import middleware.auth as auth_mod
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.auth import ClerkVerifier
from middleware.settings import Settings


@pytest.fixture()
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def clerk_client(tmp_path, rsa_key):
    """A TestClient running in ``clerk`` auth mode with a stubbed JWKS."""
    settings = Settings(
        db_path=tmp_path / "db.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        spa_dist=tmp_path / "no-dist",
        requirements_dir=tmp_path / "no-reqs",
        auth="clerk",
        clerk_jwks_url="https://example.test/jwks.json",
        clerk_publishable_key="pk_test_abc",
    )
    verify = ClerkVerifier("https://example.test/jwks.json")
    verify._signing_key = lambda token: rsa_key.public_key()
    original = auth_mod.verifier_from_settings
    auth_mod.verifier_from_settings = lambda s: verify
    try:
        app = create_app(settings)
    finally:
        auth_mod.verifier_from_settings = original
    return TestClient(app)


def token(key, sub="user_clerk_1", **claims) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {
        "sub": sub,
        "iat": now,
        "exp": now + dt.timedelta(minutes=5),
        "name": "Clerk User",
        "email": "clerk@example.test",
        **claims,
    }
    return jwt.encode(payload, key, algorithm="RS256")


def auth(key, **claims) -> dict:
    return {"Authorization": f"Bearer {token(key, **claims)}"}


def test_me_carries_empty_preferences_before_save(tmp_path, rsa_key):
    client = clerk_client(tmp_path, rsa_key)
    res = client.get("/me", headers=auth(rsa_key))
    assert res.status_code == 200
    body = res.json()
    assert body["sub"] == "user_clerk_1"
    assert body["mode"] == "clerk"
    assert body["displayName"] == "Clerk User"
    assert body["preferences"] == {}


def test_put_preferences_round_trip(tmp_path, rsa_key):
    client = clerk_client(tmp_path, rsa_key)
    res = client.put(
        "/me/preferences",
        headers=auth(rsa_key),
        json={
            "preferences": {
                "theme": "dark",
                "defaultAssistantModel": "mistral-large-latest",
            }
        },
    )
    assert res.status_code == 200
    saved = res.json()["preferences"]
    assert saved["theme"] == "dark"
    assert saved["defaultAssistantModel"] == "mistral-large-latest"

    me = client.get("/me", headers=auth(rsa_key)).json()
    assert me["preferences"]["theme"] == "dark"


def test_put_preferences_ignores_unknown_keys(tmp_path, rsa_key):
    client = clerk_client(tmp_path, rsa_key)
    res = client.put(
        "/me/preferences",
        headers=auth(rsa_key),
        json={"preferences": {"theme": "light", "hack": "nope"}},
    )
    assert res.status_code == 200
    saved = res.json()["preferences"]
    assert saved == {"theme": "light"}


def test_preferences_merge_on_subsequent_puts(tmp_path, rsa_key):
    client = clerk_client(tmp_path, rsa_key)
    client.put(
        "/me/preferences",
        headers=auth(rsa_key),
        json={"preferences": {"theme": "dark"}},
    )
    res = client.put(
        "/me/preferences",
        headers=auth(rsa_key),
        json={"preferences": {"defaultAssistantModel": "mistral-medium-latest"}},
    )
    saved = res.json()["preferences"]
    assert saved == {"theme": "dark", "defaultAssistantModel": "mistral-medium-latest"}


def test_profiles_are_scoped_per_clerk_sub(tmp_path, rsa_key):
    client = clerk_client(tmp_path, rsa_key)
    client.put(
        "/me/preferences",
        headers=auth(rsa_key, sub="user_a"),
        json={"preferences": {"theme": "dark"}},
    )
    client.put(
        "/me/preferences",
        headers=auth(rsa_key, sub="user_b"),
        json={"preferences": {"theme": "light"}},
    )
    a = client.get("/me", headers=auth(rsa_key, sub="user_a")).json()
    b = client.get("/me", headers=auth(rsa_key, sub="user_b")).json()
    assert a["preferences"]["theme"] == "dark"
    assert b["preferences"]["theme"] == "light"


def test_clerk_sub_resolves_project_membership(tmp_path, rsa_key):
    """The JWT sub is the join key: a project created by the Clerk identity
    shows up in its /me memberships and is viewable under the same token."""
    client = clerk_client(tmp_path, rsa_key)
    created = client.post(
        "/projects", headers=auth(rsa_key), json={"name": "Clerk Lab"}
    )
    assert created.status_code in (200, 201)
    slug = created.json()["slug"]

    me = client.get("/me", headers=auth(rsa_key)).json()
    assert any(m["projectSlug"] == slug for m in me["memberships"])

    home = client.get(f"/projects/{slug}", headers=auth(rsa_key))
    assert home.status_code == 200
    # A different Clerk identity is not a member and must not see it.
    other = client.get(f"/projects/{slug}", headers=auth(rsa_key, sub="stranger"))
    assert other.status_code in (403, 404)


def test_assistant_models_catalog_is_public(tmp_path, rsa_key):
    client = clerk_client(tmp_path, rsa_key)
    res = client.get("/assistant/models")
    assert res.status_code == 200
    body = res.json()
    assert "mistral-small-latest" in body["models"]
    assert body["defaultModel"]
