"""The calibration kit under scripts/: session order, instrument version, matrix.

pytest's testpaths do not include scripts/, so the scripts are exercised here
and run through a subprocess exactly as the researcher will run them.
"""

import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
EXPERIMENT = ROOT / "docs" / "experiments" / "ai-use-calibration"
PLAN = EXPERIMENT / "plan.md"
LABELS = EXPERIMENT / "labels.csv"
TASK = EXPERIMENT / "task"
REFERENCE_SOLUTION = EXPERIMENT / "reference" / "inventory_solution.py"

NO_AI = "no-ai"
AI_ROUTES = [
    "copilot-inline",
    "copilot-chat",
    "browser-paste",
    "retype",
    "cli-agent-hooks",
    "cli-agent-no-hooks",
]
BENIGN = [
    "benign-formatter",
    "benign-snippet",
    "benign-rename",
    "benign-own-paste",
    "benign-stackoverflow-paste",
]
MATRIX_COLUMNS = [
    "scenario",
    "signal",
    "fired",
    "fired_ci_low",
    "fired_ci_high",
    "n",
    "abstained",
]


def run_script(name: str, *args: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def order_rows() -> list[dict]:
    result = run_script("calibration_order.py")
    assert result.returncode == 0, result.stderr
    return list(csv.DictReader(result.stdout.splitlines()))


# --- calibration_order.py --------------------------------------------------


def test_order_has_31_rows_and_is_deterministic():
    first = run_script("calibration_order.py")
    second = run_script("calibration_order.py")
    assert first.returncode == 0, first.stderr
    assert first.stdout == second.stdout
    lines = first.stdout.strip().splitlines()
    assert lines[0] == "order,scenario,rep"
    rows = order_rows()
    assert len(rows) == 31
    assert [int(r["order"]) for r in rows] == list(range(1, 32))


def test_order_counts_per_scenario():
    rows = order_rows()
    counts = Counter(r["scenario"] for r in rows)
    expected = {
        NO_AI: 3,
        **dict.fromkeys(AI_ROUTES, 3),
        **dict.fromkeys(BENIGN, 2),
    }
    assert counts == expected


def test_order_reps_count_up_in_session_order():
    seen = Counter()
    for row in order_rows():
        seen[row["scenario"]] += 1
        assert int(row["rep"]) == seen[row["scenario"]]


def test_order_is_actually_shuffled():
    scenarios = [r["scenario"] for r in order_rows()]
    unshuffled = [NO_AI] * 3 + [s for s in AI_ROUTES for _ in range(3)]
    unshuffled += [s for s in BENIGN for _ in range(2)]
    assert scenarios != unshuffled


def test_frozen_plan_carries_the_printed_order_verbatim():
    # The plan is committed to freeze it; a drifted order would silently
    # invalidate the freeze.
    printed = run_script("calibration_order.py").stdout.strip()
    assert printed in PLAN.read_text()


# --- instrument_version.py -------------------------------------------------


def test_instrument_version_prints_the_documented_keys():
    result = run_script("instrument_version.py")
    assert result.returncode == 0, result.stderr
    version = json.loads(result.stdout)
    assert {"head", "uncommittedDiffSha256", "vsixVersion"} <= set(version)
    assert len(version["head"]) == 40
    assert len(version["uncommittedDiffSha256"]) == 64
    package = json.loads((ROOT / "extension" / "package.json").read_text())
    assert version["vsixVersion"] == package["version"]


def test_instrument_version_hashes_the_documented_diff(tmp_path):
    script = load_script("instrument_version")
    calls = []

    def fake_git(*args):
        calls.append(args)
        if args[0] == "rev-parse":
            return b"abc123\n"
        if args[0] == "diff":
            return b"diff --git a/x b/x\n+changed\n"
        return b"extension/new.ts\n"

    (tmp_path / "extension").mkdir()
    (tmp_path / "extension" / "package.json").write_text('{"version": "9.8.7"}')
    version = script.collect(tmp_path, run_git=fake_git)
    assert version["head"] == "abc123"
    assert version["vsixVersion"] == "9.8.7"
    assert (
        version["uncommittedDiffSha256"]
        == hashlib.sha256(b"diff --git a/x b/x\n+changed\n").hexdigest()
    )
    assert version["untrackedFiles"] == ["extension/new.ts"]
    assert ("rev-parse", "HEAD") in calls
    assert (
        "diff",
        "HEAD",
        "--",
        "extension",
        "agent-capture",
        "analysis/src/analysis/recipes/control_arm_audit.py",
    ) in calls


def test_instrument_version_only_ever_reads_git():
    script = load_script("instrument_version")
    for forbidden in ("commit", "add", "stash", "checkout", "reset", "config"):
        with pytest.raises(ValueError, match="read-only"):
            script.git(forbidden)


# --- run_calibration.py ----------------------------------------------------


def event(session, kind, seq, payload=None, condition="calibration"):
    return {
        "sessionId": session,
        "participantId": "operator",
        "condition": condition,
        "type": kind,
        "seq": seq,
        "payload": payload or {},
    }


def session_rows(session, *extra, complete=True, first_seq=0):
    """A TERN session; `extra` are (type, payload) events between start and end."""
    rows = [
        event(session, "session_start", first_seq),
        event(
            session,
            "environment_snapshot",
            first_seq + 1,
            {
                "auditCapture": {
                    "aiLifecycle": True,
                    "editBursts": True,
                    "clipboard": True,
                }
            },
        ),
    ]
    for offset, (kind, payload) in enumerate(extra, start=2):
        rows.append(event(session, kind, first_seq + offset, payload))
    if complete:
        rows.append(event(session, "session_end", first_seq + 2 + len(extra)))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return path


def write_labels(path: Path, labels: list[tuple[str, str, str]]) -> Path:
    lines = ["sessionId,scenario,aiUsed,rep,operatorNote"]
    lines += [f"{sid},{scenario},{used},1," for sid, scenario, used in labels]
    path.write_text("\n".join(lines) + "\n")
    return path


def matrix(out: Path) -> dict[tuple[str, str], dict]:
    with (out / "matrix.csv").open(newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == MATRIX_COLUMNS
        return {(r["scenario"], r["signal"]): r for r in reader}


def run_calibration(tmp_path, rows, labels, *, extra_rows=()):
    rows_path = write_jsonl(tmp_path / "rows.jsonl", rows)
    labels_path = write_labels(tmp_path / "labels.csv", labels)
    out = tmp_path / "out"
    result = run_script(
        "run_calibration.py",
        "--rows",
        rows_path,
        *extra_rows,
        "--labels",
        labels_path,
        "--out",
        out,
    )
    return result, out


def test_run_calibration_writes_matrix(tmp_path):
    rows = session_rows("s-no-ai") + session_rows(
        "s-inline", ("ai_suggestion", {"action": "accepted"})
    )
    result, out = run_calibration(
        tmp_path,
        rows,
        [("s-no-ai", "no-ai", "false"), ("s-inline", "copilot-inline", "true")],
    )
    assert result.returncode == 0, result.stderr
    table = matrix(out)
    assert {r["scenario"] for r in table.values()} == {"no-ai", "copilot-inline"}
    assert {s for _, s in table} >= {"combined", "accepted_inline_suggestion"}

    fired = table[("copilot-inline", "accepted_inline_suggestion")]
    assert float(fired["fired"]) == 1.0
    assert fired["n"] == "1"
    assert fired["abstained"] == "0"
    assert float(fired["fired_ci_high"]) == 1.0
    quiet = table[("no-ai", "accepted_inline_suggestion")]
    assert float(quiet["fired"]) == 0.0
    assert float(quiet["fired_ci_low"]) == 0.0

    report = json.loads((out / "report.json").read_text())
    assert set(report["byScenario"]) == {"no-ai", "copilot-inline"}
    assert report["labelled"] == 2
    assert (out / "matrix.png").read_bytes().startswith(b"\x89PNG")


def test_incomplete_capture_abstains_and_is_never_a_negative(tmp_path):
    # No session_end: TERN did not finish capturing, so silence proves nothing.
    rows = session_rows("s-torn", complete=False)
    result, out = run_calibration(tmp_path, rows, [("s-torn", "retype", "true")])
    assert result.returncode == 0, result.stderr
    cell = matrix(out)[("retype", "combined")]
    assert cell["abstained"] == "1"
    assert cell["n"] == "0"
    assert cell["fired"] == ""  # NA, not 0
    assert cell["fired_ci_low"] == "" and cell["fired_ci_high"] == ""


def test_scenario_without_assessed_sessions_reports_na_not_zero(tmp_path):
    rows = session_rows("s-ok") + session_rows("s-torn", complete=False)
    result, out = run_calibration(
        tmp_path,
        rows,
        [("s-ok", "no-ai", "false"), ("s-torn", "retype", "true")],
    )
    assert result.returncode == 0, result.stderr
    table = matrix(out)
    for signal in ("combined", "paste_edit", "agent_turn"):
        assert table[("retype", signal)]["fired"] == ""
        assert table[("retype", signal)]["n"] == "0"
    assert table[("no-ai", "combined")]["fired"] == "0.0"


def test_labelled_session_with_no_rows_is_an_abstention_and_a_warning(tmp_path):
    rows = session_rows("s-ok")
    result, out = run_calibration(
        tmp_path,
        rows,
        [("s-ok", "no-ai", "false"), ("s-lost", "browser-paste", "true")],
    )
    assert result.returncode == 0, result.stderr
    assert "s-lost" in result.stderr
    cell = matrix(out)[("browser-paste", "combined")]
    assert cell["fired"] == "" and cell["n"] == "0" and cell["abstained"] == "1"
    report = json.loads((out / "report.json").read_text())
    assert report["unmatchedLabels"] == ["s-lost"]


def test_rows_accept_a_dataset_export_and_several_files_without_duplicates(tmp_path):
    tern = session_rows("s-cli", ("tool_call", {}))
    agent = [
        {**event("s-cli", "agent_turn", 0), "source": "agent-capture"},
    ]
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps({"studyId": "x", "rows": tern + agent}))
    jsonl = write_jsonl(tmp_path / "tern.jsonl", tern)  # same rows again
    labels = write_labels(tmp_path / "labels.csv", [("s-cli", "cli-agent-hooks", "1")])
    out = tmp_path / "out"
    result = run_script(
        "run_calibration.py",
        "--rows",
        jsonl,
        dataset,
        "--labels",
        labels,
        "--out",
        out,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out / "report.json").read_text())
    scenario = report["byScenario"]["cli-agent-hooks"]
    assert scenario["labelled"] == 1
    assert matrix(out)[("cli-agent-hooks", "tool_call")]["fired"] == "1.0"
    assert matrix(out)[("cli-agent-hooks", "agent_turn")]["fired"] == "1.0"


