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
        return Identity(sub=sub, display_name=sub, mode="token")

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

    def flags() -> dict[str, bool]:
        res = client.get(f"/projects/{slug}", headers=bearer("alice"))
        assert res.status_code == 200, res.text
        return {s["id"]: s["hasProtocol"] for s in res.json()["studies"]}

    # A starting protocol is a draft until it is applied.
    assert flags() == {bare: False, full: False}
    import yaml
    from middleware.db import ProtocolDraftRow, make_session_factory

    with make_session_factory(f"sqlite:///{client.db_path}")() as s:
        s.add(
            ProtocolDraftRow(
                study_id=full,
                yaml=yaml.safe_dump(MINIMAL_PROTOCOL),
                compilation_id="",
                updated_at="",
            )
        )
        s.commit()
    assert flags() == {bare: False, full: True}


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


def test_a_study_keeps_the_name_it_was_given(client):
    slug = client.post(
        "/projects", json={"name": "Lab"}, headers=bearer("alice")
    ).json()["slug"]
    made = client.post(
        f"/projects/{slug}/studies",
        json={"name": "ZZ Audit: Copilot (pilot)"},
        headers=bearer("alice"),
    ).json()["id"]
    listed = client.get("/studies", headers=bearer("alice")).json()
    assert next(st for st in listed if st["id"] == made)["name"] == (
        "ZZ Audit: Copilot (pilot)"
    )
    summary = client.get(f"/studies/{made}/summary", headers=bearer("alice")).json()
    assert summary["name"] == "ZZ Audit: Copilot (pilot)"
