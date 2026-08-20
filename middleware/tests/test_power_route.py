"""The power/sensitivity route (P2-2): /studies/{study_id}/power."""

from __future__ import annotations

from datetime import UTC, datetime

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
    return TestClient(create_app(settings, clock=lambda: FROZEN_NOW))


def bearer(sub: str) -> dict:
    return {"Authorization": f"Bearer {sub}"}


def make_study(client: TestClient, owner: str) -> str:
    made = client.post(
        "/projects",
        json={"name": f"{owner}'s lab"},
        headers=bearer(owner),
    )
    assert made.status_code == 200, made.text
    slug = made.json()["slug"]
    res = client.post(
        f"/projects/{slug}/studies",
        json={"name": "Pilot"},
        headers=bearer(owner),
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def test_power_route_shape_with_defaults(client):
    study_id = make_study(client, "alice")
    r = client.get(f"/studies/{study_id}/power", headers=bearer("alice"))
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["model"].startswith("two-sample t-test")
    assert payload["alpha"] == 0.05 and payload["powerTarget"] == 0.8
    assert [c["effectSize"] for c in payload["curves"]] == [0.2, 0.5, 0.8]
    points = payload["curves"][2]["points"]
    assert [p["power"] for p in points] == sorted(p["power"] for p in points)
    by_size = {e["effectSize"]: e for e in payload["requiredN"]}
    assert by_size[0.8]["reachesTarget"] and by_size[0.8]["nPerGroup"] == 26
    assert not by_size[0.2]["reachesTarget"] and not by_size[0.5]["reachesTarget"]


def test_power_route_honors_query_parameters(client):
    study_id = make_study(client, "alice")
    r = client.get(
        f"/studies/{study_id}/power?alpha=0.01&maxN=200&powerTarget=0.9&effectSizes=0.5,0.8",
        headers=bearer("alice"),
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["alpha"] == 0.01 and payload["powerTarget"] == 0.9
    assert payload["maxTotalN"] == 200
    assert [c["effectSize"] for c in payload["curves"]] == [0.5, 0.8]


def test_power_route_rejects_bad_parameters_as_422(client):
    study_id = make_study(client, "alice")
    for query in (
        "alpha=1.5",
        "alpha=0",
        "powerTarget=0",
        "maxN=2",
        "effectSizes=abc",
        "effectSizes=0.2,-1",
    ):
        r = client.get(f"/studies/{study_id}/power?{query}", headers=bearer("alice"))
        assert r.status_code == 422, f"{query}: {r.text}"


def test_power_route_requires_credentials_and_membership(client):
    study_id = make_study(client, "alice")
    assert client.get(f"/studies/{study_id}/power").status_code == 401
    # A non-member of the project cannot read it either.
    assert (
        client.get(f"/studies/{study_id}/power", headers=bearer("bob")).status_code
        == 403
    )


def test_power_route_404s_for_unknown_study(client):
    assert (
        client.get("/studies/no-such-study/power", headers=bearer("alice")).status_code
        == 404
    )


def test_power_route_works_without_a_compiled_protocol(client):
    """
    Recruitment planning happens while the design is still in conversation — the route
    must not demand a compiled protocol.
    """
    study_id = make_study(client, "alice")
    r = client.get(f"/studies/{study_id}/power", headers=bearer("alice"))
    assert r.status_code == 200
