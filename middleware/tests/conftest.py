"""Shared fixtures for enrollment-route tests (Task A4).

Two ``TestClient`` fixtures, both driven through the real gates — never a
fabricated shortcut:

- ``client_no_ethics``: a bare app; no study has ever seen an ethics-approval
  call, so mint must refuse it (409) regardless of whether a protocol draft
  exists.
- ``client_ethics_ok``: the ``pilot`` study taken through a real design
  conversation (chooses the METR within-subjects template, whose default
  ``conditions`` are exactly ``[ai-assisted, unassisted]`` —
  ``templates/registry/metr-rct-v1.yaml``), approved, then ethics-approved.

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

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

STUDY = "pilot"


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
    r = client.post(
        f"/studies/{study}/conversation/approve",
        json={"compilationId": comp_id, "approvedBy": "Owner", "rationale": rationale},
    )
    return r


def _reach_approved_protocol(client, study=STUDY):
    """Drive an empty study to an approved, validating protocol draft (the
    pre-condition every ethics-gated test starts from)."""
    reply = _ask(client, "what design and statistics should I use?", study)
    for m in reply["moves"]:
        if m["kind"] == "choose-template":
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
def client_no_ethics(tmp_path) -> TestClient:
    return _build_client(tmp_path)


@pytest.fixture()
def client_ethics_ok(tmp_path) -> TestClient:
    tc = _build_client(tmp_path)
    _reach_approved_protocol(tc)
    _approve_ethics(tc)
    return tc
