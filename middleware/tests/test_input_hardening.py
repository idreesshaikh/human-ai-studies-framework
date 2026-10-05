"""Input validation, honest errors and unknown-id handling on the public routes."""

import io

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.auth import Identity
from middleware.settings import Settings

from middleware import semantic_scholar

NOPE = "no-such-study"


@pytest.fixture
def strict_client(tmp_path, monkeypatch):
    """Hosted identities require an existing study; local mode supports bootstrap."""
    from middleware import auth

    monkeypatch.setattr(
        auth,
        "verifier_from_settings",
        lambda settings: (
            lambda authorization: Identity(
                sub="researcher", display_name="Researcher", mode="clerk"
            )
        ),
    )
    return TestClient(
        create_app(
            Settings(
                db_path=tmp_path / "strict.sqlite3",
                data_dir=tmp_path / "data",
                spa_dist=tmp_path / "no-dist",
                protocol_path=None,
            )
        )
    )


def _project_and_study(client: TestClient, name: str = "Alpha") -> tuple[str, str]:
    slug = client.post("/projects", json={"name": name}).json()["slug"]
    study = client.post(f"/projects/{slug}/studies", json={"name": "First"}).json()
    return slug, study["id"]


def _event(session_id: str, pid: str, cond: str, seq: int = 0) -> dict:
    return {
        "sessionId": session_id,
        "seq": seq,
        "v": 3,
        "participantId": pid,
        "condition": cond,
        "type": "session_start",
    }


def _credential(client: TestClient) -> str:
    tok = client.post(
        "/studies/pilot/enrollment/tokens", json={"count": 1, "grain": "participant"}
    ).json()[0]
    raw = tok["connectionString"].split("#", 1)[1]
    return client.post("/pair/redeem", json={"token": raw}).json()["sessionCredential"]


# 1. token count bounds


