"""Project scoping + the permission matrix."""

import datetime as dt
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from middleware.app import _slug_from_text, create_app
from middleware.auth import Identity
from middleware.authz import CAPABILITIES, ROLE_RANK, Role, has_role
from middleware.db import make_session_factory
from middleware.settings import Settings

from middleware import auth as auth_mod

FROZEN_NOW = dt.datetime(2026, 7, 18, 12, 0, tzinfo=dt.UTC)


def _fake_verifier(authorization: str) -> Identity:
    """
    A test verifier: ``Authorization: Bearer <sub>`` becomes a clerk-mode identity whose
    sub is the token.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    sub = authorization.removeprefix("Bearer ")
    return Identity(sub=sub, display_name=sub, mode="clerk")


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(auth_mod, "verifier_from_settings", lambda _s: _fake_verifier)
    settings = Settings(
        db_path=tmp_path / "authz.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        spa_dist=tmp_path / "no-dist",
    )
    tc = TestClient(create_app(settings, clock=lambda: FROZEN_NOW))
    tc.db_path = settings.db_path
    return tc


def bearer(sub: str) -> dict:
    return {"Authorization": f"Bearer {sub}"}


def make_project(client: TestClient, owner: str, name: str) -> str:
    """Create a project as ``owner`` (auto owner membership); return slug."""
    res = client.post("/projects", json={"name": name}, headers=bearer(owner))
    assert res.status_code == 200, res.text
    return res.json()["slug"]


def add_member(client, slug, owner, sub, role) -> None:
    """
    Invite ``sub`` at ``role`` and accept as that identity (the real flow).
    """
    inv = client.post(
        f"/projects/{slug}/invitations",
        json={"role": role},
        headers=bearer(owner),
    )
    assert inv.status_code == 200, inv.text
    token = inv.json()["token"]
    acc = client.post(f"/invitations/{token}/accept", headers=bearer(sub))
    assert acc.status_code == 200, acc.text


def test_matrix_is_data_every_role_capability_pair():
    """
    has_role agrees with the rank ordering for every capability × role — iterating the
    dict is what makes an untested capability impossible.
    """
    for capability, required in CAPABILITIES.items():
        for role in Role:
            expected = ROLE_RANK[role] >= ROLE_RANK[required]
            assert has_role(role, capability) is expected, f"{role} vs {capability}"


def test_non_member_never_satisfies_any_capability():
    for capability in CAPABILITIES:
        assert has_role(None, capability) is False


def test_create_project_makes_creator_owner(client):
    slug = make_project(client, "alice", "Alice's lab")
    mine = client.get("/projects", headers=bearer("alice")).json()
    assert [(p["slug"], p["role"]) for p in mine] == [(slug, "owner")]


def test_project_list_carries_the_shape_of_each_project(client):
    """
    A row says how many studies it holds (FR-PLAT-1), so the project list never has to
    fan out to ``/projects/{slug}`` once per row.
    """
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
    """
    Create and list return one type, not two wearing the same name: the client models a
    project once, and a new project is an empty one.
    """
    res = client.post("/projects", json={"name": "Fresh"}, headers=bearer("alice"))
    assert res.status_code == 200, res.text
    created = res.json()
    listed = client.get("/projects", headers=bearer("alice")).json()[0]

    assert created.keys() == listed.keys()
    assert created["role"] == "owner"
    assert created["studyCount"] == 0


def test_slug_from_text_backs_off_to_a_word_boundary():
    """
    A study name is often a whole typed sentence (the "describe your study"
    opening question), not a short title — a hard character cut lands
    mid-word as often as not, and that becomes the study's permanent id.
    """
    long = "Does AI pair programming change debugging time, comparing telemetry?"
    assert _slug_from_text(long, 40) == "does-ai-pair-programming-change"
    # No boundary within the limit at all: the hard cut is the only option.
    assert _slug_from_text("supercalifragilisticexpialidocious", 10) == (
        "supercalif"
    )
    # Short text well under the limit is untouched.
    assert _slug_from_text("Hello World", 40) == "hello-world"


def test_study_name_from_a_long_sentence_keeps_whole_words(client):
    slug = make_project(client, "alice", "Sentence lab")
    long = "Does AI pair programming change debugging time, comparing telemetry?"
    made = client.post(
        f"/projects/{slug}/studies", json={"name": long}, headers=bearer("alice")
    )
    assert made.status_code == 200, made.text
    words = {w.strip(",?").lower() for w in long.split()}
    last_word = made.json()["id"].split("-")[-1]
    assert last_word in words


def test_reposting_personal_reuses_the_existing_project(client):
    """
    Every "quick start" entry point posts {name: "Personal"} to land the caller in
    their one implicit project — the second and later calls must return the same
    project (with an accurate studyCount), not 500 on a nonexistent relationship.
    """
    first = client.post("/projects", json={"name": "Personal"}, headers=bearer("dee"))
    assert first.status_code == 200, first.text

    made = client.post(
        f"/projects/{first.json()['slug']}/studies",
        json={"name": "One"},
        headers=bearer("dee"),
    )
    assert made.status_code == 200, made.text

    second = client.post("/projects", json={"name": "Personal"}, headers=bearer("dee"))
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["studyCount"] == 1


def test_delete_study_is_owner_only_and_removes_it(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "member")
    made = client.post(
        f"/projects/{slug}/studies", json={"name": "Doomed"}, headers=bearer("rea")
    )
    assert made.status_code == 200, made.text
    study_id = made.json()["id"]

    denied = client.delete(f"/studies/{study_id}", headers=bearer("rea"))
    assert denied.status_code == 403

    ok = client.delete(f"/studies/{study_id}", headers=bearer("alice"))
    assert ok.status_code == 200 and ok.json()["deleted"] == study_id
    home = client.get(f"/projects/{slug}", headers=bearer("alice")).json()
    assert study_id not in [s["id"] for s in home["studies"]]
    gone = client.delete(f"/studies/{study_id}", headers=bearer("alice"))
    assert gone.status_code == 404


def test_a_studys_library_is_closed_to_non_members(client):
    """A member edits a study's library; a stranger cannot even read it."""
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "member")
    study_id = client.post(
        f"/projects/{slug}/studies", json={"name": "Library"}, headers=bearer("alice")
    ).json()["id"]
    ref = "arxiv:2507.09089"

    for sub in ("alice", "rea"):
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

    for method, path in (
        ("put", f"/studies/{study_id}/papers/{ref}/links"),
        ("delete", f"/studies/{study_id}/papers/{ref}"),
    ):
        call = getattr(client, method)
        kwargs = {"json": {"targets": ["RQ-1"]}} if method == "put" else {}
        # A member passes the gate (the DELETE then 404s on a paper that was never
        # ingested — the point is which side of the gate they land).
        allowed = call(path, headers=bearer("rea"), **kwargs)
        assert allowed.status_code in (200, 404), allowed.text
        assert call(path, headers=bearer("stranger"), **kwargs).status_code == 403


