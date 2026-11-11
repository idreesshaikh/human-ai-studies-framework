"""Per-user profile preferences (FR-OPS-7), keyed by the caller's identity."""

import middleware.auth as auth_mod
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.auth import Identity
from middleware.settings import Settings


def identity_client(tmp_path) -> TestClient:
    """A TestClient whose bearer value is the caller's identity, so several
    callers can be told apart without a hosted sign-in provider."""

    def verify(authorization: str) -> Identity:
        if not authorization.startswith("Bearer "):
            raise auth_mod.HTTPException(401, "missing bearer token")
        sub = authorization.removeprefix("Bearer ")
        return Identity(sub=sub, display_name=f"Researcher {sub}", mode="token")

    settings = Settings(
        db_path=tmp_path / "db.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        spa_dist=tmp_path / "no-dist",
    )
    original = auth_mod.verifier_from_settings
    auth_mod.verifier_from_settings = lambda s: verify
    try:
        app = create_app(settings)
    finally:
        auth_mod.verifier_from_settings = original
    return TestClient(app)


def auth(sub: str = "user_1") -> dict:
    return {"Authorization": f"Bearer {sub}"}


def test_me_carries_empty_preferences_before_save(tmp_path):
    client = identity_client(tmp_path)
    res = client.get("/me", headers=auth())
    assert res.status_code == 200
    body = res.json()
    assert body["sub"] == "user_1"
    assert body["displayName"] == "Researcher user_1"
    assert body["preferences"] == {}


def test_put_preferences_round_trip(tmp_path):
    client = identity_client(tmp_path)
    res = client.put(
        "/me/preferences",
        headers=auth(),
        json={
            "preferences": {
                "theme": "dark",
                "savedViews": {"library": "constellation"},
            }
        },
    )
    assert res.status_code == 200
    saved = res.json()["preferences"]
    assert saved["theme"] == "dark"
    assert saved["savedViews"] == {"library": "constellation"}

    me = client.get("/me", headers=auth()).json()
    assert me["preferences"]["theme"] == "dark"


def test_put_preferences_ignores_unknown_keys(tmp_path):
    client = identity_client(tmp_path)
    res = client.put(
        "/me/preferences",
        headers=auth(),
        json={"preferences": {"theme": "light", "hack": "nope"}},
    )
    assert res.status_code == 200
    assert res.json()["preferences"] == {"theme": "light"}


def test_preferences_merge_on_subsequent_puts(tmp_path):
    client = identity_client(tmp_path)
    client.put(
        "/me/preferences",
        headers=auth(),
        json={"preferences": {"theme": "dark"}},
    )
    res = client.put(
        "/me/preferences",
        headers=auth(),
        json={"preferences": {"savedViews": {"library": "list"}}},
    )
    saved = res.json()["preferences"]
    assert saved == {"theme": "dark", "savedViews": {"library": "list"}}


def test_profiles_are_scoped_per_identity(tmp_path):
    client = identity_client(tmp_path)
    client.put(
        "/me/preferences",
        headers=auth("user_a"),
        json={"preferences": {"theme": "dark"}},
    )
    client.put(
        "/me/preferences",
        headers=auth("user_b"),
        json={"preferences": {"theme": "light"}},
    )
    a = client.get("/me", headers=auth("user_a")).json()
    b = client.get("/me", headers=auth("user_b")).json()
    assert a["preferences"]["theme"] == "dark"
    assert b["preferences"]["theme"] == "light"


def test_identity_resolves_project_membership(tmp_path):
    """The identity is the join key: a project its creator made shows up in
    /me, and another identity that is not a member cannot see it."""
    client = identity_client(tmp_path)
    created = client.post("/projects", headers=auth(), json={"name": "Lab"})
    assert created.status_code in (200, 201)
    slug = created.json()["slug"]

    me = client.get("/me", headers=auth()).json()
    assert any(m["projectSlug"] == slug for m in me["memberships"])

    assert client.get(f"/projects/{slug}", headers=auth()).status_code == 200
    other = client.get(f"/projects/{slug}", headers=auth("stranger"))
    assert other.status_code in (403, 404)
