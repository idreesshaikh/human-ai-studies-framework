import copy
import json

import pytest
import yaml
from middleware.replay import replay_frames
from sqlalchemy.orm import Session

from middleware import db


def event(**changes):
    return {
        "ts": "2026-10-05T10:00:00Z",
        "source": "tern",
        "seq": 1,
        "type": "workspace_snapshot",
        "flags": [],
        "payload": {},
        **changes,
    }


def test_replay_order_is_stable_across_producers_and_timezones():
    rows = [
        event(source="z"),
        event(source="a"),
        event(ts="2026-10-05T10:30:00+01:00"),
        event(ts="invalid"),
    ]
    first = replay_frames(rows)
    assert first == replay_frames(list(reversed(rows)))
    assert first[0]["ts"] == "2026-10-05T10:30:00+01:00"
    assert [r["source"] for r in first[1:3]] == ["a", "z"]
    assert first[-1]["ts"] == "invalid"


def test_replay_does_not_reconstruct_or_leak_uncaptured_code():
    row = event(
        payload={
            "diff": "private fixture",
            "codeCaptureEnabled": True,
            "insertions": 3,
            "conversation": "not replay content",
        }
    )
    assert replay_frames([row])[0]["diff"] is None
    assert "conversation" not in json.dumps(replay_frames([row], raw_code=True))
    assert replay_frames([row], raw_code=True)[0]["diff"] == "private fixture"
    row["payload"]["diff"] = "x" * 64_001
    assert replay_frames([row], raw_code=True)[0]["diff"] is None


@pytest.mark.parametrize("enabled", [False, True])
def test_replay_and_exports_respect_study_capture_policy(client_designed, enabled):
    client = client_designed
    document = copy.deepcopy(client.get("/studies/pilot/protocol").json()["document"])
    document.setdefault("capture", {}).setdefault("privacy", {})["rawCode"] = enabled
    with Session(db._engine) as session:
        draft = session.get(db.ProtocolDraftRow, "pilot")
        draft.yaml = yaml.safe_dump(document)
        session.add(
            db.SessionBlock(
                session_id="replay-fixture", study_id="pilot", participant_id="fixture"
            )
        )
        session.commit()
    response = client.post(
        "/ingest/events",
        json=[
            {
                "v": 4,
                "ts": "2026-10-05T10:00:00Z",
                "mono": 0,
                "seq": 1,
                "sessionId": "replay-fixture",
                "participantId": "fixture",
                "condition": "ai-assisted",
                "source": "workspace-snapshot",
                "type": "workspace_snapshot",
                "payload": {"codeCaptureEnabled": True, "diff": "+ synthetic code"},
            }
        ],
    )
    assert response.status_code == 200
    replay = client.get("/studies/pilot/sessions/replay-fixture/replay")
    assert replay.status_code == 200
    assert replay.json()["frames"][0]["diff"] == (
        "+ synthetic code" if enabled else None
    )
    assert client.get("/studies/wrong/sessions/replay-fixture/replay").status_code in {
        403,
        404,
    }
    # Generic event reads never expose raw diffs; use the policy-gated replay.
    assert (
        "diff" not in client.get("/sessions/replay-fixture/events").json()[0]["payload"]
    )
    dataset = client.get("/studies/pilot/dataset").json()
    assert ("+ synthetic code" in json.dumps(dataset)) is enabled
