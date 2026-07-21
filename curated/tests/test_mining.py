"""The curated-dataset leg: normalizer, adapter, heuristics, frame, threats.

All offline (cassette). These exercise the pure logic; the middleware job
runner + endpoints are tested in ``middleware/tests/test_curated.py``.
"""

from pathlib import Path

import pytest
from curated.cassette import Cassette, RateLimited, request_key
from curated.contract import (
    CURATED_SCHEMA_VERSION,
    Cursor,
    CursorCheckpoint,
    NormalizedEvent,
    SamplingFrame,
)
from curated.frame import FrameError, frame_from_protocol
from curated.github_adapter import GitHubAdapter
from curated.heuristics import ActorSignal, classify, heuristic_records
from curated.pseudonymize import new_salt, pseudonym
from curated.threats import build_record, validate_record_doc

CASSETTE = (
    Path(__file__).resolve().parents[1]
    / "src/curated/cassettes/cursor-mining-demo.json"
)
_FIXTURES = Path(__file__).parent / "cassettes"

FRAME = SamplingFrame(
    query="repo:example/app is:merged",
    window_start="2025-01-01",
    window_end="2025-06-30",
    exclusions=["draft"],
    conditions=["agent-pr", "human-pr"],
    actor_unit="developer",
)


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


# ------------------------------------------------------- adapter + cassette


def test_cassette_key_matches_adapter_query():
    # The demo cassette is keyed on the exact query the adapter builds.
    key = request_key(
        "GET",
        "/search/issues",
        {
            "q": "repo:example/app is:merged type:pr created:2025-01-01..2025-06-30",
            "page": 1,
        },
    )
    assert Cassette.load(CASSETTE).get.__self__  # cassette loads
    # The adapter's plan must find a total_count via that key.
    adapter = GitHubAdapter(Cassette.load(CASSETTE), salt=new_salt())
    assert adapter.plan(FRAME).requested >= 1
    assert key.startswith("GET /search/issues?")


def test_adapter_mines_events_content_free():
    adapter = GitHubAdapter(Cassette.load(CASSETTE), salt=new_salt())
    events, checkpoints = run_all(adapter, FRAME)
    assert events and checkpoints
    types = {e.type for e in events}
    assert {"mined_pull_request", "mined_commit", "mined_review"} <= types
    # Every event is schema v5 and content-free (no raw login/message/code).
    for e in events:
        assert e.schema_version == CURATED_SCHEMA_VERSION
        assert isinstance(e, NormalizedEvent)
        blob = repr(e.payload).lower()
        for raw in ("dana", "sam", "cursor[bot]", "devin-ai"):
            assert raw not in blob
        assert e.participant_id.startswith(("actor-", "repo-"))


def test_agent_and_human_prs_land_in_declared_arms():
    adapter = GitHubAdapter(Cassette.load(CASSETTE), salt=new_salt())
    events, _ = run_all(adapter, FRAME)
    prs = {e.session_id: e.condition for e in events if e.type == "mined_pull_request"}
    # PR 101 (cursor[bot]) is agent; PR 102 (dana) is human.
    assert prs["pr-example/app-101"] == "agent-pr"
    assert prs["pr-example/app-102"] == "human-pr"


def test_exclusions_drop_candidates():
    adapter = GitHubAdapter(Cassette.load(CASSETTE), salt=new_salt())
    events, _ = run_all(adapter, FRAME)
    # PR 105 is flagged "draft" and is excluded → no events for it.
    assert not any(e.session_id == "pr-example/app-105" for e in events)
    assert adapter.dropped.counts.get("excluded-by-inclusion-rule", 0) >= 1


def test_remining_is_idempotent_same_keys():
    salt = new_salt()
    a = GitHubAdapter(Cassette.load(CASSETTE), salt=salt)
    b = GitHubAdapter(Cassette.load(CASSETTE), salt=salt)
    ea, _ = run_all(a, FRAME)
    eb, _ = run_all(b, FRAME)
    keys_a = [(e.session_id, e.source, e.seq) for e in ea]
    keys_b = [(e.session_id, e.source, e.seq) for e in eb]
    # Same idempotency keys, in the same order — replay drops duplicates.
    assert keys_a == keys_b
    assert len(keys_a) == len(set(keys_a))  # unique within the run


def test_resume_from_checkpoint_no_duplicate_prs():
    # Mine the first checkpoint, then resume from its cursor; the union of
    # PRs must equal a full run with no duplicates (F2.1).
    salt = new_salt()
    full, _ = run_all(GitHubAdapter(Cassette.load(CASSETTE), salt=salt), FRAME)
    full_prs = [e.session_id for e in full if e.type == "mined_pull_request"]

    a = GitHubAdapter(Cassette.load(CASSETTE), salt=salt)
    first_events, first_ckpts = [], []
    for item in a.run(FRAME, None):
        if isinstance(item, CursorCheckpoint):
            first_ckpts.append(item)
            break
        first_events.append(item)
    resume_cursor = first_ckpts[0].cursor
    partial_prs = [e.session_id for e in first_events if e.type == "mined_pull_request"]

    b = GitHubAdapter(Cassette.load(CASSETTE), salt=salt)
    resumed, _ = run_all(b, FRAME, resume_cursor)
    resumed_prs = [e.session_id for e in resumed if e.type == "mined_pull_request"]

    union = partial_prs + resumed_prs
    assert set(union) == set(full_prs)
    assert len(union) == len(set(union))  # no PR mined twice across the resume


def test_actor_snapshot_is_once_per_actor():
    adapter = GitHubAdapter(Cassette.load(CASSETTE), salt=new_salt())
    events, _ = run_all(adapter, FRAME)
    snaps = [e for e in events if e.type == "mined_actor_snapshot"]
    pids = [e.participant_id for e in snaps]
    assert len(pids) == len(set(pids))  # one snapshot per distinct actor


# ------------------------------------------------------------- rate limit


def test_cassette_rate_limit_fires_then_recovers():
    cas = Cassette.load(CASSETTE)
    with pytest.raises(RateLimited) as exc:
        cas.get("GET", "/rate/limited")
    assert exc.value.retry_after == 1
    # onlyFirst=1 → the retry succeeds.
    assert cas.get("GET", "/rate/limited") == {"message": "API rate limit exceeded"}


# ---------------------------------------------------------------- threats


def test_threats_record_generated_and_valid():
    adapter = GitHubAdapter(Cassette.load(CASSETTE), salt=new_salt())
    events, _ = run_all(adapter, FRAME)
    rec = build_record(
        FRAME,
        fired_heuristic_ids=adapter.fired_heuristics,
        requested=6,
        retrieved=adapter.retrieved,
        dropped=adapter.dropped.counts,
    )
    doc = rec.to_doc()
    assert validate_record_doc(doc) == []
    assert doc["heuristics"]  # heuristics that fired are named
    assert doc["coverage"]["dropped"].get("excluded-by-inclusion-rule", 0) >= 1
    assert doc["samplingFrame"]["actorUnitWindowing"]
    assert events  # sanity


# ---------------------------------------------------------------------------
# Slice B — Archive adapter (FR-CUR-4)
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