@pytest.mark.parametrize(
    ("label_lines", "message"),
    [
        (["s1,not-a-scenario,false,1,"], "unknown scenario"),
        (["s1,no-ai,maybe,1,"], "aiUsed"),
        (["s1,no-ai,false,1,", "s1,retype,true,1,"], "duplicate"),
        ([], "no labelled sessions"),
    ],
)
def test_bad_labels_are_refused_with_a_clear_message(tmp_path, label_lines, message):
    rows_path = write_jsonl(tmp_path / "rows.jsonl", session_rows("s1"))
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "\n".join(["sessionId,scenario,aiUsed,rep,operatorNote", *label_lines]) + "\n"
    )
    result = run_script(
        "run_calibration.py",
        "--rows",
        rows_path,
        "--labels",
        labels,
        "--out",
        tmp_path / "out",
    )
    assert result.returncode != 0
    assert message in result.stderr
    assert "Traceback" not in result.stderr


def test_the_labels_file_starts_with_the_exact_header():
    # Only the first line: the operator adds a row after every session.
    first_line = LABELS.read_text().splitlines()[0]
    assert first_line == "sessionId,scenario,aiUsed,rep,operatorNote"


# --- the session task ------------------------------------------------------


def copy_task(tmp_path: Path) -> Path:
    """A fresh copy of the participant folder, as each session starts from."""
    work = tmp_path / "work"
    shutil.copytree(
        TASK, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache")
    )
    return work


def run_task_tests(work: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )


def test_task_tests_pass_against_the_reference_solution(tmp_path):
    work = copy_task(tmp_path)
    shutil.copyfile(REFERENCE_SOLUTION, work / "inventory.py")
    result = run_task_tests(work)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "8 passed" in result.stdout


def test_task_tests_fail_on_every_test_against_the_stub(tmp_path):
    result = run_task_tests(copy_task(tmp_path))
    assert result.returncode != 0
    assert "8 failed" in result.stdout
    assert "passed" not in result.stdout


def test_participant_folder_holds_stubs_and_no_solution():
    stub = (TASK / "inventory.py").read_text()
    assert stub.count("raise NotImplementedError") == 5
    assert not list(TASK.rglob("*solution*"))
    assert "def _is_skipped" not in "".join(
        p.read_text() for p in TASK.rglob("*.py") if p.name != "test_inventory.py"
    )
