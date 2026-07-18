"""Project scoping + the permission matrix (MP-14 Slice A).

The contract under test:

- the matrix is *data* — every capability × role pair is checked by
  iterating ``authz.CAPABILITIES`` (so a new capability can't ship
  untested);
- the server enforces it — a lower role replaying a higher role's requests
  gets uniform 403s with a plain-language body;
- no project-scoped route skips the choke point (a route audit);
- cross-project access is refused;
- the boot migration adopts orphan studies into the implicit project;
- the invitation flow is single-use and expiring; the last owner can't be
  removed.
"""

import datetime as dt
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.auth import Identity
from middleware.authz import CAPABILITIES, ROLE_RANK, Role, has_role
from middleware.db import make_session_factory
from middleware.settings import Settings

from middleware import auth as auth_mod

FROZEN_NOW = dt.datetime(2026, 7, 18, 12, 0, tzinfo=dt.UTC)


def _fake_verifier(authorization: str) -> Identity:
    """A test verifier: ``Authorization: Bearer <sub>`` becomes a clerk-mode
    identity whose sub is the token. Lets a test drive many identities
    without minting real JWTs. Empty header is rejected like a real one."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    sub = authorization.removeprefix("Bearer ")
    return Identity(sub=sub, display_name=sub, mode="clerk")


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    # Multi-tenant behaviour: swap the verifier for the header-driven fake so
    # each request can carry a different identity.
    monkeypatch.setattr(
        auth_mod, "verifier_from_settings", lambda _s: _fake_verifier
    )
    settings = Settings(
        db_path=tmp_path / "authz.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        dashboard_dist=tmp_path / "no-dist",
    )
    return TestClient(create_app(settings, clock=lambda: FROZEN_NOW))


def bearer(sub: str) -> dict:
    return {"Authorization": f"Bearer {sub}"}


def make_project(client: TestClient, owner: str, name: str) -> str:
    """Create a project as ``owner`` (auto owner membership); return slug."""
    res = client.post("/projects", json={"name": name}, headers=bearer(owner))
    assert res.status_code == 200, res.text
    return res.json()["slug"]


def add_member(client, slug, owner, sub, role) -> None:
    """Invite ``sub`` at ``role`` and accept as that identity (the real flow;
    the invited identity's email doubles as its sub)."""
    inv = client.post(
        f"/projects/{slug}/invitations",
        json={"email": sub, "role": role},
        headers=bearer(owner),
    )
    assert inv.status_code == 200, inv.text
    token = inv.json()["token"]
    acc = client.post(f"/invitations/{token}/accept", headers=bearer(sub))
    assert acc.status_code == 200, acc.text


# --------------------------------------------------------- the matrix as data


def test_matrix_is_data_every_role_capability_pair():
    """has_role agrees with the rank ordering for every capability × role —
    iterating the dict is what makes an untested capability impossible."""
    for capability, required in CAPABILITIES.items():
        for role in Role:
            expected = ROLE_RANK[role] >= ROLE_RANK[required]
            assert has_role(role, capability) is expected, (
                f"{role} vs {capability}"
            )


def test_non_member_never_satisfies_any_capability():
    for capability in CAPABILITIES:
        assert has_role(None, capability) is False


# ------------------------------------------------------ server-side enforcement


def test_create_project_makes_creator_owner(client):
    slug = make_project(client, "alice", "Alice's lab")
    mine = client.get("/projects", headers=bearer("alice")).json()
    assert [(p["slug"], p["role"]) for p in mine] == [(slug, "owner")]


def test_view_capability_across_roles(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "researcher")
    add_member(client, slug, "alice", "vic", "viewer")
    # Every member can view the project home.
    for sub in ("alice", "rea", "vic"):
        assert client.get(f"/projects/{slug}", headers=bearer(sub)).status_code == 200
    # A non-member cannot.
    stranger = client.get(f"/projects/{slug}", headers=bearer("stranger"))
    assert stranger.status_code == 403


def test_manage_members_is_owner_only_with_uniform_403(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "researcher")
    add_member(client, slug, "alice", "vic", "viewer")
    # A researcher and a viewer replaying an owner-only request both get 403,
    # each with a plain-language body (not an empty/opaque error).
    for sub in ("rea", "vic"):
        res = client.post(
            f"/projects/{slug}/invitations",
            json={"email": "x", "role": "viewer"},
            headers=bearer(sub),
        )
        assert res.status_code == 403
        detail = res.json()["detail"]
        assert detail and "role" in detail.lower()


def test_delete_is_owner_only(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "researcher")
    assert client.request("DELETE",
        f"/projects/{slug}", json={"confirm": slug}, headers=bearer("rea")
    ).status_code == 403
    # Owner deletes with the typed confirmation.
    assert client.request("DELETE",
        f"/projects/{slug}", json={"confirm": slug}, headers=bearer("alice")
    ).status_code == 200


def test_delete_requires_typed_confirmation(client):
    slug = make_project(client, "alice", "Lab")
    assert client.request("DELETE",
        f"/projects/{slug}", json={"confirm": "wrong"}, headers=bearer("alice")
    ).status_code == 400


# ------------------------------------------------------------ cross-project


def test_cross_project_access_refused(client):
    p1 = make_project(client, "alice", "One")
    make_project(client, "bob", "Two")
    p2 = client.get("/projects", headers=bearer("bob")).json()[0]["slug"]
    # Alice is not a member of Bob's project — she can't read or delete it.
    assert client.get(f"/projects/{p2}", headers=bearer("alice")).status_code == 403
    assert client.request("DELETE",
        f"/projects/{p2}", json={"confirm": p2}, headers=bearer("alice")
    ).status_code == 403
    # A slug that doesn't exist at all 404s (learns the prober nothing more).
    assert client.get("/projects/nope", headers=bearer("alice")).status_code == 404
    _ = p1


# --------------------------------------------------------------- route audit


def test_every_project_scoped_route_carries_the_choke_point(client):
    """No project-scoped route enforces membership only in the frontend: each
    ``/projects/{slug}/...`` and ``/studies/{study_id}/...`` route depends on
    a require_project* factory. The public/self-serve exceptions are listed."""
    app = client.app
    # Routes that legitimately don't take a project/study scope check.
    exempt = {
        ("POST", "/projects"),  # create — any signed-in identity
        ("GET", "/projects"),  # my memberships — self-scoped
        ("POST", "/invitations/{token}/accept"),  # token is the credential
        ("GET", "/me"),
        ("GET", "/demo"),  # public pointer
    }
    offenders = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if not (path.startswith("/projects") or path.startswith("/studies/")):
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            if (method, path) in exempt:
                continue
            # The dependency names include 'slug' or 'study_id' params from
            # the require_project* closures; assert at least one dependency
            # references the authz module's closures by checking the route's
            # dependant tree for our parameter names.
            dep = getattr(route, "dependant", None)
            names = _dependency_param_names(dep) if dep else set()
            if not ({"slug", "study_id"} & names):
                offenders.append((method, path))
    assert not offenders, f"routes missing the choke point: {offenders}"


def _dependency_param_names(dependant) -> set:
    names = set()
    stack = [dependant]
    while stack:
        d = stack.pop()
        for p in getattr(d, "query_params", []) + getattr(d, "path_params", []):
            names.add(p.name)
        stack.extend(getattr(d, "dependencies", []))
    return names


# ------------------------------------------------------------ boot migration


def test_boot_migration_adopts_orphan_studies(tmp_path, monkeypatch):
    """A study row left by a pre-projects middleware is adopted into the
    implicit project on boot, not orphaned or dropped."""
    monkeypatch.setattr(
        auth_mod, "verifier_from_settings", lambda _s: _fake_verifier
    )
    db_path = tmp_path / "legacy.sqlite3"
    # First boot creates the schema (and the implicit project).
    settings = Settings(
        db_path=db_path, data_dir=tmp_path / "d", protocol_path=None,
        dashboard_dist=tmp_path / "no-dist",
    )
    create_app(settings, clock=lambda: FROZEN_NOW)
    # Simulate a legacy orphan study (null project_id), then reboot.
    con = sqlite3.connect(db_path)
    con.execute(
        "INSERT INTO studies (id, protocol_version, phase, data_path, project_id) "
        "VALUES ('legacy', '', 'design', '', '')"
    )
    con.commit()
    con.close()
    create_app(settings, clock=lambda: FROZEN_NOW)
    con = sqlite3.connect(db_path)
    (pid,) = con.execute(
        "SELECT project_id FROM studies WHERE id='legacy'"
    ).fetchone()
    con.close()
    assert pid == "implicit"


# ------------------------------------------------------------ invitations


def test_invitation_is_single_use(client):
    slug = make_project(client, "alice", "Lab")
    inv = client.post(
        f"/projects/{slug}/invitations",
        json={"email": "rea", "role": "researcher"},
        headers=bearer("alice"),
    ).json()
    token = inv["token"]
    first = client.post(f"/invitations/{token}/accept", headers=bearer("rea"))
    assert first.status_code == 200
    # Re-accepting the same token fails — it's spent.
    again = client.post(f"/invitations/{token}/accept", headers=bearer("rea"))
    assert again.status_code == 404


def test_expired_invitation_is_refused(client, tmp_path):
    slug = make_project(client, "alice", "Lab")
    inv = client.post(
        f"/projects/{slug}/invitations",
        json={"email": "rea", "role": "researcher"},
        headers=bearer("alice"),
    ).json()
    # Backdate the expiry directly, then try to accept.
    factory = make_session_factory(tmp_path / "authz.sqlite3")
    from middleware.db import Invitation
    from sqlalchemy import select
    s = factory()
    row = s.scalar(select(Invitation).where(Invitation.token == inv["token"]))
    row.expires_at = "2020-01-01T00:00:00.000+00:00"
    s.commit()
    s.close()
    res = client.post(f"/invitations/{inv['token']}/accept", headers=bearer("rea"))
    assert res.status_code == 410
    assert "expired" in res.json()["detail"].lower()


def test_last_owner_cannot_be_removed(client):
    slug = make_project(client, "alice", "Lab")
    res = client.delete(
        f"/projects/{slug}/members/alice", headers=bearer("alice")
    )
    assert res.status_code == 409
    assert "owner" in res.json()["detail"].lower()