def test_view_capability_across_roles(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "member")
    for sub in ("alice", "rea"):
        assert client.get(f"/projects/{slug}", headers=bearer(sub)).status_code == 200
    stranger = client.get(f"/projects/{slug}", headers=bearer("stranger"))
    assert stranger.status_code == 403


def test_manage_members_is_owner_only_with_uniform_403(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "member")
    res = client.patch(
        f"/projects/{slug}/members/rea",
        json={"role": "owner"},
        headers=bearer("rea"),
    )
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert detail and "role" in detail.lower()


def test_member_can_invite_but_not_mint_owner(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "member")

    ok = client.post(
        f"/projects/{slug}/invitations",
        json={"role": "member"},
        headers=bearer("rea"),
    )
    assert ok.status_code == 200
    assert ok.json()["url"].startswith("/invitations/")
    assert ok.json()["role"] == "member"

    # A member cannot escalate by inviting an owner.
    escalate = client.post(
        f"/projects/{slug}/invitations",
        json={"role": "owner"},
        headers=bearer("rea"),
    )
    assert escalate.status_code == 403


def test_delete_is_owner_only(client):
    slug = make_project(client, "alice", "Lab")
    add_member(client, slug, "alice", "rea", "member")
    assert (
        client.request(
            "DELETE",
            f"/projects/{slug}",
            json={"confirm": "DELETE"},
            headers=bearer("rea"),
        ).status_code
        == 403
    )
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
    """
    studies.project_id carries a real FK with no ON DELETE CASCADE — Postgres (the
    production database) 500s on a dangling reference if a project's studies aren't
    cascaded first.
    """
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
    gone = client.delete(f"/studies/{study_id}", headers=bearer("alice"))
    assert gone.status_code == 404


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
    assert client.get("/projects/nope", headers=bearer("alice")).status_code == 404
    _ = p1


