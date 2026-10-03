"""Tasks end to end: designed → assigned → captured → attributable."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

STUDY = "tasks-study"

_SKETCH = (
    "I want to know whether an AI assistant changes how carefully developers "
    "review code, with 12 professional developers in 45-minute sessions."
)


@pytest.fixture()
def client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "tasks.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    return TestClient(create_app(settings))


def _ask(client, text):
    r = client.post(f"/studies/{STUDY}/conversation/turns", json={"text": text})
    assert r.status_code == 200, r.text
    return r.json()


def _accept_all(client, reply):
    for move in reply["moves"]:
        r = client.post(
            f"/studies/{STUDY}/conversation/moves/{move['moveId']}/decision",
            json={"status": "accepted", "decidedBy": "Owner"},
        )
        assert r.status_code == 200, r.text


def _designed_study(client) -> dict:
    """Drive a real conversation to an approved protocol with two tasks."""
    _accept_all(client, _ask(client, _SKETCH))
    _accept_all(
        client,
        _ask(
            client,
            "what design and statistics should I use? I was thinking "
            "within-subjects, with each developer doing both conditions "
            "counterbalanced",
        ),
    )
    result = client.post(
        f"/studies/{STUDY}/conversation/compile", json={}
    ).json()
    assert result["valid"], (result["errors"], result["unresolved"])
    r = client.post(
        f"/studies/{STUDY}/conversation/approve",
        json={"compilationId": result["compilationId"], "approvedBy": "Owner"},
    )
    assert r.status_code == 200, r.text
    return result


def _pair(client, token: str) -> dict:
    r = client.post("/pair/redeem", json={"token": token})
    assert r.status_code == 200, r.text
    return r.json()


def _mint(client, count: int = 2) -> list[dict]:
    r = client.post(
        f"/studies/{STUDY}/enrollment/tokens",
        json={"count": count, "grain": "participant"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _capture_config(client, credential: str, session_id: str) -> dict:
    r = client.get(
        f"/studies/{STUDY}/capture-config",
        params={"sessionId": session_id},
        headers={"authorization": f"Bearer {credential}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_a_session_is_assigned_a_task_and_the_editor_receives_it(client):
    _designed_study(client)
    token = _mint(client, 1)[0]
    redeemed = _pair(client, token["connectionString"].rsplit("#", 1)[1])
    assert redeemed["captureConfig"]["block"]["taskId"]
    cred = redeemed[
        "sessionCredential"
    ]

    config = _capture_config(client, cred, "s-1")
    block = config["block"]
    assert block["taskId"], "a session must know what work it is for"
    assert block["condition"]
    assert block["of"] >= 1

    settings = config["settings"]
    assert settings["tern.session.taskId"] == block["taskId"]
    assert settings["tern.condition"] == block["condition"]


def test_events_come_back_attributable_to_the_task(client):
    """The point of the whole chain: the data can answer "which task?"."""
    _designed_study(client)
    token = _mint(client, 1)[0]
    redeemed = _pair(client, token["connectionString"].rsplit("#", 1)[1])
    cred = redeemed["sessionCredential"]
    block = _capture_config(client, cred, "s-1")["block"]

    r = client.post(
        "/ingest/events",
        json={
            "source": "tern",
            "events": [
                {
                    "sessionId": "s-1",
                    "seq": 0,
                    "participantId": redeemed["participantId"],
                    "condition": block["condition"],
                    "v": 4,
                    "ts": "2026-08-18T10:00:00Z",
                    "mono": 0.0,
                    "type": "session_start",
                    "payload": {},
                }
            ],
        },
        headers={"authorization": f"Bearer {cred}"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 1

    events = client.get("/sessions/s-1/events").json()
    assert events[0]["taskId"] == block["taskId"]


def test_re_pulling_a_running_session_returns_the_same_block(client):
    """
    The editor re-pulls its config at every session start, and a resumed session pulls
    again.
    """
    _designed_study(client)
    token = _mint(client, 1)[0]
    cred = _pair(client, token["connectionString"].rsplit("#", 1)[1])[
        "sessionCredential"
    ]

    first = _capture_config(client, cred, "s-1")["block"]
    again = _capture_config(client, cred, "s-1")["block"]
    assert first == again


def test_the_next_session_advances_to_the_next_block(client):
    """
    A within-subjects participant's second session is their second block  -  a different
    condition, so they are their own comparison.
    """
    _designed_study(client)
    token = _mint(client, 1)[0]
    cred = _pair(client, token["connectionString"].rsplit("#", 1)[1])[
        "sessionCredential"
    ]

    first = _capture_config(client, cred, "s-1")["block"]
    second = _capture_config(client, cred, "s-2")["block"]
    assert second["index"] == first["index"] + 1
    assert second["condition"] != first["condition"], (
        "a within-subjects participant must meet both conditions"
    )


def test_two_participants_meet_the_conditions_in_opposite_orders(client):
    """
    Counterbalancing, observable from outside: whatever comes second benefits from
    practice, so the order has to alternate.
    """
    _designed_study(client)
    tokens = _mint(client, 2)
    firsts = []
    for i, token in enumerate(tokens):
        cred = _pair(client, token["connectionString"].rsplit("#", 1)[1])[
            "sessionCredential"
        ]
        firsts.append(_capture_config(client, cred, f"p{i}-s1")["block"]["condition"])
    assert firsts[0] != firsts[1], firsts


def test_a_session_without_an_id_reports_a_block_without_consuming_one(client):
    """An older extension sends no session id."""
    _designed_study(client)
    token = _mint(client, 1)[0]
    cred = _pair(client, token["connectionString"].rsplit("#", 1)[1])[
        "sessionCredential"
    ]

    r = client.get(
        f"/studies/{STUDY}/capture-config",
        headers={"authorization": f"Bearer {cred}"},
    )
    assert r.status_code == 200
    assert r.json()["block"]["index"] == 0

    assert _capture_config(client, cred, "s-1")["block"]["index"] == 0