@pytest.mark.parametrize("count", [0, -1, 101, 100000])
def test_minting_rejects_counts_outside_1_to_100(client_designed, count):
    r = client_designed.post(
        "/studies/pilot/enrollment/tokens",
        json={"count": count, "grain": "participant"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "count must be between 1 and 100"
    assert client_designed.get("/studies/pilot/enrollment/tokens").json() == []


# 2. invalid bearer on ingest


def test_invalid_ingest_bearer_is_retained_with_integrity_flag(client_designed):
    r = client_designed.post(
        "/ingest/events",
        json=[_event("s9", "P01", "ai-assisted")],
        headers={"authorization": "Bearer not-a-real-credential"},
    )
    # Sensor collection must not block a session (NFR-1). Invalid credentials
    # cannot authenticate data: every retained row is explicitly flagged.
    assert r.status_code == 200
    rows = client_designed.get("/sessions/s9/events").json()
    assert len(rows) == 1
    assert "unauthenticated" in rows[0]["flags"]


def test_anonymous_ingest_still_lands(client_designed):
    r = client_designed.post(
        "/ingest/events", json=[_event("s8", "P01", "ai-assisted")]
    )
    assert r.status_code == 200
    assert r.json()["inserted"] == 1


# 3. a credentialed session is visible without a separate start call


def test_credentialed_ingest_opens_the_session_for_its_study(client_designed):
    cred = _credential(client_designed)
    r = client_designed.post(
        "/ingest/events",
        json=[_event("fresh-session", "P01", "ai-assisted")],
        headers={"authorization": f"Bearer {cred}"},
    )
    assert r.status_code == 200
    listed = client_designed.get("/studies/pilot/sessions").json()
    assert "fresh-session" in [x["sessionId"] for x in listed]
    dataset = client_designed.get("/studies/pilot/dataset").json()["rows"]
    assert any(row["sessionId"] == "fresh-session" for row in dataset)


# 4. conversation turns


def test_blank_turn_is_rejected(client_no_protocol):
    _, study = _project_and_study(client_no_protocol)
    for text in ["", "   \n"]:
        r = client_no_protocol.post(
            f"/studies/{study}/conversation/turns", json={"text": text}
        )
        assert r.status_code == 422
    turns = client_no_protocol.get(f"/studies/{study}/conversation").json()
    assert "turns" not in turns or turns["turns"] == []


def test_turn_for_a_study_that_does_not_exist_is_404(strict_client):
    r = strict_client.post(
        f"/studies/{NOPE}/conversation/turns", json={"text": "hello there"}
    )
    assert r.status_code == 404
    r = strict_client.post(
        f"/studies/{NOPE}/conversation/turns/stream", json={"text": "hello there"}
    )
    assert r.status_code == 404


# 5. name lengths


def test_project_name_is_capped_at_80(client_no_protocol):
    r = client_no_protocol.post("/projects", json={"name": "x" * 81})
    assert r.status_code == 400
    assert "80" in r.json()["detail"]
    assert (
        client_no_protocol.post("/projects", json={"name": "x" * 80}).status_code == 200
    )


def test_renaming_a_project_is_capped_too(client_no_protocol):
    slug, _ = _project_and_study(client_no_protocol)
    r = client_no_protocol.patch(f"/projects/{slug}", json={"name": "y" * 100000})
    assert r.status_code == 400


def test_study_name_is_capped(client_no_protocol):
    slug, _ = _project_and_study(client_no_protocol)
    r = client_no_protocol.post(f"/projects/{slug}/studies", json={"name": "z" * 500})
    assert r.status_code == 400
    assert "120" in r.json()["detail"]


def test_project_slug_is_capped(client_no_protocol):
    r = client_no_protocol.post("/projects", json={"name": "ok", "slug": "s" * 60})
    assert r.status_code == 400


# 6. invitations


def test_invitation_email_must_look_like_an_email(client_no_protocol):
    slug, _ = _project_and_study(client_no_protocol)
    r = client_no_protocol.post(
        f"/projects/{slug}/invitations", json={"role": "member", "email": "notanemail"}
    )
    assert r.status_code == 400
    assert "email" in r.json()["detail"].lower()
    ok = client_no_protocol.post(
        f"/projects/{slug}/invitations",
        json={"role": "member", "email": "a@example.org"},
    )
    assert ok.status_code == 200
    assert "email" not in ok.json()


def test_bad_role_message_is_plain_words(client_no_protocol):
    slug, _ = _project_and_study(client_no_protocol)
    r = client_no_protocol.post(f"/projects/{slug}/invitations", json={"role": "god"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "[" not in detail and "'" not in detail
    assert "member" in detail and "owner" in detail


# 7. templates


def test_unknown_template_is_404_without_a_filesystem_path(client_no_protocol):
    r = client_no_protocol.post("/templates/nope-template/instantiate", json={})
    assert r.status_code == 404
    assert r.json()["detail"] == "template not found"
    plan = client_no_protocol.get("/templates/nope-template/plan")
    assert plan.status_code == 404
    assert "/" not in plan.json()["detail"]


# 8. unknown studies


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", f"/studies/{NOPE}/dataset", None),
        ("get", f"/studies/{NOPE}/power", None),
        ("get", f"/studies/{NOPE}/enrollment/tokens", None),
        ("post", f"/studies/{NOPE}/enrollment/tokens", {"count": 1}),
        ("post", f"/studies/{NOPE}/sessions/start", {"sessionId": "ghost"}),
    ],
)
def test_unknown_study_is_404(strict_client, method, path, body):
    _, study = _project_and_study(strict_client)
    r = getattr(strict_client, method)(path, **({"json": body} if body else {}))
    assert r.status_code == 404, r.text
    sessions = strict_client.get(f"/studies/{study}/sessions").json()
    assert "ghost" not in [x["sessionId"] for x in sessions]


def test_known_study_still_works(client_no_protocol):
    _, study = _project_and_study(client_no_protocol)
    assert client_no_protocol.get(f"/studies/{study}/dataset").status_code == 200
    assert client_no_protocol.get(f"/studies/{study}/power").status_code == 200
    started = client_no_protocol.post(
        f"/studies/{study}/sessions/start", json={"sessionId": "real"}
    )
    assert started.status_code == 200


# 9. paper upload


def test_upload_rejects_a_file_that_is_not_a_pdf(client_no_protocol):
    _, study = _project_and_study(client_no_protocol)
    r = client_no_protocol.post(
        f"/studies/{study}/papers/upload",
        files={"file": ("README.md", io.BytesIO(b"# not a pdf"), "text/markdown")},
    )
    assert r.status_code == 415
    assert "PDF" in r.json()["detail"]
    assert client_no_protocol.get(f"/studies/{study}/papers").json() == []


# 10. paper lookup errors


def _missing(url):
    raise semantic_scholar.SemanticScholarError(f"GET {url} -> HTTP 404", status=404)


def _outage(url):
    raise semantic_scholar.SemanticScholarError(f"GET {url} failed: timed out")


def test_unknown_arxiv_id_is_404_in_plain_words(client_no_protocol, monkeypatch):
    _, study = _project_and_study(client_no_protocol)
    monkeypatch.setattr(semantic_scholar, "get_json", _missing)
    r = client_no_protocol.post(
        f"/studies/{study}/papers", json={"arxivId": "0000.0000"}
    )
    assert r.status_code == 404
    assert (
        r.json()["detail"] == "We couldn't find that paper. Check the arXiv id or DOI."
    )


def test_upstream_outage_is_502_without_urls(client_no_protocol, monkeypatch):
    _, study = _project_and_study(client_no_protocol)
    monkeypatch.setattr(semantic_scholar, "get_json", _outage)
    r = client_no_protocol.post(f"/studies/{study}/papers", json={"doi": "10.1/x"})
    assert r.status_code == 502
    detail = r.json()["detail"]
    assert detail == "Paper lookup is unavailable right now. Try again later."
    assert "http" not in detail.lower()


# Public API compatibility: these are still supported. Setup calls quick-protocol,
# while self-hosted integrations consume the schema, corpus and artifact routes.


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("get", "/papers/index", 200),
        ("get", "/schemas/template", 200),
        ("get", "/files", 200),
        ("get", "/corpus/status", 200),
        ("post", "/studies/pilot/quick-protocol", 422),
    ],
)
def test_supported_routes_remain_available(client_no_protocol, method, path, expected):
    r = getattr(client_no_protocol, method)(path)
    assert r.status_code == expected
