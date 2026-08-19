"""Project scoping + the permission matrix.

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
    monkeypatch.setattr(auth_mod, "verifier_from_settings", lambda _s: _fake_verifier)
    settings = Settings(
        db_path=tmp_path / "authz.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        spa_dist=tmp_path / "no-dist",
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
            assert has_role(role, capability) is expected, f"{role} vs {capability}"


def test_non_member_never_satisfies_any_capability():
    for capability in CAPABILITIES:
        assert has_role(None, capability) is False


# ------------------------------------------------------ server-side enforcement


def test_create_project_makes_creator_owner(client):
    slug = make_project(client, "alice", "Alice's lab")
    mine = client.get("/projects", headers=bearer("alice")).json()
    assert [(p["slug"], p["role"]) for p in mine] == [(slug, "owner")]


def test_project_list_carries_the_shape_of_each_project(client):
    """A row says how many studies it holds (FR-PLAT-1), so the project list
    never has to fan out to ``/projects/{slug}`` once per row.

    It used to carry a lifecycle phase mix too. That went with the lifecycle
    board: with no phases to advance through, every study reported the same
    one and the breakdown said nothing."""
    slug = make_project(client, "alice", "Counted lab")

    empty = client.get("/projects", headers=bearer("alice")).json()[0]
    assert empty["studyCount"] == 0
    assert "phaseCounts" not in empty

    for name in ("One", "Two"):
        made = client.post(
            f"/projects/{slug}/studies", json={"name": name}, headers=bearer("alice")
        )
        assert made.status_code == 200, made.text

    row = client.get("/projects", headers=bearer("alice")).json()[0]
    assert row["studyCount"] == 2


def test_created_project_has_the_same_shape_as_a_listed_one(client):
    """Create and list return one type, not two wearing the same name: the
    client models a project once, and a new project is an empty one."""
    res = client.post("/projects", json={"name": "Fresh"}, headers=bearer("alice"))
    assert res.status_code == 200, res.text
    created = res.json()
    listed = client.get("/projects", headers=bearer("alice")).json()[0]

    assert created.keys() == listed.keys()
    assert created["role"] == "owner"
    assert created["studyCount"] == 0


def test_delete_study_is_owner_only_and_removes_it(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "researcher")
    made = client.post(
        f"/projects/{slug}/studies", json={"name": "Doomed"}, headers=bearer("rea")
    )
    assert made.status_code == 200, made.text
    study_id = made.json()["id"]

    # A researcher can start a study but not delete one (owner-only).
    denied = client.delete(f"/studies/{study_id}", headers=bearer("rea"))
    assert denied.status_code == 403

    # The owner can, and it's gone from the project afterwards.
    ok = client.delete(f"/studies/{study_id}", headers=bearer("alice"))
    assert ok.status_code == 200 and ok.json()["deleted"] == study_id
    home = client.get(f"/projects/{slug}", headers=bearer("alice")).json()
    assert study_id not in [s["id"] for s in home["studies"]]
    # Deleting a missing study 404s.
    gone = client.delete(f"/studies/{study_id}", headers=bearer("alice"))
    assert gone.status_code == 404


def test_a_studys_library_is_not_open_to_viewers(client):
    """A viewer reads a study; they do not edit its library.

    These three routes were gated on bare authentication rather than the
    project choke point, so any signed-in identity could delete another
    project's papers. The route audit missed them because it matched on
    parameter names, which a route's own {study_id} satisfies — both halves
    are fixed together, or the next one slips through the same way.
    """
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "researcher")
    add_member(client, slug, "alice", "vic", "viewer")
    study_id = client.post(
        f"/projects/{slug}/studies", json={"name": "Library"}, headers=bearer("alice")
    ).json()["id"]
    ref = "arxiv:2507.09089"

    # Reading a paper's protocol links is a view; every member may.
    for sub in ("alice", "rea", "vic"):
        assert (
            client.get(
                f"/studies/{study_id}/papers/{ref}/links", headers=bearer(sub)
            ).status_code
            == 200
        )
    assert (
        client.get(
            f"/studies/{study_id}/papers/{ref}/links", headers=bearer("stranger")
        ).status_code
        == 403
    )

    # Editing them, or removing a paper, needs contribute.
    for method, path in (
        ("put", f"/studies/{study_id}/papers/{ref}/links"),
        ("delete", f"/studies/{study_id}/papers/{ref}"),
    ):
        call = getattr(client, method)
        kwargs = {"json": {"targets": ["RQ-1"]}} if method == "put" else {}
        assert call(path, headers=bearer("vic"), **kwargs).status_code == 403
        # A researcher passes the gate (the DELETE then 404s on a paper that
        # was never ingested — the point is which side of the gate they land).
        allowed = call(path, headers=bearer("rea"), **kwargs)
        assert allowed.status_code in (200, 404), allowed.text


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
    # A researcher and a viewer replaying an owner-only request (changing a
    # member's role) both get 403, each with a plain-language body (not an
    # empty/opaque error).
    for sub in ("rea", "vic"):
        res = client.patch(
            f"/projects/{slug}/members/vic",
            json={"role": "researcher"},
            headers=bearer(sub),
        )
        assert res.status_code == 403
        detail = res.json()["detail"]
        assert detail and "role" in detail.lower()


def test_researcher_can_invite_but_not_mint_owner(client):
    # D40: inviting a colleague is a researcher+ capability (members invite
    # peers), but only an owner can invite another owner.
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "researcher")
    add_member(client, slug, "alice", "vic", "viewer")

    ok = client.post(
        f"/projects/{slug}/invitations",
        json={"email": "peer@lab.example", "role": "researcher"},
        headers=bearer("rea"),
    )
    assert ok.status_code == 200
    assert ok.json()["url"].startswith("/invitations/")
    # No mail key configured in tests → degrades to copy-link, never sends.
    assert ok.json()["emailed"] is False

    # A researcher cannot escalate by inviting an owner.
    escalate = client.post(
        f"/projects/{slug}/invitations",
        json={"email": "boss@lab.example", "role": "owner"},
        headers=bearer("rea"),
    )
    assert escalate.status_code == 403

    # A viewer cannot invite at all.
    denied = client.post(
        f"/projects/{slug}/invitations",
        json={"email": "x@lab.example", "role": "viewer"},
        headers=bearer("vic"),
    )
    assert denied.status_code == 403


def test_delete_is_owner_only(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "researcher")
    assert (
        client.request(
            "DELETE",
            f"/projects/{slug}",
            json={"confirm": "DELETE"},
            headers=bearer("rea"),
        ).status_code
        == 403
    )
    # Owner deletes with the typed confirmation.
    assert (
        client.request(
            "DELETE",
            f"/projects/{slug}",
            json={"confirm": "DELETE"},
            headers=bearer("alice"),
        ).status_code
        == 200
    )


def test_delete_requires_typed_confirmation(client):
    slug = make_project(client, "alice", "Lab")
    assert (
        client.request(
            "DELETE",
            f"/projects/{slug}",
            json={"confirm": "wrong"},
            headers=bearer("alice"),
        ).status_code
        == 400
    )


def test_delete_project_removes_its_studies(client):
    """studies.project_id carries a real FK with no ON DELETE CASCADE —
    Postgres (the production database) 500s on a dangling reference if a
    project's studies aren't cascaded first. SQLite doesn't enforce that FK
    by default, so this only checks the studies are actually gone, not that
    a lax-FK engine would have caught the omission."""
    slug = make_project(client, "alice", "Lab")
    made = client.post(
        f"/projects/{slug}/studies", json={"name": "Doomed"}, headers=bearer("alice")
    )
    assert made.status_code == 200, made.text
    study_id = made.json()["id"]

    assert (
        client.request(
            "DELETE",
            f"/projects/{slug}",
            json={"confirm": "DELETE"},
            headers=bearer("alice"),
        ).status_code
        == 200
    )
    # Deleting a missing study 404s (test_delete_study_is_owner_only_and_...
    # confirms this) — reused here to prove the study didn't survive the
    # project it belonged to.
    gone = client.delete(f"/studies/{study_id}", headers=bearer("alice"))
    assert gone.status_code == 404


# ------------------------------------------------------------ cross-project


def test_cross_project_access_refused(client):
    p1 = make_project(client, "alice", "One")
    make_project(client, "bob", "Two")
    p2 = client.get("/projects", headers=bearer("bob")).json()[0]["slug"]
    # Alice is not a member of Bob's project — she can't read or delete it.
    assert client.get(f"/projects/{p2}", headers=bearer("alice")).status_code == 403
    assert (
        client.request(
            "DELETE",
            f"/projects/{p2}",
            json={"confirm": "DELETE"},
            headers=bearer("alice"),
        ).status_code
        == 403
    )
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
        # The participant's editor holds a session credential, never a project
        # identity, so this one is gated on that credential instead (it 401s
        # without it) — see get_capture_config's docstring, FR-INST-21.
        ("GET", "/studies/{study_id}/capture-config"),
    }
    offenders = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set()) or set()
        if not (path.startswith(("/projects", "/studies/"))):
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            if (method, path) in exempt:
                continue
            dep = getattr(route, "dependant", None)
            if not _authz_capabilities(dep):
                offenders.append((method, path))
    assert not offenders, f"routes missing the choke point: {offenders}"


def _authz_capabilities(dependant) -> set:
    """Every capability a route is actually gated on.

    Looks for the ``__authz_capability__`` stamp ``authz.build_authz`` puts on
    its closures. The earlier version of this audit collected *parameter
    names* and passed a route if it mentioned ``slug`` or ``study_id`` — but
    FastAPI's dependant tree includes the endpoint's own path params, so every
    ``/studies/{study_id}/...`` route satisfied that test whether or not it
    was guarded. ``DELETE /studies/{id}/papers/{ref}`` shipped unguarded
    through exactly that blind spot.
    """
    capabilities = set()
    stack = [dependant] if dependant else []
    while stack:
        d = stack.pop()
        call = getattr(d, "call", None)
        capability = getattr(call, "__authz_capability__", None)
        if capability:
            capabilities.add(capability)
        stack.extend(getattr(d, "dependencies", []))
    return capabilities


# ------------------------------------------------------------ boot migration


def test_boot_migration_adopts_orphan_studies(tmp_path, monkeypatch):
    """A study row left by a pre-projects middleware is adopted into the
    implicit project on boot, not orphaned or dropped."""
    monkeypatch.setattr(auth_mod, "verifier_from_settings", lambda _s: _fake_verifier)
    db_path = tmp_path / "legacy.sqlite3"
    # First boot creates the schema (and the implicit project).
    settings = Settings(
        db_path=db_path,
        data_dir=tmp_path / "d",
        protocol_path=None,
        spa_dist=tmp_path / "no-dist",
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
    (pid,) = con.execute("SELECT project_id FROM studies WHERE id='legacy'").fetchone()
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
    res = client.delete(f"/projects/{slug}/members/alice", headers=bearer("alice"))
    assert res.status_code == 409
    assert "owner" in res.json()["detail"].lower()