def test_every_project_scoped_route_carries_the_choke_point(client):
    """
    No project-scoped route enforces membership only in the frontend: each
    ``/projects/{slug}/...`` and ``/studies/{study_id}/...`` route depends on a
    require_project* factory.
    """
    app = client.app
    # Routes that legitimately don't take a project/study scope check.
    exempt = {
        ("POST", "/projects"),
        ("GET", "/projects"),
        ("POST", "/invitations/{token}/accept"),
        ("GET", "/me"),
        # The participant's editor holds a session credential, never a project identity,
        # so this one is gated on that credential instead (it 401s without it) — see
        # get_capture_config's docstring, FR-INST-21.
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
    """Every capability a route is actually gated on."""
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


def test_boot_migration_adopts_orphan_studies(tmp_path, monkeypatch):
    """
    A study row left by a pre-projects middleware is adopted into the implicit project
    on boot, not orphaned or dropped.
    """
    monkeypatch.setattr(auth_mod, "verifier_from_settings", lambda _s: _fake_verifier)
    db_path = tmp_path / "legacy.sqlite3"
    settings = Settings(
        db_path=db_path,
        data_dir=tmp_path / "d",
        protocol_path=None,
        spa_dist=tmp_path / "no-dist",
    )
    create_app(settings, clock=lambda: FROZEN_NOW)
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


def test_invitation_link_is_reusable_until_revoked(client):
    slug = make_project(client, "alice", "Lab")
    inv = client.post(
        f"/projects/{slug}/invitations",
        json={"role": "member"},
        headers=bearer("alice"),
    ).json()
    token = inv["token"]
    first = client.post(f"/invitations/{token}/accept", headers=bearer("rea"))
    assert first.status_code == 200
    # A second person can use the same link — sharing, not single-use.
    second = client.post(f"/invitations/{token}/accept", headers=bearer("bob"))
    assert second.status_code == 200
    home = client.get(f"/projects/{slug}", headers=bearer("alice")).json()
    assert {m["identitySub"] for m in home["members"]} == {"alice", "rea", "bob"}
    # Revoking the link stops new people from joining.
    client.delete(f"/projects/{slug}/invitations/{inv['id']}", headers=bearer("alice"))
    gone = client.post(f"/invitations/{token}/accept", headers=bearer("carol"))
    assert gone.status_code == 404


def test_expired_invitation_is_refused(client, tmp_path):
    slug = make_project(client, "alice", "Lab")
    inv = client.post(
        f"/projects/{slug}/invitations",
        json={"role": "member"},
        headers=bearer("alice"),
    ).json()
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


def _event(seq: int, session: str, participant: str) -> dict:
    """One v2 StudyEvent in the extension's wire shape."""
    return {
        "v": 2,
        "ts": f"2026-07-18T10:00:{seq:02d}.000Z",
        "mono": seq * 1000.0,
        "sessionId": session,
        "participantId": participant,
        "condition": "ai-assisted",
        "seq": seq,
        "type": "fatigue_response",
        "payload": {"answer": 3},
    }


def _study_with_session(client, slug, owner, name, session_id, participant) -> str:
    """A study in ``slug`` with one open session carrying one event."""
    study = client.post(
        f"/projects/{slug}/studies", json={"name": name}, headers=bearer(owner)
    )
    assert study.status_code == 200, study.text
    study_id = study.json()["id"]
    opened = client.post(
        f"/studies/{study_id}/sessions/start",
        json={"sessionId": session_id},
        headers=bearer(owner),
    )
    assert opened.status_code == 200, opened.text
    posted = client.post("/ingest/events", json=[_event(0, session_id, participant)])
    assert posted.status_code == 200, posted.text
    return study_id


def test_session_list_is_scoped_to_its_own_study(client):
    """A study's session list holds only that study's sessions."""
    alice = make_project(client, "alice", "Alice's lab")
    bob = make_project(client, "bob", "Bob's lab")
    _study_with_session(client, alice, "alice", "alice study", "alice-s1", "A01")
    bob_study = _study_with_session(client, bob, "bob", "bob study", "bob-s1", "B01")

    res = client.get(f"/studies/{bob_study}/sessions", headers=bearer("bob"))
    assert res.status_code == 200, res.text
    listed = res.json()

    assert [row["sessionId"] for row in listed] == ["bob-s1"]
    assert "A01" not in {row["participantId"] for row in listed}


def test_session_list_includes_sessions_mapped_by_their_block(client):
    """A paired TERN session counts as its study's, without sessions/start."""
    from middleware.db import SessionBlock, make_session_factory

    slug = make_project(client, "alice", "Alice's lab")
    study = client.post(
        f"/projects/{slug}/studies", json={"name": "paired"}, headers=bearer("alice")
    ).json()["id"]

    factory = make_session_factory(f"sqlite:///{client.db_path}")
    with factory() as s:
        s.add(
            SessionBlock(
                session_id="paired-s1",
                study_id=study,
                participant_id="P01",
                block_index=0,
                task_id="t1",
                condition="ai-assisted",
                assigned_at="2026-07-18T10:00:00+00:00",
            )
        )
        s.commit()

    client.post("/ingest/events", json=[_event(0, "paired-s1", "P01")])

    listed = client.get(f"/studies/{study}/sessions", headers=bearer("alice")).json()
    assert [row["sessionId"] for row in listed] == ["paired-s1"]


def test_unattributed_sessions_are_never_adopted_when_multi_tenant(client):
    """An unpaired session belongs to nobody here, not to whoever asks first."""
    slug = make_project(client, "alice", "Alice's lab")
    study = client.post(
        f"/projects/{slug}/studies", json={"name": "clean"}, headers=bearer("alice")
    ).json()["id"]

    client.post("/ingest/events", json=[_event(0, "drive-by", "X99")])

    listed = client.get(f"/studies/{study}/sessions", headers=bearer("alice")).json()
    assert listed == []


def test_session_events_refused_to_a_non_member(client):
    """Knowing a session id is not authorisation to read it."""
    alice = make_project(client, "alice", "Alice's lab")
    _study_with_session(client, alice, "alice", "alice study", "alice-s1", "A01")
    make_project(client, "bob", "Bob's lab")

    events = client.get("/sessions/alice-s1/events", headers=bearer("bob"))
    assert events.status_code in (403, 404), events.text
    gaps = client.get("/sessions/alice-s1/gaps", headers=bearer("bob"))
    assert gaps.status_code in (403, 404), gaps.text

    mine = client.get("/sessions/alice-s1/events", headers=bearer("alice"))
    assert mine.status_code == 200, mine.text
    assert [e["seq"] for e in mine.json()] == [0]


def test_two_researchers_may_both_name_a_project_test(client):
    """A project name is not a global resource to be claimed first."""
    first = client.post("/projects", json={"name": "test"}, headers=bearer("alice"))
    second = client.post("/projects", json={"name": "test"}, headers=bearer("bob"))

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["name"] == second.json()["name"] == "test"
    assert first.json()["slug"] != second.json()["slug"]
    assert len(client.get("/projects", headers=bearer("bob")).json()) == 1


def test_an_explicitly_chosen_slug_still_reports_a_collision(client):
    """Auto-disambiguation is for a slug the platform derived."""
    client.post(
        "/projects", json={"name": "One", "slug": "shared"}, headers=bearer("alice")
    )
    clash = client.post(
        "/projects", json={"name": "Two", "slug": "shared"}, headers=bearer("bob")
    )
    assert clash.status_code == 409, clash.text


def test_the_demo_project_is_readable_by_anyone_who_signs_in(client):
    """One fully-built study everybody can look at, nobody can edit."""
    from middleware.demo import seed_demo

    seed_demo(f"sqlite:///{client.db_path}")

    listed = client.get("/projects", headers=bearer("newcomer")).json()
    demo = [p for p in listed if p["slug"] == "demo"]
    assert demo, f"the demo is not offered to a new identity: {listed}"
    assert demo[0]["role"] == "viewer"
    assert demo[0]["studyCount"] == 1


def test_the_demo_project_cannot_be_written_to(client):
    """
    Viewer, and only viewer: a shared example that any visitor could add a study to,
    rename, or delete is not an example for long.
    """
    from middleware.demo import seed_demo

    seed_demo(f"sqlite:///{client.db_path}")

    assert client.get("/projects/demo", headers=bearer("newcomer")).status_code == 200
    assert (
        client.post(
            "/projects/demo/studies",
            json={"name": "mine"},
            headers=bearer("newcomer"),
        ).status_code
        == 403
    )
    assert (
        client.request(
            "DELETE",
            "/projects/demo",
            json={"confirm": "DELETE"},
            headers=bearer("newcomer"),
        ).status_code
        == 403
    )


def test_status_only_reports_this_study_s_sessions(client):
    """
    `/status` read `Event` with no study scoping at all: it grouped every event
    row in the database by session and returned the lot, so one project's Data
    tab listed another project's sessions and participants. `/sessions` had
    closed exactly this leak; `/status` answers the same question and never got
    the same treatment. Both now share `_session_scope`.
    """
    from middleware.demo import DEMO_STUDY_ID, seed_demo

    seed_demo(f"sqlite:///{client.db_path}")
    client.post("/ingest/events", json=[_event(0, "S-sample-001", "P01")])

    slug = make_project(client, "alice", "Other lab")
    # `/status` needs a protocol before it will report anything, so this study
    # is seeded with a minimal one — the leak being tested is about whose
    # sessions come back, not about protocol resolution.
    mine = client.post(
        f"/projects/{slug}/studies",
        json={
            "name": "Mine",
            "protocol": {
                "protocolVersion": 4,
                "study": {"id": "mine", "title": "Mine"},
                "researchQuestions": [{"id": "RQ-1", "text": "A question?"}],
                "conditions": ["ai-assisted"],
                "participants": {"planned": 2, "design": "within-subjects"},
                "phases": [{"name": "design", "gates": []}],
            },
        },
        headers=bearer("alice"),
    ).json()["id"]
    client.post(
        f"/studies/{mine}/sessions/start",
        json={"sessionId": "S-mine-001"},
        headers=bearer("alice"),
    )
    client.post("/ingest/events", json=[_event(0, "S-mine-001", "P09")])

    mine_status = client.get(f"/studies/{mine}/status", headers=bearer("alice")).json()
    assert [s["sessionId"] for s in mine_status["sessions"]] == ["S-mine-001"]

    demo_status = client.get(
        f"/studies/{DEMO_STUDY_ID}/status", headers=bearer("alice")
    ).json()
    assert "S-mine-001" not in [s["sessionId"] for s in demo_status["sessions"]]


def test_the_demo_study_resolves_a_protocol(client):
    """
    The demo exists to be "one fully-built study anybody can look at", and every
    panel that shows collected data — the whole Data tab, Planning, /status —
    gates on the study resolving a protocol. It never could: the seeder wrote a
    project, a study row and session mappings but no protocol, and the boot
    protocol (when one is loaded at all) is a different study id, so all three
    resolution paths missed and /status 404'd on the one study seeded with real
    sessions and metrics.
    """
    from middleware.demo import DEMO_STUDY_ID, seed_demo

    seed_demo(f"sqlite:///{client.db_path}")

    res = client.get(f"/studies/{DEMO_STUDY_ID}/protocol", headers=bearer("newcomer"))
    assert res.status_code == 200, res.text
    proto = res.json()
    # The design the bundled sample sessions actually implement — P02 appears in
    # both conditions, so a demo protocol claiming anything else would describe
    # data the demo does not have.
    assert proto["conditions"] == ["ai-assisted", "unassisted"]
    assert proto["participants"]["design"] == "within-subjects"

    status = client.get(f"/studies/{DEMO_STUDY_ID}/status", headers=bearer("newcomer"))
    assert status.status_code == 200, status.text


def test_the_demo_study_shows_the_design_record(client):
    """The read-only demo includes the conversation it is meant to teach."""
    from middleware.demo import DEMO_STUDY_ID, seed_demo

    seed_demo(f"sqlite:///{client.db_path}")

    conversation = client.get(
        f"/studies/{DEMO_STUDY_ID}/conversation", headers=bearer("newcomer")
    )
    assert conversation.status_code == 200, conversation.text
    turns = conversation.json()["turns"]
    platform_turn = next(turn for turn in turns if turn["role"] == "platform")
    assert platform_turn["source"] == "demo"
    assert platform_turn["moves"]
    assert platform_turn["recommendations"]


def test_the_demo_study_shows_its_paired_prescription(client):
    """Domain recipe IDs still resolve through the protocol's design shape."""
    from middleware.demo import DEMO_STUDY_ID, seed_demo

    seed_demo(f"sqlite:///{client.db_path}")

    response = client.get(
        f"/analysis/prescriptions?study_id={DEMO_STUDY_ID}",
        headers=bearer("newcomer"),
    )
    assert response.status_code == 200, response.text
    assert [row["designShape"] for row in response.json()["prescriptions"]] == ["paired"]


def test_the_demo_study_owns_the_sample_sessions(client):
    """
    The seeded sample data belongs to the demo study, so it shows there — and nowhere
    else.
    """
    from middleware.demo import DEMO_STUDY_ID, seed_demo

    seed_demo(f"sqlite:///{client.db_path}")
    client.post("/ingest/events", json=[_event(0, "S-sample-001", "P01")])

    rows = client.get(
        f"/studies/{DEMO_STUDY_ID}/sessions", headers=bearer("newcomer")
    ).json()
    assert [r["sessionId"] for r in rows] == ["S-sample-001"]

    mine = make_project(client, "newcomer", "My lab")
    study = client.post(
        f"/projects/{mine}/studies", json={"name": "fresh"}, headers=bearer("newcomer")
    ).json()["id"]
    mine_rows = client.get(
        f"/studies/{study}/sessions", headers=bearer("newcomer")
    ).json()
    assert mine_rows == []
