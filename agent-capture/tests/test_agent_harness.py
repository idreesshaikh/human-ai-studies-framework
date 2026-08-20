"""Task-outcome harness (FR-INST-16)."""

from datetime import UTC, datetime, timedelta

from agent_capture.events import SOURCE_HARNESS, Keys
from agent_capture.harness import Harness, run_pytest

PASSING = "def test_ok():\n    assert 1 + 1 == 2\n"
FAILING = "def test_bad():\n    assert False\n"


def _write(dir_, name, body):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(body)


def test_run_pytest_counts_pass_and_fail(tmp_path):
    _write(tmp_path, "test_a.py", PASSING)
    _write(tmp_path, "test_b.py", FAILING)
    result = run_pytest(tmp_path)
    assert result["passed"] == 1
    assert result["failed"] == 1
    assert result["total"] == 2


def test_missing_tests_dir_reports_not_ran(tmp_path):
    result = run_pytest(tmp_path / "nope")
    assert result == {"passed": 0, "failed": 0, "total": 0, "ran": False}


def test_harness_emits_failing_then_green_outcome(tmp_path):
    tests = tmp_path / "task-tests"
    _write(tests, "test_it.py", FAILING)

    class Clock:
        def __init__(self):
            self.t = datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC)

        def __call__(self):
            return self.t

    clock = Clock()
    start = clock()
    harness = Harness(
        Keys("P01", "ai-assisted", "S1"), tests, clock=clock, session_start=start
    )

    first = harness.run(trigger="save")
    assert first["source"] == SOURCE_HARNESS
    assert first["type"] == "task_outcome"
    assert first["payload"]["passed"] is False
    assert "firstGreenMs" not in first["payload"]

    clock.t += timedelta(minutes=30)
    (tests / "test_it.py").write_text(PASSING)
    green = harness.run(trigger="session-end")
    assert green["payload"]["passed"] is True
    assert green["payload"]["total"] == 1
    assert green["payload"]["firstGreenMs"] == 30 * 60 * 1000

    assert [first["seq"], green["seq"]] == [0, 1]


def test_first_green_is_sticky(tmp_path):
    """
    Once green, time-to-first-green stays pinned to the first pass even if a later run
    regresses.
    """
    tests = tmp_path / "task-tests"
    _write(tests, "test_it.py", PASSING)
    harness = Harness(Keys("P01", "ai-assisted", "S1"), tests)
    green = harness.run()
    assert green["payload"]["passed"] is True
    ttg = green["payload"]["firstGreenMs"]
    (tests / "test_it.py").write_text(FAILING)
    regressed = harness.run()
    assert regressed["payload"]["passed"] is False
    assert regressed["payload"]["firstGreenMs"] == ttg
