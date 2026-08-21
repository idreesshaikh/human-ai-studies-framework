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
    from middleware import assistant

    double = model_double.plausible()
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr(assistant, "_post_json", double.post)
    monkeypatch.setattr(
        assistant.MistralProvider, "__init__", _provider_init(double.post)
    )


def _provider_init(default_post):
    """A ``MistralProvider.__init__`` whose default transport is the double."""

    def __init__(self, api_key, model=None, post=None, stream=None):
        from middleware import assistant

        assistant._ChatCompletionsProvider.__init__(
            self,
            "https://api.mistral.ai/v1/chat/completions",
            api_key,
            model or assistant.MISTRAL_MODEL,
            post or default_post,
            stream or assistant._post_stream,
        )

    return __init__

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
    _ask(client, _STUDY_SKETCH, study)
    reply = _ask(client, (
        "what design and statistics should I use? I was thinking "
        "within-subjects, with each developer doing both conditions "
        "counterbalanced"
    ), study)
    template_moves = [m for m in reply["moves"] if m["kind"] == "choose-template"]
    assert template_moves, "no design was proposed after describing the study"
    for m in template_moves:
        _accept(client, m["moveId"], study)
    result = _compile(client, study)
    assert result["valid"], result["errors"]
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
