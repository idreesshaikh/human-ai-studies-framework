"""Project payloads distinguish a saved or boot protocol from an empty study."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.auth import Identity
from middleware.settings import Settings
from pytest import fixture

FROZEN_NOW = datetime(2026, 8, 19, 10, 0, tzinfo=UTC)


@fixture
def client(tmp_path, monkeypatch) -> TestClient:
    import middleware.auth as auth_mod

    def _fake_verifier(authorization: str) -> Identity:
        if not authorization.startswith("Bearer "):
            raise auth_mod.HTTPException(401, "missing bearer token")
        sub = authorization.removeprefix("Bearer ")
        return Identity(sub=sub, display_name=sub, mode="clerk")

    monkeypatch.setattr(auth_mod, "verifier_from_settings", lambda _s: _fake_verifier)
    settings = Settings(
        db_path=tmp_path / "power.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=None,
        spa_dist=tmp_path / "no-dist",
    )
    client = TestClient(create_app(settings, clock=lambda: FROZEN_NOW))
    client.db_path = settings.db_path
    return client


def bearer(sub: str) -> dict:
    return {"Authorization": f"Bearer {sub}"}


MINIMAL_PROTOCOL = {
    "protocolVersion": 4,
    "study": {"id": "x", "title": "X"},
    "researchQuestions": [{"id": "RQ-1", "text": "A question?"}],
    "conditions": ["ai-assisted"],
    "participants": {"planned": 2, "design": "within-subjects"},
    "phases": [{"name": "design", "gates": []}],
}


def test_project_payload_flags_studies_with_a_protocol(client):
    slug = client.post(
        "/projects", json={"name": "Lab"}, headers=bearer("alice")
    ).json()["slug"]
    bare = client.post(
        f"/projects/{slug}/studies", json={"name": "Bare"}, headers=bearer("alice")
    ).json()["id"]
    full = client.post(
        f"/projects/{slug}/studies",
        json={"name": "Full", "protocol": MINIMAL_PROTOCOL},
        headers=bearer("alice"),
    ).json()["id"]
    res = client.get(f"/projects/{slug}", headers=bearer("alice"))
    assert res.status_code == 200, res.text
    studies = {s["id"]: s for s in res.json()["studies"]}
    assert studies[bare]["hasProtocol"] is False
    assert studies[full]["hasProtocol"] is True


def test_boot_protocol_is_reported_without_a_saved_draft(tmp_path):
    from middleware.db import ProtocolDraftRow, make_session_factory
    from protocol.loader import load_protocol

    protocol_path = (
        Path(__file__).resolve().parents[2] / "protocol/examples/pilot-study.yaml"
    )
    study_id = load_protocol(protocol_path)["study"]["id"]
    settings = Settings(
        db_path=tmp_path / "boot.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=protocol_path,
        spa_dist=tmp_path / "no-dist",
        auth="none",
    )
    with TestClient(create_app(settings)) as boot_client:
        response = boot_client.get("/projects/implicit")
    assert response.status_code == 200
    studies = {study["id"]: study for study in response.json()["studies"]}
    assert studies[study_id]["hasProtocol"] is True
    with make_session_factory(settings.db_url)() as session:
        assert session.get(ProtocolDraftRow, study_id) is None
