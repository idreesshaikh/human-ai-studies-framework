"""
The session timeline figure (P2-1): one session's events on a shared timeline — a lane
per event type in first-appearance order, minutes from the session's first event,
flagged rows drawn as open diamonds.
"""

from __future__ import annotations

import io

import matplotlib.pyplot as plt
from analysis.dataset import Dataset
from analysis.figures import session_timeline
from tests_support import synthetic_rows

plt.close("all")


def _flagged_rows() -> list[dict]:
    rows = synthetic_rows()
    rows[3]["flags"] = ["future-ts"]
    return rows


def _svg(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="svg")
    return buf.getvalue()


def test_lanes_follow_first_appearance_order():
    dataset = Dataset(rows=synthetic_rows(), study_id="pilot-2026")
    sid = dataset.rows[0]["sessionId"]
    session = dataset.events[dataset.events["sessionId"] == sid]
    expected = []
    for t in session["type"]:
        if t not in expected:
            expected.append(t)
    fig = session_timeline(dataset, sid)
    labels = [lab.get_text() for lab in fig.axes[0].get_yticklabels()]
    assert [lab.split(" (")[0] for lab in labels] == expected


def test_x_axis_is_minutes_from_session_start():
    dataset = Dataset(rows=synthetic_rows(), study_id="pilot-2026")
    sid = dataset.rows[0]["sessionId"]
    session = dataset.events[dataset.events["sessionId"] == sid]
    duration = (session["ts"].max() - session["ts"].min()).total_seconds() / 60.0
    fig = session_timeline(dataset, sid)
    lo, hi = fig.axes[0].get_xlim()
    assert lo <= 0
    assert hi - lo >= duration


def test_flagged_rows_are_drawn_differently():
    """
    A row carrying ingest flags must not be silently identical to a clean row: the
    flagged session renders one more marker collection (the open diamond overlay) than
    the same session without flags.
    """
    clean = Dataset(rows=synthetic_rows(), study_id="pilot-2026")
    flagged = Dataset(rows=_flagged_rows(), study_id="pilot-2026")
    sid = flagged.rows[0]["sessionId"]
    n_clean = len(session_timeline(clean, sid).axes[0].collections)
    n_flagged = len(session_timeline(flagged, sid).axes[0].collections)
    assert n_flagged == n_clean + 1


def test_unknown_session_renders_without_crash():
    dataset = Dataset(rows=synthetic_rows(), study_id="pilot-2026")
    fig = session_timeline(dataset, "no-such-session")
    assert "no events" in "".join(t.get_text() for t in fig.axes[0].texts)


def test_figure_is_deterministic():
    rows = _flagged_rows()
    dataset = Dataset(rows=rows, study_id="pilot-2026")
    a = _svg(session_timeline(dataset, rows[0]["sessionId"]))
    b = _svg(session_timeline(dataset, rows[0]["sessionId"]))
    assert a == b
