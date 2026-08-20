"""Live presence + study-change pushes (D6/FR-PLAT collaboration)."""

import queue
import threading

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.presence import QUEUE_MAX, Hub
from middleware.settings import Settings

from middleware import presence

STUDY = "presence-study"


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "presence.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    return TestClient(create_app(settings))


@pytest.fixture(autouse=True)
def _clean_hub():
    presence.hub._viewers.clear()
    yield
    presence.hub._viewers.clear()


def test_a_joiner_is_announced_to_everyone_already_there():
    hub = Hub()
    first = hub.subscribe(STUDY, "user-1", "Ada", "t0")
    hub.subscribe(STUDY, "user-2", "Grace", "t1")
    event, data = first.events.get_nowait()
    assert event == "presence"
    assert [v["displayName"] for v in data["viewers"]] == ["Ada", "Grace"]


def test_two_tabs_are_one_person():
    """
    A colleague in two windows is one presence — two chips would read as two colleagues.
    """
    hub = Hub()
    hub.subscribe(STUDY, "user-1", "Ada", "2026-01-01T10:00:00Z")
    hub.subscribe(STUDY, "user-1", "Ada", "2026-01-01T10:05:00Z")
    hub.subscribe(STUDY, "user-2", "Grace", "2026-01-01T10:02:00Z")

    viewers = hub.viewers(STUDY)
    assert [v["displayName"] for v in viewers] == ["Ada", "Grace"]
    assert viewers[0]["since"] == "2026-01-01T10:00:00Z"


def test_leaving_removes_the_presence():
    hub = Hub()
    viewer = hub.subscribe(STUDY, "user-1", "Ada", "t0")
    hub.unsubscribe(STUDY, viewer.viewer_id)
    assert hub.viewers(STUDY) == []
    assert STUDY not in hub._viewers


def test_publish_reaches_every_viewer_of_that_study_only():
    hub = Hub()
    here = hub.subscribe(STUDY, "user-1", "Ada", "t0")
    elsewhere = hub.subscribe("other-study", "user-2", "Grace", "t0")

    delivered = hub.publish(STUDY, "study", {"changed": "conversation"})
    assert delivered == 1
    assert here.events.get_nowait() == ("study", {"changed": "conversation"})
    assert elsewhere.events.empty()


def test_a_stalled_viewer_drops_events_instead_of_growing_memory():
    hub = Hub()
    viewer = hub.subscribe(STUDY, "user-1", "Ada", "t0")
    for _ in range(QUEUE_MAX + 10):
        hub.publish(STUDY, "study", {"changed": "conversation"})
    assert viewer.events.qsize() <= QUEUE_MAX
    assert viewer.dropped > 0


def test_publishing_never_blocks_the_writer():
    """A conversation turn must not wait on someone's browser."""
    hub = Hub()
    hub.subscribe(STUDY, "user-1", "Ada", "t0")
    for _ in range(QUEUE_MAX * 2):
        hub.publish(STUDY, "study", {"changed": "x"})

    finished = threading.Event()

    def _publish():
        hub.publish(STUDY, "study", {"changed": "y"})
        finished.set()

    thread = threading.Thread(target=_publish)
    thread.start()
    thread.join(timeout=2)
    assert finished.is_set()


@pytest.fixture()
def published(monkeypatch):
    """Record what the routes publish, without any subscriber."""
    seen: list[tuple[str, str, dict]] = []

    def _record(study_id, event, data, **kw):
        seen.append((study_id, event, data))
        return 0

    monkeypatch.setattr(presence.hub, "publish", _record)
    return seen


def test_a_new_turn_publishes_a_conversation_change(client, published):
    res = client.post(
        f"/studies/{STUDY}/conversation/turns", json={"text": "an rct please"}
    )
    assert res.status_code == 200
    changes = [d for sid, ev, d in published if sid == STUDY and ev == "study"]
    assert changes and changes[0]["changed"] == "conversation"
    assert changes[0]["turnId"] == res.json()["platformTurnId"]


def test_deciding_a_move_publishes_a_move_change(client, published):
    turn = client.post(
        f"/studies/{STUDY}/conversation/turns",
        json={"text": "over-trust in AI generated code"},
    ).json()
    if not turn["moves"]:
        pytest.skip("scripted reply proposed no moves for this input")
    move_id = turn["moves"][0]["moveId"]
    published.clear()
    res = client.post(
        f"/studies/{STUDY}/conversation/moves/{move_id}/decision",
        json={"status": "accepted", "decidedBy": "Researcher"},
    )
    assert res.status_code == 200
    changes = [d for _, ev, d in published if ev == "study"]
    assert changes and changes[0]["changed"] == "move"
    assert changes[0]["moveId"] == move_id


def test_hub_survives_a_publish_with_no_viewers():
    assert Hub().publish("nobody-here", "study", {"changed": "draft"}) == 0


def test_queue_full_is_the_only_drop_path():
    """A viewer whose queue is full is behind; nothing else discards events."""
    hub = Hub()
    viewer = hub.subscribe(STUDY, "user-1", "Ada", "t0")
    viewer.events = queue.Queue(1)
    assert hub.publish(STUDY, "study", {"changed": "a"}) == 1
    assert hub.publish(STUDY, "study", {"changed": "b"}) == 0
    assert viewer.dropped == 1
