"""Compare rehearsal action logs (ground truth) with the TERN rows they produced.

    python scripts/rehearsals/compare.py LOG_DIR [ROWS_DIR]

LOG_DIR holds the `*-actions.jsonl` files written by
`scripts/calibration_drive.cjs --out`; ROWS_DIR defaults to
~/ai-use-calibration/dry/rows. For rehearsals only, never calibration sessions.
"""

import collections
import datetime as dt
import itertools
import json
import sys
from pathlib import Path

QUIET = {"edit_burst", "clipboard_paste", "visible_range", "attention"}
QUIET |= {"editor_focus", "file_save"}


def stamp(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def read_jsonl(path: Path) -> list[dict]:
    with path.open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def tern_rows(rows_dir: Path) -> dict[str, list[dict]]:
    sessions: dict[str, list[dict]] = collections.defaultdict(list)
    for path in rows_dir.glob("operator_*.jsonl"):
        for row in read_jsonl(path):
            sessions[row["sessionId"]].append(row)
    return sessions


def describe(session_id: str, rows: list[dict]) -> list[str]:
    rows = sorted(rows, key=lambda r: r["seq"])
    types = collections.Counter(r["type"] for r in rows)
    seqs = [r["seq"] for r in rows]
    gaps = [(a, b) for a, b in itertools.pairwise(seqs) if b != a + 1]
    bursts = [r["payload"] for r in rows if r["type"] == "edit_burst"]
    pastes = [r["payload"] for r in rows if r["type"] == "clipboard_paste"]
    internal = sum("msSinceInternalCopy" in p for p in pastes)
    big = [
        (b["charsAdded"], b["durationMs"], b["origin"])
        for b in bursts
        if b.get("charsAdded", 0) >= 80
    ]
    other = {k: v for k, v in types.items() if k not in QUIET}
    origins = dict(collections.Counter(b["origin"] for b in bursts))
    return [
        f"   session {session_id}: {len(rows)} rows, seq gaps {gaps[:4]}, "
        f"sensor errors {types['behavior_sensor_error']}",
        f"     bursts by origin {origins}",
        f"     clipboard_paste {len(pastes)} (internal copy {internal}), "
        f"chars {[p['charCount'] for p in pastes]}",
        f"     bursts of 80+ chars (chars, ms, origin): {big[:8]}",
        f"     lifecycle and other events: {other}",
    ]


def main() -> None:
    logs = Path(sys.argv[1])
    rows_dir = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else (Path.home() / "ai-use-calibration" / "dry" / "rows")
    )
    sessions = tern_rows(rows_dir)
    for log in sorted(logs.glob("*-actions.jsonl")):
        actions = read_jsonl(log)
        start = stamp(actions[0]["ts"])
        stop = stamp(actions[-1]["ts"]) + dt.timedelta(seconds=30)
        steps = [a["step"] for a in actions if a["action"] == "step"]
        did = collections.Counter(s["do"] for s in steps)
        cmd_v = did["paste"] + sum(s.get("keys") == "Meta+V" for s in steps)
        print(f"== {log.name}: {dict(did)}")
        print(f"   Cmd+V pastes {cmd_v}, palette pastes {did['palettePaste']}")
        for action in actions:
            if action["action"] == "error":
                print("   DRIVER ERROR:", action["error"][:300])
        first = {
            sid: min(stamp(r["ts"]) for r in rows) for sid, rows in sessions.items()
        }
        for sid, began in sorted(first.items(), key=lambda item: item[1]):
            if start <= began <= stop:
                print("\n".join(describe(sid, sessions[sid])))


if __name__ == "__main__":
    main()
