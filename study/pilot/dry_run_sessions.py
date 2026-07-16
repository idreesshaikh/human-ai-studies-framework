"""MP-08 dry run: the facilitator's two fake 45-minute sessions.

Synthesizes participant P00's counterbalanced session pair (ai-assisted /
Task A, then unassisted / Task B) in the extension's HttpSink wire format -
schema v3, contiguous seq, realistic event mix per condition - and POSTs
them to a running middleware. P00 is deliberately outside the P1..P6
roster: the middleware must flag every row ``unknown-participant`` (so
dry-run data can never masquerade as a roster participant's) while still
ingesting it (never-interrupt, NFR-1).

Deterministic by construction (hand-authored schedules, fixed date) so the
dry run is replayable bit-for-bit (NFR-6). Stdlib only, like
``middleware/scripts/replay_session.py``:

    uv run python study/pilot/dry_run_sessions.py [--server URL]

Exits nonzero if a POST fails, a seq gap is detected, or the
unknown-participant flag does not appear.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request

DATE = "2026-07-12"
SCHEMA_V = 3


def _event(session, participant, condition, seq, start_h, minute, type_, payload):
    total_min = start_h * 60 + minute
    h, m = divmod(int(total_min), 60)
    sec = round((total_min % 1) * 60, 1)
    return {
        "v": SCHEMA_V,
        "ts": f"{DATE}T{h:02d}:{m:02d}:{sec:04.1f}Z",
        "mono": minute * 60_000.0,
        "sessionId": session,
        "participantId": participant,
        "condition": condition,
        "seq": seq,
        "type": type_,
        "payload": payload,
    }


def _session(session_id, condition, start_h, schedule):
    """Schedule: [(minute, type, payload)] -> wire events, contiguous seq."""
    return [
        _event(session_id, "P00", condition, seq, start_h, minute, type_, payload)
        for seq, (minute, type_, payload) in enumerate(schedule)
    ]


def _sug(n, action, **extra):
    return ("ai_suggestion", {"suggestionId": f"dr-sg{n}", "action": action, **extra})


TASK_A = "src/aggregate.py"  # Task A "expenses" (ai-assisted session)
TASK_B = "src/parse.py"  # Task B "logbook" (unassisted session)

#: 09:00 - ai-assisted, Task A. Suggestion review is the condition's texture:
#: five suggestion lifecycles (3 accepted / 2 dismissed), AI-origin bursts
#: followed by visible-range dwell, and a mid-session reference paste.
AI_SCHEDULE = [
    (0.0, "session_start", {"plannedDurationMinutes": 45}),
    (0.1, "editor_focus", {"state": "focused"}),
    (0.2, "visible_range", {"file": TASK_A, "topLine": 0, "bottomLine": 44}),
    (2.0, "edit_burst", {"file": TASK_A, "charsAdded": 120, "charsDeleted": 14,
                         "linesTouched": 6, "durationMs": 48_000, "origin": "human"}),
    (4.0, *_sug(1, "shown")),
    (4.1, *_sug(1, "accepted", visibleMs=6_400, charCount=96, lineCount=4)),
    (4.2, "edit_burst", {"file": TASK_A, "charsAdded": 96, "charsDeleted": 0,
                         "linesTouched": 4, "durationMs": 60, "origin": "ai"}),
    (4.5, "visible_range", {"file": TASK_A, "topLine": 18, "bottomLine": 62}),
    (6.0, "file_save", {"file": TASK_A, "charCount": 3_180, "lineCount": 128}),
    (9.0, *_sug(2, "shown")),
    (9.2, *_sug(2, "dismissed", visibleMs=11_800)),
    (11.0, "clipboard_paste", {"charCount": 240, "lineCount": 8, "targetFile": TASK_A}),
    (11.1, "edit_burst", {"file": TASK_A, "charsAdded": 240, "charsDeleted": 0,
                          "linesTouched": 8, "durationMs": 90, "origin": "paste"}),
    (13.0, "edit_burst", {"file": TASK_A, "charsAdded": 88, "charsDeleted": 30,
                          "linesTouched": 5, "durationMs": 70_000, "origin": "human"}),
    (15.2, "fatigue_response", {"score": 2, "latencyMs": 2_800}),
    (18.0, *_sug(3, "shown")),
    (18.2, *_sug(3, "accepted", visibleMs=9_100, charCount=210, lineCount=9)),
    (18.3, "edit_burst", {"file": TASK_A, "charsAdded": 210, "charsDeleted": 0,
                          "linesTouched": 9, "durationMs": 55, "origin": "ai"}),
    (18.6, "visible_range", {"file": TASK_A, "topLine": 40, "bottomLine": 84}),
    (20.0, "file_save", {"file": TASK_A, "charCount": 3_610, "lineCount": 141}),
    (24.0, "window_blur", {}),
    (25.5, "window_focus", {}),
    (27.0, *_sug(4, "shown")),
    (27.3, *_sug(4, "dismissed", visibleMs=16_500)),
    (29.0, "edit_burst", {"file": TASK_A, "charsAdded": 150, "charsDeleted": 42,
                          "linesTouched": 7, "durationMs": 95_000, "origin": "human"}),
    (31.4, "fatigue_response", {"score": 3, "latencyMs": 3_500}),
    (34.0, *_sug(5, "shown")),
    (34.1, *_sug(5, "accepted", visibleMs=4_200, charCount=64, lineCount=2)),
    (34.2, "edit_burst", {"file": TASK_A, "charsAdded": 64, "charsDeleted": 0,
                          "linesTouched": 2, "durationMs": 45, "origin": "ai"}),
    (34.5, "visible_range", {"file": TASK_A, "topLine": 96, "bottomLine": 140}),
    (38.0, "file_save", {"file": TASK_A, "charCount": 3_890, "lineCount": 150}),
    (43.0, "edit_burst", {"file": TASK_A, "charsAdded": 20, "charsDeleted": 6,
                          "linesTouched": 2, "durationMs": 30_000, "origin": "human"}),
    (45.0, "end_survey", {"mentalDemand": 9, "effort": 8, "frustration": 5}),
    (45.2, "session_end", {"reason": "completed"}),
]

#: 11:00 - unassisted, Task B. No ai_suggestion events; more and longer
#: human bursts, two stuck episodes, higher fatigue and workload.
UN_SCHEDULE = [
    (0.0, "session_start", {"plannedDurationMinutes": 45}),
    (0.1, "editor_focus", {"state": "focused"}),
    (0.2, "visible_range", {"file": TASK_B, "topLine": 0, "bottomLine": 44}),
    (3.0, "edit_burst", {"file": TASK_B, "charsAdded": 210, "charsDeleted": 35,
                         "linesTouched": 11, "durationMs": 150_000, "origin": "human"}),
    (7.0, "visible_range", {"file": TASK_B, "topLine": 30, "bottomLine": 74}),
    (9.0, "file_save", {"file": TASK_B, "charCount": 2_940, "lineCount": 119}),
    (12.0, "clipboard_paste",
     {"charCount": 410, "lineCount": 14, "targetFile": TASK_B}),
    (12.1, "edit_burst", {"file": TASK_B, "charsAdded": 410, "charsDeleted": 0,
                          "linesTouched": 14, "durationMs": 110, "origin": "paste"}),
    (14.0, "stuck_response",
     {"answer": "yes", "reason": "dwell", "evidenceMs": 128_000}),
    (16.1, "fatigue_response", {"score": 3, "latencyMs": 4_100}),
    (19.0, "edit_burst", {"file": TASK_B, "charsAdded": 180, "charsDeleted": 64,
                          "linesTouched": 9, "durationMs": 200_000, "origin": "human"}),
    (23.0, "visible_range", {"file": TASK_B, "topLine": 60, "bottomLine": 104}),
    (25.0, "file_save", {"file": TASK_B, "charCount": 3_310, "lineCount": 132}),
    (27.0, "window_blur", {}),
    (28.0, "window_focus", {}),
    (30.5, "stuck_response",
     {"answer": "yes", "reason": "dwell", "evidenceMs": 145_000}),
    (32.0, "fatigue_response", {"score": 4, "latencyMs": 5_200}),
    (35.0, "edit_burst", {"file": TASK_B, "charsAdded": 260, "charsDeleted": 90,
                          "linesTouched": 12, "durationMs": 240_000,
                          "origin": "human"}),
    (39.0, "visible_range", {"file": TASK_B, "topLine": 88, "bottomLine": 130}),
    (41.0, "file_save", {"file": TASK_B, "charCount": 3_520, "lineCount": 140}),
    (43.5, "edit_burst", {"file": TASK_B, "charsAdded": 40, "charsDeleted": 12,
                          "linesTouched": 3, "durationMs": 60_000, "origin": "human"}),
    (45.0, "end_survey", {"mentalDemand": 14, "effort": 13, "frustration": 11}),
    (45.2, "session_end", {"reason": "completed"}),
]


def _call(method, url, body=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    sessions = [
        ("S-P00-dry-ai", "ai-assisted", 9, AI_SCHEDULE),
        ("S-P00-dry-un", "unassisted", 11, UN_SCHEDULE),
    ]
    ok = True
    for sid, condition, start_h, schedule in sessions:
        events = _session(sid, condition, start_h, schedule)
        res = _call(
            "POST",
            f"{args.server}/ingest/events",
            {"source": "cognitive-overlay", "events": events},
        )
        gaps = _call("GET", f"{args.server}/sessions/{sid}/gaps")
        flagged = res.get("flagged", 0)
        print(
            f"{sid} ({condition}): {res['inserted']} inserted, "
            f"{res['duplicates']} duplicates, flagged {flagged}; "
            f"gaps: {len(gaps['gaps'])} "
            f"(received {gaps['received']}/{gaps['expected']})"
        )
        if gaps["gaps"]:
            print(f"  ERROR: seq gaps in {sid}: {gaps['gaps']}", file=sys.stderr)
            ok = False
        # P00 is off-roster on purpose - the flag MUST appear on fresh rows.
        if res["inserted"] and not flagged:
            print(
                f"  ERROR: {sid} ingested without the unknown-participant "
                "flag (P00 is off-roster; FR-META-1)",
                file=sys.stderr,
            )
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
