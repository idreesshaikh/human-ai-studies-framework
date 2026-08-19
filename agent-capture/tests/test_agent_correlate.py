"""Cross-leg correlation window logic + code-evolution derivation
(FR-AGENT-3, FR-INST-17)."""

from datetime import UTC, datetime, timedelta

from agent_capture.correlate import (
    correlate_session,
    find_burst_annotations,
    find_reliance_loops,
)
from agent_capture.events import Keys
from agent_capture.evolution import compute_evolution, derive_evolution

BASE = datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC)
KEYS = Keys("P01", "ai-assisted", "S1")


def ev(offset_s, type_, payload, *, source="agent-capture", seq=0):
    return {
        "ts": (BASE + timedelta(seconds=offset_s)).isoformat(timespec="milliseconds"),
        "type": type_,
        "source": source,
        "seq": seq,
        "payload": payload,
    }


def _turn(offset, role, code_chars=0, seq=0):
    payload = {"role": role}
    if code_chars:
        payload["codeBlocks"] = [{"language": "python", "chars": code_chars}]
        payload["responseChars"] = code_chars
    return ev(offset, "agent_turn", payload, seq=seq)


# --- a canonical error -> agent -> paste-back timeline ---------------------

RELIANCE_TIMELINE = [
    ev(
        0,
        "clipboard_paste",
        {"charCount": 200, "targetFile": "x"},
        source="tern",
        seq=10,
    ),
    _turn(5, "user", seq=1),
    _turn(9, "assistant", code_chars=100, seq=2),
    ev(15, "edit_burst", {"origin": "ai", "charsAdded": 96, "charsDeleted": 0}, seq=3),
]


def test_reliance_loop_detected_in_window():
    loops = find_reliance_loops(RELIANCE_TIMELINE, window_s=120)
    assert len(loops) == 1
    loop = loops[0]
    assert loop["derived"] is True
    assert loop["durationMs"] == 15_000
    assert loop["startRef"]["seq"] == 10  # the paste
    assert loop["endRef"]["seq"] == 3  # the paste-back burst


def test_reliance_loop_not_detected_outside_window():
    late = list(RELIANCE_TIMELINE)
    late[-1] = ev(300, "edit_burst", {"origin": "ai", "charsAdded": 96})
    assert find_reliance_loops(late, window_s=120) == []


def test_burst_annotation_links_matching_size_turn():
    annotations = find_burst_annotations(RELIANCE_TIMELINE, window_s=120)
    assert len(annotations) == 1
    a = annotations[0]
    assert a["agentTurnRef"]["seq"] == 2  # the assistant code turn
    assert a["burstCharsAdded"] == 96


def test_human_origin_burst_is_not_annotated():
    events = [
        _turn(0, "assistant", code_chars=100, seq=1),
        ev(5, "edit_burst", {"origin": "human", "charsAdded": 96}, seq=2),
    ]
    assert find_burst_annotations(events) == []


def test_correlate_session_emits_derived_events():
    derived = correlate_session(RELIANCE_TIMELINE, KEYS, window_s=120)
    types = [e["type"] for e in derived]
    assert "reliance_loop" in types
    assert "edit_burst_annotation" in types
    assert all(e["source"] == "agent-derived" for e in derived)
    assert all(e["payload"]["derived"] is True for e in derived)
    # Deterministic dense seq so re-runs reconcile.
    assert [e["seq"] for e in derived] == list(range(len(derived)))


# --- code evolution (FR-INST-17) ------------------------------------------


def test_compute_evolution_loc_churn_and_persistence():
    events = [
        ev(0, "workspace_snapshot", {"insertions": 50, "deletions": 0}),
        ev(60, "workspace_snapshot", {"insertions": 30, "deletions": 20}),
        ev(10, "edit_burst", {"origin": "ai", "charsAdded": 200, "charsDeleted": 40}),
        ev(20, "edit_burst", {"origin": "human", "charsAdded": 100, "charsDeleted": 0}),
        ev(30, "git_commit", {"hash": "abc", "insertions": 10, "deletions": 0}),
    ]
    m = compute_evolution(events)
    assert m["grossLocInserted"] == 80
    assert m["grossLocDeleted"] == 20
    assert m["netLoc"] == 60
    assert m["churnLinesApprox"] == 20
    assert m["aiCharsInserted"] == 200
    assert m["totalCharsInserted"] == 300
    assert m["aiInsertionShare"] == 200 / 300
    # persistence = surviving AI chars / inserted AI chars (char-approx).
    assert m["aiPersistenceApprox"] == (200 - 40) / 200
    assert m["participantCommits"] == 1
    assert "approximation" in m


def test_derive_evolution_none_without_inputs():
    assert derive_evolution([_turn(0, "assistant", code_chars=5)], KEYS) is None
    evt = derive_evolution(
        [ev(0, "workspace_snapshot", {"insertions": 1, "deletions": 0})], KEYS
    )
    assert evt["type"] == "code_evolution"
