"""Shared fixtures for enrollment-route tests.

Three ``TestClient`` fixtures, all driven through the real flow — never a
fabricated shortcut:

- ``client_no_protocol``: a bare app. Nothing has been designed, so there is
  no protocol to enroll against and mint must 404.
- ``client_designed``: the ``pilot`` study taken through a real design
  conversation (chooses the METR within-subjects template, whose default
  ``conditions`` are exactly ``[ai-assisted, unassisted]`` —
  ``templates/registry/metr-rct-v1.yaml``) and approved. **Nothing else.**
  This is the state a researcher is actually in when they want to set the
  study up, and every enrollment route has to work from here.
- ``client_ethics_ok``: ``client_designed`` plus a recorded ethics approval,
  which no longer gates anything but does snapshot the approved protocol, so
  the amendment path still has a base to diff against.

Enrollment used to be gated on that recorded approval - mint, metric toggles
and ``/pair/redeem`` all refused without it, and a ``dev_mode`` flag existed
purely to switch the gate off so the flow could be tested at all. The gate
blocked the one thing this product exists to do, so it is gone; the fixture
that bypassed it went with it.

Mirrors ``test_evolution.py``'s ``client`` fixture (lines 64-89) and its
``_reach_approved_protocol`` / ``_approve_ethics`` helpers (lines 123-140)
verbatim, with the study id fixed to ``"pilot"``. Note: this ``"pilot"`` is a
study conversationally built at test time — it is *not*
``protocol/examples/pilot-study.yaml`` (whose real ``study.id`` is
``pilot-2026``; confirmed via ``grep studies/pilot-2026`` in
``test_middleware_api.py``). No ``protocol_path`` is loaded here (matching
test_evolution.py's own fixture, which also loads none), so there is no
collision between the two "pilot" names.
"""

import model_double
import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

STUDY = "pilot"


@pytest.fixture(autouse=True)
def _model(monkeypatch):
    """Give every middleware test a language model.

    The design conversation requires one - it raises ``ModelUnavailable``
    rather than answering from a keyword script - so any test that drives a
    conversation needs a model to drive it. This patches the single network
    seam (``assistant._post_json``) rather than ``make_client``, so client
    resolution, provider selection and the whole request/response path stay
    real; only the socket is replaced. A test that wants a different model,
    an outage, or no model at all just patches over this.
    """
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
    """A ``MistralProvider.__init__`` whose default transport is the double.

    The real default is bound at class-definition time (``post=_post_json``),
    so patching the module attribute alone would not reach a provider built
    inside the app under test. The signature is otherwise unchanged: a test
    passing its own ``post=`` still wins.
    """

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

#: A study described the way a researcher would, so the elicitation gate
#: (FR-CONV-10) opens honestly rather than being bypassed in tests.
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


# ---------------------------------------------------------------- helpers
# Copied from test_evolution.py, study defaulted to this file's STUDY.


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
    """Drive an empty study to an approved, validating protocol draft - the
    state a researcher reaches by designing, and the only pre-condition
    enrollment now has."""
    # The platform withholds a design shape until the study is understood
    # (FR-CONV-10), so describe the study first — the conversation this helper
    # drives is now the one a researcher would actually have.
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


def _approve_ethics(client, study=STUDY):
    r = client.post(f"/studies/{study}/ethics-approval")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- fixtures


@pytest.fixture()
def client_no_protocol(tmp_path) -> TestClient:
    return _build_client(tmp_path)


@pytest.fixture()
def client_designed(tmp_path) -> TestClient:
    """Designed and compiled, nothing more - the state setup starts from."""
    tc = _build_client(tmp_path)
    _reach_approved_protocol(tc)
    return tc


@pytest.fixture()
def client_ethics_ok(tmp_path) -> TestClient:
    tc = _build_client(tmp_path)
    _reach_approved_protocol(tc)
    _approve_ethics(tc)
    return tc
