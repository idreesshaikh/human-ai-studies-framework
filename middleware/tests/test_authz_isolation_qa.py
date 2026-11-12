"""Focused QA regressions for read-only membership and credential boundaries."""

import datetime as dt
import sqlite3
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.auth import Identity
from middleware.db import Membership, SessionBlock, SessionOpen, make_session_factory
from middleware.settings import Settings

from middleware import auth as auth_mod

ROOT = Path(__file__).parents[2]
FROZEN_NOW = dt.datetime(2026, 11, 11, 12, 0, tzinfo=dt.UTC)


def _fake_verifier(authorization: str) -> Identity:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    sub = authorization.removeprefix("Bearer ")
    return Identity(sub=sub, display_name=sub, mode="token")


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(auth_mod, "verifier_from_settings", lambda _s: _fake_verifier)
    settings = Settings(
        db_path=tmp_path / "authz-isolation.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        spa_dist=tmp_path / "no-dist",
    )
    tc = TestClient(create_app(settings, clock=lambda: FROZEN_NOW))
    tc.db_path = settings.db_path
    return tc


def bearer(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {sub}"}


def make_project(client: TestClient, owner: str, name: str) -> str:
    made = client.post("/projects", json={"name": name}, headers=bearer(owner))
    assert made.status_code == 200, made.text
    return made.json()["slug"]


def make_study(client: TestClient, owner: str, slug: str, name: str) -> str:
    made = client.post(
        f"/projects/{slug}/studies",
        json={"name": name},
        headers=bearer(owner),
    )
    assert made.status_code == 200, made.text
    return made.json()["id"]


def test_viewer_can_read_and_export_but_cannot_contribute_or_enroll(client):
    slug = make_project(client, "owner", "Role boundary")
    study = make_study(client, "owner", slug, "A private study")

    invitation = client.post(
        f"/projects/{slug}/invitations",
        json={"role": "member"},
        headers=bearer("owner"),
    )
    assert invitation.status_code == 200, invitation.text
    accepted = client.post(
        f"/invitations/{invitation.json()['token']}/accept",
        headers=bearer("analyst"),
    )
    assert accepted.status_code == 200, accepted.text

    # Viewer is an owner-assigned internal read-only role, never an invite role.
    viewer_invite = client.post(
        f"/projects/{slug}/invitations",
        json={"role": "viewer"},
        headers=bearer("owner"),
    )
    assert viewer_invite.status_code == 400
    promoted = client.patch(
        f"/projects/{slug}/members/analyst",
        json={"role": "viewer"},
        headers=bearer("owner"),
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "viewer"

    home = client.get(f"/projects/{slug}", headers=bearer("analyst"))
    assert home.status_code == 200, home.text
    roles = {m["identitySub"]: m["role"] for m in home.json()["members"]}
    assert roles["analyst"] == "viewer"
    data = client.get(f"/studies/{study}/dataset", headers=bearer("analyst"))
    assert data.status_code == 200
    assert (
        client.get(
            f"/studies/{study}/papers/arxiv:2507.09089/links",
            headers=bearer("analyst"),
        ).status_code
        == 200
    )

    # A viewer cannot mutate the library or mint participant credentials.
    assert (
        client.put(
            f"/studies/{study}/papers/arxiv:2507.09089/links",
            json={"targets": ["RQ-1"]},
            headers=bearer("analyst"),
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/studies/{study}/enrollment/tokens",
            json={"count": 1, "grain": "participant"},
            headers=bearer("analyst"),
        ).status_code
        == 403
    )

    # The regular member role remains a contributor and can make the same edit.
    demoted = client.patch(
        f"/projects/{slug}/members/analyst",
        json={"role": "member"},
        headers=bearer("owner"),
    )
    assert demoted.status_code == 200, demoted.text
    edit = client.put(
        f"/studies/{study}/papers/arxiv:2507.09089/links",
        json={"targets": ["RQ-1"]},
        headers=bearer("analyst"),
    )
    assert edit.status_code in (200, 404), edit.text


def test_participant_credential_is_study_bound_and_not_a_project_identity(client):
    example = yaml.safe_load((ROOT / "protocol/examples/planner-v6.yaml").read_text())
    studies = []
    for owner, project_name in (("owner-a", "Study A"), ("owner-b", "Study B")):
        slug = make_project(client, owner, project_name)
        protocol = dict(example)
        protocol["study"] = dict(example["study"])
        protocol["study"]["id"] = "draft"
        protocol["study"]["title"] = project_name
        made = client.post(
            f"/projects/{slug}/studies",
            json={"name": project_name, "protocol": protocol},
            headers=bearer(owner),
        )
        assert made.status_code == 200, made.text
        studies.append(made.json()["id"])

    study_a, study_b = studies
    minted = client.post(
        f"/studies/{study_a}/enrollment/tokens",
        json={"count": 1, "grain": "participant"},
        headers=bearer("owner-a"),
    )
    assert minted.status_code == 200, minted.text
    raw = minted.json()[0]["connectionString"].rsplit("#", 1)[1]
    paired = client.post("/pair/redeem", json={"token": raw})
    assert paired.status_code == 200, paired.text
    credential = paired.json()["sessionCredential"]
    session_headers = {"Authorization": f"Bearer {credential}"}

    own_config = client.get(
        f"/studies/{study_a}/capture-config", headers=session_headers
    )
    assert own_config.status_code == 200, own_config.text
    cross_config = client.get(
        f"/studies/{study_b}/capture-config", headers=session_headers
    )
    assert cross_config.status_code == 401

    # Session credentials do not confer researcher membership on project APIs.
    project_data = client.get(f"/studies/{study_a}/dataset", headers=session_headers)
    assert project_data.status_code == 403

    # A valid credential from A must not let a participant write into B's known
    # scheduled session, which would contaminate B's exports under A's identity.
    factory = make_session_factory(f"sqlite:///{client.db_path}")
    with factory() as session:
        session.add(
            SessionBlock(
                session_id="a-private-session",
                study_id=study_a,
                participant_id="P01",
                block_index=0,
                task_id="task-a",
                condition="ai-assisted",
                assigned_at="2026-11-11T12:00:00+00:00",
            )
        )
        session.add(
            SessionBlock(
                session_id="b-private-session",
                study_id=study_b,
                participant_id="P01",
                block_index=0,
                task_id="task-b",
                condition="unassisted",
                assigned_at="2026-11-11T12:00:00+00:00",
            )
        )
        session.add(
            SessionOpen(
                session_id="b-open-session",
                study_id=study_b,
                protocol_version=1,
                opened_at="2026-11-11T12:00:00+00:00",
            )
        )
        session.commit()

    def event(session_id: str, seq: int) -> dict:
        return {
            "v": 2,
            "ts": f"2026-11-11T12:01:{seq:02d}+00:00",
            "mono": float(seq),
            "sessionId": session_id,
            "participantId": "P01",
            "condition": "unassisted",
            "seq": seq,
            "type": "fatigue_response",
            "payload": {"answer": 3},
        }

    foreign_ingest = client.post(
        "/ingest/events",
        # The batch must be rejected atomically: a valid A session preceding B's
        # foreign session cannot leave a partial write behind.
        json=[event("a-private-session", 0), event("b-private-session", 1)],
        headers=session_headers,
    )
    assert foreign_ingest.status_code == 403, foreign_ingest.text

    # SessionOpen is also an ownership mapping when a session has no planned block.
    foreign_open_ingest = client.post(
        "/ingest/events",
        json=[event("b-open-session", 2)],
        headers=session_headers,
    )
    assert foreign_open_ingest.status_code == 403, foreign_open_ingest.text
    foreign_metric = client.post(
        "/ingest/metrics",
        json=[
            {
                "sessionId": "b-private-session",
                "participantId": "P01",
                "condition": "unassisted",
                "taskId": "task-b",
                "schemaVersion": 1,
                "metricId": "foreign-metric-1",
                "timestamp": "2026-11-11T12:01:00+00:00",
                "file": "task.py",
                "parameter_count": 2,
            }
        ],
        headers=session_headers,
    )
    assert foreign_metric.status_code == 403, foreign_metric.text

    # The same credential cannot use another participant's scheduled block inside
    # its own study, even if the session ID and study ID are valid.
    second_token = client.post(
        f"/studies/{study_a}/enrollment/tokens",
        json={"count": 1, "grain": "participant"},
        headers=bearer("owner-a"),
    )
    assert second_token.status_code == 200, second_token.text
    second_raw = second_token.json()[0]["connectionString"].rsplit("#", 1)[1]
    second_pair = client.post("/pair/redeem", json={"token": second_raw})
    assert second_pair.status_code == 200, second_pair.text
    other_credential = second_pair.json()["sessionCredential"]
    assert second_pair.json()["participantId"] != paired.json()["participantId"]
    other_session = "a-other-participant-session"
    other_config = client.get(
        f"/studies/{study_a}/capture-config?sessionId={other_session}",
        headers={"Authorization": f"Bearer {other_credential}"},
    )
    assert other_config.status_code == 200, other_config.text
    other_condition = other_config.json()["block"]["condition"]
    cross_participant_event = event(other_session, 3)
    cross_participant_event["condition"] = other_condition
    assert (
        client.post(
            "/ingest/events",
            json=[cross_participant_event],
            headers=session_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/ingest/metrics",
            json=[
                {
                    "sessionId": other_session,
                    "participantId": "P01",
                    "condition": other_condition,
                    "taskId": other_config.json()["block"]["taskId"],
                    "schemaVersion": 1,
                    "metricId": "other-participant-metric",
                    "timestamp": "2026-11-11T12:01:03+00:00",
                    "file": "task.py",
                    "parameter_count": 2,
                }
            ],
            headers=session_headers,
        ).status_code
        == 403
    )

    a_data = client.get(f"/studies/{study_a}/dataset", headers=bearer("owner-a"))
    assert a_data.status_code == 200, a_data.text
    assert a_data.json()["rows"] == []
    b_data = client.get(f"/studies/{study_b}/dataset", headers=bearer("owner-b"))
    assert b_data.status_code == 200, b_data.text
    assert b_data.json()["rows"] == []

    own_metric = client.post(
        "/ingest/metrics",
        json=[
            {
                "sessionId": "a-private-session",
                "participantId": "forged-participant",
                "condition": "unassisted",
                "taskId": "forged-task",
                "schemaVersion": 1,
                "metricId": "own-metric-1",
                "timestamp": "2026-11-11T12:02:00+00:00",
                "file": "task.py",
                "parameter_count": 2,
            }
        ],
        headers=session_headers,
    )
    assert own_metric.status_code == 200, own_metric.text
    own_rows = client.get(
        f"/studies/{study_a}/dataset", headers=bearer("owner-a")
    ).json()["rows"]
    assert len(own_rows) == 1
    assert own_rows[0]["participantId"] == "P01"
    assert own_rows[0]["condition"] == "ai-assisted"
    assert own_rows[0]["taskId"] == "task-a"
    assert "credential-mismatch" in own_rows[0]["flags"]

    # A participant-grain link may resume the same participant, and keeps the same
    # study-scoped credential across that reuse.
    resumed = client.post("/pair/redeem", json={"token": raw})
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["sessionCredential"] == credential


def test_existing_membership_check_is_migrated_without_losing_rows(tmp_path):
    """A pre-viewer DB upgrades its CHECK and retains existing memberships."""
    db_path = tmp_path / "legacy-memberships.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE memberships ("
        "project_id VARCHAR NOT NULL, identity_sub VARCHAR NOT NULL, "
        "role VARCHAR NOT NULL, invited_by VARCHAR NOT NULL, "
        "joined_at VARCHAR NOT NULL, "
        "PRIMARY KEY (project_id, identity_sub), "
        "CONSTRAINT ck_membership_role CHECK (role IN ('owner', 'member'))"
        ")"
    )
    conn.execute(
        "INSERT INTO memberships VALUES ('implicit', 'local', 'owner', '', '')"
    )
    conn.commit()
    conn.close()

    factory = make_session_factory(db_path)
    with factory() as session:
        existing = session.get(Membership, ("implicit", "local"))
        assert existing is not None and existing.role == "owner"
        session.add(
            Membership(
                project_id="implicit",
                identity_sub="read-only-auditor",
                role="viewer",
                invited_by="local",
                joined_at="2026-11-11T12:00:00+00:00",
            )
        )
        session.commit()

    with factory() as session:
        viewer = session.get(Membership, ("implicit", "read-only-auditor"))
        assert viewer is not None and viewer.role == "viewer"
