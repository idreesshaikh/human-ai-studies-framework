"""Shared fixtures for enrollment-route tests."""

import model_double
import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

STUDY = "pilot"


@pytest.fixture(autouse=True)
def _model(monkeypatch):
    """Give every middleware test a language model."""
    monkeypatch.setenv("MIDDLEWARE_API_ONLY", "1")
    from middleware import assistant

    double = model_double.plausible()
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(assistant, "_post_json", double.post)


@pytest.fixture(autouse=True, scope="session")
def _offline_literature():
    """No test reaches Semantic Scholar. Live search runs on background threads
    that can outlive a test's stubs, so it is switched off for the whole run;
    tests of live search switch it back on around their own stubs."""
    import os

    before = os.environ.get("MIDDLEWARE_LIVE_SEARCH")
    os.environ["MIDDLEWARE_LIVE_SEARCH"] = "0"
    yield
    if before is None:
        os.environ.pop("MIDDLEWARE_LIVE_SEARCH", None)
    else:
        os.environ["MIDDLEWARE_LIVE_SEARCH"] = before


_STUDY_SKETCH = (
    "I want to see whether developers finish maintenance tasks faster with "
    "an AI assistant than without one, in 45-minute lab sessions, "
    "measuring task completion time and correctness."
)


def _build_client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    tc = TestClient(create_app(settings))
    tc.db_path = settings.db_path
    return tc


def _ask(client, text, study=STUDY):
    r = client.post(f"/studies/{study}/conversation/turns", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def _accept(client, move_id, study=STUDY, status="accepted"):
    r = client.post(
        f"/studies/{study}/conversation/moves/{move_id}/decision",
        json={"status": status, "decidedBy": "Owner"},
    )
    assert r.status_code == 200, r.text


def _compile(client, study=STUDY):
    r = client.post(f"/studies/{study}/conversation/compile", json={})
    assert r.status_code == 200, r.text
    return r.json()


def _approve(client, comp_id, study=STUDY, rationale=""):
    return client.post(
        f"/studies/{study}/conversation/approve",
        json={"compilationId": comp_id, "approvedBy": "Owner", "rationale": rationale},
    )


def _reach_approved_protocol(client, study=STUDY):
    """
    Drive an empty study to an approved, validating protocol draft - the state a
    researcher reaches by designing, and the only pre-condition enrollment now has.
    """
    reply = _ask(client, _STUDY_SKETCH, study)
    assert reply["moves"], "no plan was proposed after describing the study"
    for m in reply["moves"]:
        _accept(client, m["moveId"], study)
    result = _compile(client, study)
    assert result["valid"], (result["errors"], result["unresolved"])
    r = _approve(client, result["compilationId"], study)
    assert r.status_code == 200, r.text
    return result


@pytest.fixture()
def client_no_protocol(tmp_path) -> TestClient:
    return _build_client(tmp_path)


@pytest.fixture()
def client_designed(tmp_path) -> TestClient:
    """Designed and compiled, nothing more - the state setup starts from."""
    tc = _build_client(tmp_path)
    _reach_approved_protocol(tc)
    return tc


@pytest.fixture(autouse=True)
def _api_only_planner_tests(monkeypatch):
    """API test fixtures deliberately have no compiled frontend."""
    monkeypatch.setenv("MIDDLEWARE_API_ONLY", "1")
