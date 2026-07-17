"""meyer-fragmentation on a constructed dataset with known answers
(FR-ANA-5 second replication, docs/archive/roadmap/09 item 3): switch counts are
hand-countable, same-file repeats must collapse, window-focus events
(no `file` payload) must be ignored."""

import analysis.recipes  # noqa: F401 - populate the registry
import pytest
from analysis.core import REGISTRY
from analysis.dataset import Dataset


def _ev(session, participant, condition, seq, minute, type_, payload):
    return {
        "source": "cognitive-overlay",
        "ts": f"2026-07-12T{10 + int(minute) // 60:02d}:{int(minute) % 60:02d}:00.000Z",
        "sessionId": session,
        "participantId": participant,
        "condition": condition,
        "type": type_,
        "seq": seq,
        "flags": [],
        "payload": payload,
    }


def _session(session, participant, condition, focus_files):
    """60-minute session; focus_files = [(minute, file-or-None)] where None
    means a window-focus event (no file payload)."""
    rows = [_ev(session, participant, condition, 0, 0, "session_start",
                {"plannedDurationMinutes": 60})]
    seq = 1
    for minute, file in focus_files:
        payload = {"state": "focused"} if file is None else {"file": file}
        rows.append(_ev(session, participant, condition, seq, minute,
                        "editor_focus", payload))
        seq += 1
    rows.append(_ev(session, participant, condition, seq, 15,
                    "fatigue_response", {"score": 2, "latencyMs": 3000}))
    rows.append(_ev(session, participant, condition, seq + 1, 60,
                    "session_end", {"reason": "completed"}))
    return rows


@pytest.fixture()
def dataset() -> Dataset:
    rows = _session(
        "S1", "P01", "ai-assisted",
        # A->B->A->C = 3 switches; the duplicate B at minute 12 collapses;
        # the None row is window focus and must not count.
        [(1, "a.py"), (10, "b.py"), (12, "b.py"), (14, None),
         (20, "a.py"), (30, "c.py")],
    ) + _session(
        "S2", "P02", "unassisted",
        # 6 switches at 5-minute spacing.
        [(1, "a.py"), (6, "b.py"), (11, "a.py"), (16, "b.py"),
         (21, "a.py"), (26, "c.py"), (31, "a.py")],
    )
    return Dataset(rows=rows, study_id="synthetic")


def test_switch_rates_are_the_constructed_answer(dataset):
    result = REGISTRY["meyer-fragmentation"].run(dataset)
    per = result.tables["per_session"].set_index("sessionId")
    assert per.loc["S1", "switches"] == 3  # dupe + window rows ignored
    assert per.loc["S2", "switches"] == 6
    assert per.loc["S1", "switchesPerHour"] == pytest.approx(3.0)
    assert per.loc["S2", "switchesPerHour"] == pytest.approx(6.0)


def test_segments_and_honest_reporting(dataset):
    result = REGISTRY["meyer-fragmentation"].run(dataset)
    segments = result.tables["segments"]
    # S1 changed-file events at minutes 1,10,20,30 -> segments 9,10,10.
    s1 = segments[segments["sessionId"] == "S1"]["segmentMinutes"].tolist()
    assert s1 == pytest.approx([9.0, 10.0, 10.0])
    # One session per condition -> unpaired cells, honest framing (NFR-8).
    line = result.tables["rate_test"].iloc[0]
    assert "Mann-Whitney" in line["test"]
    assert "hypothesis-generating" in result.summary
    # The citation travels with the output (FR-ANA-5).
    assert "Meyer" in result.methods
    assert "10.1109/TSE.2017.2656886" in result.methods


def test_degrades_honestly_without_file_switches():
    rows = _session("S3", "P03", "ai-assisted", [(5, None), (25, None)])
    result = REGISTRY["meyer-fragmentation"].run(Dataset(rows=rows))
    per = result.tables["per_session"]
    assert (per["switches"] == 0).all()
    assert "no file-bearing editor_focus switches" in result.summary
