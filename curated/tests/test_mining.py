"""The curated-dataset leg: normalizer, adapter, heuristics, frame, threats.

All offline. These exercise the pure logic.
"""

from pathlib import Path

import pytest
from curated.contract import (
    Cursor,
    CursorCheckpoint,
    NormalizedEvent,
    SamplingFrame,
)
from curated.frame import FrameError, frame_from_protocol
from curated.heuristics import ActorSignal, classify, heuristic_records
from curated.pseudonymize import new_salt, pseudonym
from curated.threats import validate_record_doc

_FIXTURES = Path(__file__).parent / "cassettes"


def run_all(adapter, frame, cursor=None):
    """Drain a run into (events, checkpoints)."""
    events, checkpoints = [], []
    for item in adapter.run(frame, cursor):
        (checkpoints if isinstance(item, CursorCheckpoint) else events).append(item)
    return events, checkpoints


# --------------------------------------------------------------- pseudonyms


def test_pseudonym_is_deterministic_and_salted():
    salt = new_salt()
    a1 = pseudonym(salt, "Alice")
    a2 = pseudonym(salt, "alice")  # case/space-normalized
    assert a1 == a2 and a1.startswith("actor-")
    # A different salt yields a different pseudonym for the same actor.
    assert pseudonym(new_salt(), "alice") != a1
    # No raw identity survives.
    assert "alice" not in a1


# ------------------------------------------------------------- heuristics


def test_heuristics_classify_agents_and_record_versions():
    assert classify(ActorSignal(login="cursor[bot]", is_bot_flagged=True)).is_agent
    assert classify(ActorSignal(login="dana")).is_agent is False
    v = classify(ActorSignal(login="sam", coauthor_logins=("copilot",)))
    assert v.is_agent and v.fired == ["coauthor-trailer@1"]
    recs = heuristic_records({"coauthor-trailer@1"})
    assert recs and recs[0]["cite"] == "mining-coding-agent-activity"
    assert recs[0]["knownFailureModes"]


# ----------------------------------------------------------------- frame


def test_frame_refuses_without_curated_section():
    with pytest.raises(FrameError, match="no `curated:` section"):
        frame_from_protocol({"conditions": []})


def test_frame_parses_curated_section():
    proto = {
        "curated": {
            "actorUnit": "developer",
            "contentPolicy": "metadata-only",
            "conditions": ["agent-pr", "human-pr"],
            "samplingFrame": {
                "query": "repo:example/app is:merged",
                "window": {"start": "2025-01-01", "end": "2025-06-30"},
                "exclusions": ["draft"],
                "targetN": 6,
            },
        }
    }
    frame = frame_from_protocol(proto)
    assert frame.query.startswith("repo:example/app")
    assert frame.target_n == 6 and frame.exclusions == ["draft"]


# ---------------------------------------------------------------------------
# Archive adapter (FR-CUR-4)
# ---------------------------------------------------------------------------


def test_archive_adapter_produces_join_keyed_events():
    from curated.archive_adapter import ArchiveAdapter

    path = _FIXTURES / "archive-demo.json"
    adapter = ArchiveAdapter(path=path, salt="test-salt")
    frame = SamplingFrame(
        query=str(path),
        window_start="2025-01-01",
        window_end="2025-06-30",
        conditions=["default"],
        actor_unit="developer",
    )
    events, checkpoints = run_all(adapter, frame)
    assert len(events) >= 1
    assert len(checkpoints) >= 1
    for e in events:
        assert isinstance(e, NormalizedEvent)
        assert e.session_id
        assert e.participant_id.startswith("actor-")
        assert e.condition
        assert e.source == "archive"
        assert e.schema_version == 5
        assert e.payload
        assert "rawType" in e.payload
    assert [e.seq for e in events] == list(range(len(events)))


def test_archive_adapter_plan_reports_coverage():
    from curated.archive_adapter import ArchiveAdapter

    path = _FIXTURES / "archive-demo.json"
    adapter = ArchiveAdapter(path=path, salt="test-salt")
    frame = SamplingFrame(
        query=str(path),
        window_start="2025-01-01",
        window_end="2025-06-30",
        conditions=["default"],
        actor_unit="developer",
    )
    estimate = adapter.plan(frame)
    assert estimate.requested == 4
    assert "records in archive" in estimate.note


def test_archive_adapter_is_registered():
    from curated.registry import ADAPTERS, get_adapter

    assert "archive" in ADAPTERS
    adapter = get_adapter("archive", path="/dev/null", salt="x")
    from curated.archive_adapter import ArchiveAdapter

    assert isinstance(adapter, ArchiveAdapter)


def test_archive_adapter_produces_deterministic_events():
    from curated.archive_adapter import ArchiveAdapter

    path = _FIXTURES / "archive-demo.json"
    a1 = ArchiveAdapter(path=path, salt="test-salt")
    a2 = ArchiveAdapter(path=path, salt="test-salt")
    frame = SamplingFrame(
        query=str(path),
        window_start="2025-01-01",
        window_end="2025-06-30",
        conditions=["default"],
        actor_unit="developer",
    )
    e1, _ = run_all(a1, frame)
    e2, _ = run_all(a2, frame)
    assert len(e1) == len(e2)
    for ev1, ev2 in zip(e1, e2, strict=True):
        assert ev1.seq == ev2.seq
        assert ev1.participant_id == ev2.participant_id
        assert ev1.type == ev2.type


def test_archive_adapter_events_respect_content_free_contract():
    from curated.archive_adapter import ArchiveAdapter

    path = _FIXTURES / "archive-demo.json"
    adapter = ArchiveAdapter(path=path, salt="test-salt")
    frame = SamplingFrame(
        query=str(path),
        window_start="2025-01-01",
        window_end="2025-06-30",
        conditions=["default"],
        actor_unit="developer",
    )
    events, _ = run_all(adapter, frame)
    for e in events:
        assert "rawAuthor" not in e.payload
        assert "rawType" in e.payload


def test_archive_adapter_resume_from_cursor():
    from curated.archive_adapter import ArchiveAdapter

    path = _FIXTURES / "archive-demo.json"
    adapter = ArchiveAdapter(path=path, salt="test-salt")
    frame = SamplingFrame(
        query=str(path),
        window_start="2025-01-01",
        window_end="2025-06-30",
        conditions=["default"],
        actor_unit="developer",
    )
    full_events, _ = run_all(adapter, frame)

    # Resume from cursor skipping the first 2 events
    adapter2 = ArchiveAdapter(path=path, salt="test-salt")
    cursor = Cursor({"skip": 2, "seen": 2})
    events, _ = run_all(adapter2, frame, cursor=cursor)
    assert len(events) == len(full_events) - 2
    for ev, fev in zip(events, full_events[2:], strict=True):
        assert ev.seq == fev.seq
        assert ev.participant_id == fev.participant_id


def test_threats_record_rejects_unmitigated_bias():
    doc = {
        "samplingFrame": {"query": "x"},
        "biases": [{"description": "b", "direction": "up"}],
        "coverage": {"requested": 1, "retrieved": 1, "dropped": {}},
    }
    problems = validate_record_doc(doc)
    assert any("mitigation" in p for p in problems)
