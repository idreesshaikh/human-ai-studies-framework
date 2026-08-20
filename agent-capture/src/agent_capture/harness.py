"""Task-outcome harness (FR-INST-16) - correctness ground truth."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from agent_capture.events import (
    EVENT_TASK_OUTCOME,
    SOURCE_HARNESS,
    Keys,
    study_event,
)

Clock = Callable[[], datetime]

_COUNT = {
    kind: re.compile(rf"(\d+) {kind}")
    for kind in ("passed", "failed", "error", "errors", "skipped")
}


def run_pytest(tests_dir: str | Path) -> dict:
    """Run the acceptance suite and return ``{passed, failed, total}``."""
    tests_dir = Path(tests_dir)
    if not tests_dir.exists():
        return {"passed": 0, "failed": 0, "total": 0, "ran": False}
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(tests_dir),
                "-q",
                "--tb=no",
                "-p",
                "no:cacheprovider",
            ],
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.SubprocessError):
        return {"passed": 0, "failed": 0, "total": 0, "ran": False}
    return {**_parse_summary(proc.stdout + proc.stderr), "ran": True}


def _parse_summary(output: str) -> dict:
    counts = {}
    for kind, pat in _COUNT.items():
        m = pat.findall(output)
        counts[kind] = int(m[-1]) if m else 0
    passed = counts["passed"]
    failed = counts["failed"] + counts["error"] + counts["errors"]
    total = passed + failed
    return {"passed": passed, "failed": failed, "total": total}


class Harness:
    """
    Runs the acceptance suite per trigger for one session and tracks the first all-green
    moment for time-to-first-green.
    """

    def __init__(
        self,
        keys: Keys,
        tests_dir: str | Path,
        *,
        clock: Clock | None = None,
        session_start: datetime | None = None,
    ):
        self.keys = keys
        self.tests_dir = Path(tests_dir)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.session_start = session_start or self.clock()
        self._seq = 0
        self._first_green: datetime | None = None

    def run(self, trigger: str = "session-end") -> dict:
        """Run the suite and return one ``task_outcome`` StudyEvent."""
        now = self.clock()
        result = run_pytest(self.tests_dir)
        passed_all = result["ran"] and result["total"] > 0 and result["failed"] == 0
        payload = {
            "trigger": trigger,
            "passed": passed_all,
            "failed": result["failed"],
            "total": result["total"],
        }
        if passed_all and self._first_green is None:
            self._first_green = now
        if self._first_green is not None:
            payload["firstGreenMs"] = int(
                (self._first_green - self.session_start).total_seconds() * 1000
            )
        event = study_event(
            self.keys,
            source=SOURCE_HARNESS,
            seq=self._seq,
            type=EVENT_TASK_OUTCOME,
            ts=now.isoformat(timespec="milliseconds"),
            payload=payload,
        )
        self._seq += 1
        return event
