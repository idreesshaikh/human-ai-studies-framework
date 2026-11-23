"""The calibration kit under scripts/: session order, instrument version, matrix.

pytest's testpaths do not include scripts/, so the scripts are exercised here
and run through a subprocess exactly as the researcher will run them.
"""

import csv
import datetime as dt
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"

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
PROBES = [
    "probe-menu-paste",
    "probe-word-accept",
    "probe-mouse-accept",
    "probe-agent-closed-file",
    "probe-agent-explain",
    "probe-format-large",
    "probe-rename-many",
]
LABEL_HEADER = "sessionId,scenario,aiUsed,exposed,assisted,rep,operatorNote"
MATRIX_COLUMNS = [
    "scenario",
    "signal",
    "fired",
    "fired_ci_low",
    "fired_ci_high",
    "n",
    "abstained",
]


@pytest.fixture(autouse=True)
def isolated_calibration_tests(monkeypatch, tmp_path):
    """No private experiments, sockets, or ambient reviewer configuration."""
    monkeypatch.setenv("CALIBRATION_REVIEWER", "none")
    for reviewer in ("CODEX", "CLAUDE"):
        monkeypatch.setenv(
            f"CALIBRATION_{reviewer}", str(tmp_path / "missing-reviewer")
        )
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if (ROOT / "docs" / "experiments") in path.resolve().parents:
            pytest.fail("tests must never access docs/experiments")
        return original_open(path, *args, **kwargs)

    def no_network(*args, **kwargs):
        pytest.fail("calibration tests must not use the network")

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "bind", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)


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


@pytest.fixture
def calibration(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return load_script("run_calibration")


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
        NO_AI: 2,
        **dict.fromkeys(AI_ROUTES, 2),
        **dict.fromkeys(BENIGN, 2),
        **dict.fromkeys(PROBES, 1),
    }
    assert counts == expected


def test_order_counts_per_group():
    order = load_script("calibration_order")
    assert order.SEED == 20261112
    assert tuple(PROBES) == order.PROBES
    assert Counter(order.GROUP_OF[row["scenario"]] for row in order_rows()) == {
        "no AI": 2,
        "AI route": 12,
        "benign look-alike": 10,
        "boundary probe": 7,
    }


def test_order_reps_count_up_in_session_order():
    seen = Counter()
    for row in order_rows():
        seen[row["scenario"]] += 1
        assert int(row["rep"]) == seen[row["scenario"]]


def test_order_is_actually_shuffled():
    scenarios = [r["scenario"] for r in order_rows()]
    unshuffled = [NO_AI] * 2 + [s for s in AI_ROUTES for _ in range(2)]
    unshuffled += [s for s in BENIGN for _ in range(2)] + PROBES
    assert scenarios != unshuffled


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
    lines = [LABEL_HEADER]
    for sid, scenario, used in labels:
        flag = "true" if used in {"true", "1", "yes"} else "false"
        lines.append(f"{sid},{scenario},{used},{flag},{flag},1,")
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
    assert report["labelSummary"] == {
        "no-ai": {"labelled": 1, "aiUsed": 0, "exposed": 0, "assisted": 0},
        "copilot-inline": {"labelled": 1, "aiUsed": 1, "exposed": 1, "assisted": 1},
    }
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
    assert (report["labelled"], report["assessed"], report["abstained"]) == (2, 1, 1)
    lost = report["byScenario"]["browser-paste"]
    assert (lost["labelled"], lost["assessed"], lost["abstained"]) == (1, 0, 1)


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
        (["s1,not-a-scenario,false,false,false,1,"], "unknown scenario"),
        (["s1,no-ai,maybe,false,false,1,"], "aiUsed"),
        (["s1,no-ai,false,maybe,false,1,"], "exposed"),
        (["s1,no-ai,false,false,1,1,"], "assisted"),
        (["s1,no-ai,false,false,false,1,,extra"], "expected 7 fields"),
        (["s1,no-ai,false,false,false,1"], "expected 7 fields"),
        (
            ["s1,no-ai,false,false,false,1,", "s1,retype,true,true,true,1,"],
            "duplicate",
        ),
        ([], "no labelled sessions"),
    ],
)
def test_bad_labels_are_refused_with_a_clear_message(tmp_path, label_lines, message):
    rows_path = write_jsonl(tmp_path / "rows.jsonl", session_rows("s1"))
    labels = tmp_path / "labels.csv"
    labels.write_text("\n".join([LABEL_HEADER, *label_lines]) + "\n")
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


@pytest.mark.parametrize(
    "header",
    [
        "sessionId,scenario,aiUsed,rep,operatorNote",
        "sessionId,scenario,aiUsed,assisted,exposed,rep,operatorNote",
        LABEL_HEADER + ",extra",
    ],
)
def test_labels_require_the_exact_header(tmp_path, calibration, header):
    labels = tmp_path / "labels.csv"
    labels.write_text(header + "\n")
    with pytest.raises(calibration.CalibrationError, match="expected header") as error:
        calibration.load_labels(labels)
    assert LABEL_HEADER in str(error.value)


def test_report_counts_exposure_and_assistance_but_grades_ai_used(tmp_path):
    labels = tmp_path / "labels.csv"
    labels.write_text(
        LABEL_HEADER + "\n"
        "used,probe-agent-explain,true,true,true,1,\n"
        "exposed,probe-agent-explain,false,true,false,1,\n"
        "assisted,probe-agent-explain,false,true,true,1,\n"
        "quiet,no-ai,false,false,false,1,\n"
        "format,probe-format-large,false,false,false,1,\n"
    )
    rows = session_rows("used", ("agent_turn", {}))
    rows += session_rows("exposed") + session_rows("assisted")
    rows += session_rows("quiet") + session_rows("format")
    result = run_script(
        "run_calibration.py",
        "--rows",
        write_jsonl(tmp_path / "rows.jsonl", rows),
        "--labels",
        labels,
        "--out",
        tmp_path / "out",
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["labelSummary"] == {
        "probe-agent-explain": {
            "labelled": 3,
            "aiUsed": 1,
            "exposed": 3,
            "assisted": 2,
        },
        "no-ai": {"labelled": 1, "aiUsed": 0, "exposed": 0, "assisted": 0},
        "probe-format-large": {"labelled": 1, "aiUsed": 0, "exposed": 0, "assisted": 0},
    }
    rates = report["signals"]["agent_turn"]
    assert rates["sensitivity"]["n"] == 1
    assert rates["specificity"]["n"] == 4
    assert rates["sensitivity"]["value"] == rates["specificity"]["value"] == 1
    assert list(
        dict.fromkeys(scenario for scenario, _ in matrix(tmp_path / "out"))
    ) == ["no-ai", "probe-agent-explain", "probe-format-large"]


def test_conflicting_duplicate_names_the_key_without_a_traceback(tmp_path):
    rows = session_rows("s1")
    duplicate = write_jsonl(
        tmp_path / "duplicate.jsonl", [{**rows[0], "payload": {"changed": True}}]
    )
    result, _ = run_calibration(
        tmp_path, rows, [("s1", "no-ai", "false")], extra_rows=[duplicate]
    )
    assert result.returncode == 2
    assert "conflicting duplicate" in result.stderr
    assert "('s1', 'tern', 0)" in result.stderr
    assert "Traceback" not in result.stderr


def test_sensor_health_and_excluded_report_reuse_the_frozen_audit(calibration):
    error = ("behavior_sensor_error", {"source": "clipboard"})
    rows = (
        session_rows(
            "bad",
            error,
            error,
            ("behavior_sensor_error", {"source": "editBursts"}),
            ("ai_suggestion", {"action": "accepted"}),
        )
        + session_rows("ok")
        + session_rows("unlabelled", error)
    )
    labels = {"bad": True, "ok": False, "missing": True}
    scenarios = {"bad": "copilot-inline", "ok": "no-ai", "missing": "retype"}
    report = calibration.build_report(rows, labels, scenarios)
    assert report["channelHealth"] == {
        "bad": {"sensorErrors": 3, "errorSources": ["clipboard", "editBursts"]},
        "ok": {"sensorErrors": 0, "errorSources": []},
        "missing": {"sensorErrors": 0, "errorSources": []},
        "unlabelled": {"sensorErrors": 1, "errorSources": ["clipboard"]},
    }
    assert report["signals"]["combined"]["sensitivity"]["value"] == 1
    assert report["labelled"] == 3 and report["abstained"] == 1
    excluded = report["excludingSensorErrors"]
    expected = calibration.build_report(
        rows,
        {"ok": False, "missing": True},
        {"ok": "no-ai", "missing": "retype"},
    )
    for key in excluded:
        assert excluded[key] == expected[key]
    assert excluded["labelled"] == 2 and excluded["abstained"] == 1
    assert excluded["signals"]["combined"]["sensitivity"]["value"] is None
    assert set(excluded["byScenario"]) == {"no-ai", "retype"}


@pytest.mark.parametrize(
    ("chars", "duration", "expected"),
    [
        (19, 0, False),
        (20, 0, True),
        (20, 2399, True),
        (20, 2400, False),
        (20, 2401, False),
        (100, 12000, False),
        (100, 11999, True),
        (0, 0, False),
        (20, None, False),
    ],
)
def test_typing_speed_threshold_boundaries(calibration, chars, duration, expected):
    row = event("s1", "edit_burst", 0, {"charsAdded": chars, "durationMs": duration})
    assert calibration.typing_speed_flag(row) is expected
    assert not calibration.typing_speed_flag({**row, "source": "agent-capture"})
    assert not calibration.typing_speed_flag({**row, "type": "tool_call"})


def test_typing_speed_rates_use_complete_capture_and_exact_intervals(calibration):
    from scipy.stats import binomtest

    fast = ("edit_burst", {"charsAdded": 20, "durationMs": 0})
    slow = ("edit_burst", {"charsAdded": 20, "durationMs": 2400})
    rows = (
        session_rows("hit", fast, fast)
        + session_rows("miss", slow)
        + session_rows("false-alarm", fast)
        + session_rows("quiet", slow)
        + session_rows("incomplete-positive", fast, ("agent_turn", {}), complete=False)
        + session_rows("gap", fast)
    )
    # A gap is incomplete even with both boundaries present.
    next(r for r in rows if r["sessionId"] == "gap" and r["type"] == "session_end")[
        "seq"
    ] += 1
    labels = {
        "hit": True,
        "miss": True,
        "false-alarm": False,
        "quiet": False,
        "incomplete-positive": True,
        "gap": True,
        "lost": False,
    }
    scenarios = dict.fromkeys(labels, "retype")
    report = calibration.build_report(rows, labels, scenarios)
    signal = report["signals"]["typing_speed_flag"]
    for rate in ("sensitivity", "specificity", "fired"):
        n = 4 if rate == "fired" else 2
        ci = binomtest(n // 2, n).proportion_ci(method="exact")
        assert signal[rate] == {"value": 0.5, "ci": [ci.low, ci.high], "n": n}
    assert report["byScenario"]["retype"]["signals"]["typing_speed_flag"] == signal
    assert report["signals"]["combined"]["sensitivity"]["n"] == 3
    cell = next(
        r
        for r in calibration.matrix_rows(report, scenarios)
        if r["signal"] == "typing_speed_flag"
    )
    assert cell["n"] == 4 and cell["fired"] == "0.5" and cell["abstained"] == 2


def test_typing_speed_no_complete_sessions_is_null(calibration):
    rows = session_rows("torn", ("agent_turn", {}), complete=False)
    report = calibration.build_report(rows, {"torn": True}, {"torn": "cli-agent-hooks"})
    null = {"value": None, "ci": None, "n": 0}
    expected = {"sensitivity": null, "specificity": null, "fired": null}
    assert report["signals"]["typing_speed_flag"] == expected
    assert (
        report["byScenario"]["cli-agent-hooks"]["signals"]["typing_speed_flag"]
        == expected
    )


# --- freeze_calibration.py -------------------------------------------------

EMPTY_DIFF = hashlib.sha256(b"").hexdigest()
CLEAN_BUILD = {
    "head": "a" * 40,
    "uncommittedDiffSha256": EMPTY_DIFF,
    "vsixVersion": "1.0.1",
    "untrackedFiles": [],
}


@pytest.fixture
def freeze(tmp_path, monkeypatch):
    module = load_script("freeze_calibration")
    root = tmp_path / "repo"
    for name in module.PROCEDURE_PATHS:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"procedure: {name}\n")
    monkeypatch.setattr(module, "ROOT", root)
    iv = load_script("instrument_version")
    monkeypatch.setattr(iv, "git", lambda *args, **kwargs: b"")
    monkeypatch.setattr(module, "_instrument_version", lambda: iv)
    return module


def fake_experiment(root: Path) -> Path:
    """A stand-in for the private folder; the real one is never in a checkout."""
    exp = root / "ai-use-calibration"
    (exp / "task" / "tests").mkdir(parents=True)
    (exp / "task" / "__pycache__").mkdir()
    (exp / "reference").mkdir()
    (exp / "plan.md").write_text(
        "# Plan\n\nfrozen text\n\n## Deviations\n\nNone yet.\n"
    )
    (exp / "predictions.md").write_text(
        "# Predictions\n\nP1\n\n## Deviations\n\nNone yet.\n"
    )
    (exp / "task" / "inventory.py").write_text(
        "def f():\n    raise NotImplementedError\n"
    )
    (exp / "task" / "tests" / "test_inventory.py").write_text(
        "def test_f():\n    pass\n"
    )
    (exp / "task" / "__pycache__" / "inventory.cpython-312.pyc").write_bytes(b"\x00")
    (exp / "reference" / "inventory_solution.py").write_text("def f():\n    return 1\n")
    return exp


def test_freeze_writes_hashes_of_every_material_and_none_of_the_caches(
    tmp_path, freeze
):
    exp, manifest = fake_experiment(tmp_path), tmp_path / "freeze.json"

    assert freeze.write(exp, manifest, CLEAN_BUILD) == []

    body = json.loads(manifest.read_text())
    assert sorted(body["files"]) == [
        "plan.md",
        "predictions.md",
        "reference/inventory_solution.py",
        "task/inventory.py",
        "task/tests/test_inventory.py",
    ]
    assert body["instrument"] == {"head": "a" * 40, "vsixVersion": "1.0.1"}
    assert body["procedure"] == {
        path: hashlib.sha256((freeze.ROOT / path).read_bytes()).hexdigest()
        for path in freeze.PROCEDURE_PATHS
    }
    # The manifest carries hashes only, never the private text.
    assert "frozen text" not in manifest.read_text()
    assert freeze.check(exp, manifest, []) == []


def test_freeze_allows_appending_deviations_but_not_editing_the_plan(tmp_path, freeze):
    exp, manifest = fake_experiment(tmp_path), tmp_path / "freeze.json"
    freeze.write(exp, manifest, CLEAN_BUILD)

    plan = exp / "plan.md"
    plan.write_text(plan.read_text() + "\n- 2026-11-15: session 4 crashed.\n")
    assert freeze.check(exp, manifest, []) == []

    plan.write_text(plan.read_text().replace("frozen text", "edited text"))
    assert freeze.check(exp, manifest, []) == ["changed: plan.md"]


def test_freeze_check_names_changed_missing_and_added_files(tmp_path, freeze):
    exp, manifest = fake_experiment(tmp_path), tmp_path / "freeze.json"
    freeze.write(exp, manifest, CLEAN_BUILD)

    (exp / "task" / "inventory.py").write_text("changed\n")
    (exp / "task" / "tests" / "test_inventory.py").unlink()
    (exp / "reference" / "notes.txt").write_text("new\n")

    assert freeze.check(exp, manifest, ["instrument moved"]) == [
        "changed: task/inventory.py",
        "missing: task/tests/test_inventory.py",
        "not in the freeze: reference/notes.txt",
        "instrument moved",
    ]


def test_freeze_refuses_open_todos_a_dirty_build_and_a_second_freeze(tmp_path, freeze):
    exp, manifest = fake_experiment(tmp_path), tmp_path / "freeze.json"
    (exp / "predictions.md").write_text(
        "# P\n\nTODO-BEFORE-FREEZE" + ": pick thresholds\n"
    )
    dirty = {
        **CLEAN_BUILD,
        "uncommittedDiffSha256": "b" * 64,
        "untrackedFiles": ["extension/x.ts"],
    }

    problems = freeze.write(exp, manifest, dirty)

    assert len(problems) == 3
    assert problems[0].startswith("open item: predictions.md:3:")
    assert "uncommitted changes" in problems[1]
    assert "extension/x.ts" in problems[2]
    assert not manifest.exists()

    (exp / "predictions.md").write_text("# P\n")
    assert freeze.write(exp, manifest, CLEAN_BUILD) == []
    assert "never rewritten" in freeze.write(exp, manifest, CLEAN_BUILD)[0]


def test_freeze_check_without_a_manifest_fails_cleanly(tmp_path):
    exp = fake_experiment(tmp_path)
    result = run_script(
        "freeze_calibration.py",
        "check",
        "--experiment",
        exp,
        "--manifest",
        tmp_path / "none.json",
    )
    assert result.returncode == 1
    assert "run write first" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("dirty", ["diff", "untracked"])
def test_freeze_refuses_dirty_procedure_with_read_only_git(tmp_path, freeze, dirty):
    exp, manifest = fake_experiment(tmp_path), tmp_path / "freeze.json"
    calls = []

    def fake_git(*args):
        calls.append(args)
        if args[0] == "diff" and dirty == "diff":
            return b"changed bytes\n"
        if args[0] == "ls-files" and dirty == "untracked":
            return b"scripts/calibration_session.py\n"
        return b""

    problems = freeze.write(exp, manifest, CLEAN_BUILD, run_git=fake_git)
    assert len(problems) == 1
    message = "uncommitted" if dirty == "diff" else "untracked"
    assert message in problems[0]
    assert not manifest.exists()
    assert calls == [
        ("diff", "HEAD", "--", *freeze.PROCEDURE_PATHS),
        ("ls-files", "--others", "--", *freeze.PROCEDURE_PATHS),
    ]


@pytest.mark.parametrize("change", ["edit", "delete", "old-manifest"])
def test_freeze_check_names_procedure_mismatches(tmp_path, freeze, change):
    exp, manifest = fake_experiment(tmp_path), tmp_path / "freeze.json"
    assert freeze.write(exp, manifest, CLEAN_BUILD) == []
    name = freeze.PROCEDURE_PATHS[0]
    if change == "edit":
        (freeze.ROOT / name).write_text("changed\n")
    elif change == "delete":
        (freeze.ROOT / name).unlink()
    else:
        body = json.loads(manifest.read_text())
        del body["procedure"]
        manifest.write_text(json.dumps(body))
    expected = freeze.PROCEDURE_PATHS if change == "old-manifest" else [name]
    assert freeze.check(exp, manifest, []) == [
        f"procedure changed: {path}" for path in expected
    ]


# --- calibration_session.py ------------------------------------------------


def test_session_ids_follow_the_frozen_order():
    session = load_script("calibration_session")
    first = order_rows()[0]
    sid, scenario, rep = session.session_for(1)
    assert (scenario, rep) == (first["scenario"], int(first["rep"]))
    assert sid == f"cal-01-{scenario}-r{rep}"
    with pytest.raises(session.Refused):
        session.session_for(32)


@pytest.mark.parametrize("scenario", [NO_AI, *AI_ROUTES, *BENIGN, *PROBES])
def test_workspace_settings_turn_ai_on_only_where_the_scenario_needs_it(
    tmp_path, scenario
):
    inline = scenario in {"copilot-inline", "probe-word-accept", "probe-mouse-accept"}
    ai_off = not (inline or scenario == "copilot-chat")
    format_on_save = scenario in {"benign-formatter", "probe-format-large"}
    settings = load_script("calibration_session").workspace_settings(
        "cal-01-x-r1", scenario, tmp_path
    )
    assert settings["tern.session.id"] == "cal-01-x-r1"
    assert settings["tern.output.directory"] == str(tmp_path)
    assert settings["chat.disableAIFeatures"] is ai_off
    assert settings["github.copilot.enable"] == {"*": inline}
    assert settings["github.copilot.nextEditSuggestions.enabled"] is False
    assert settings["editor.formatOnSave"] is format_on_save


def test_scenario_script_is_copied_from_plan_section_8():
    session = load_script("calibration_session")
    plan = (
        "## 8. Scenario scripts\n\n**no-ai** (3 sessions)\n1. Type it.\n\n"
        "**retype** (3 sessions)\n1. Retype it.\n\n## 9. Collecting the rows\n"
    )
    assert (
        session.scenario_script("retype", plan)
        == "**retype** (3 sessions)\n1. Retype it."
    )
    with pytest.raises(session.Refused):
        session.scenario_script("copilot-chat", plan)


def test_labels_are_appended_once_and_never_rewritten(tmp_path):
    session = load_script("calibration_session")
    labels = tmp_path / "labels.csv"
    row = {
        "sessionId": "s1",
        "scenario": "no-ai",
        "aiUsed": "false",
        "exposed": "false",
        "assisted": "false",
        "rep": 1,
        "operatorNote": "typed, then ran pytest",
    }
    session.append_label(labels, row)
    with pytest.raises(session.Refused, match="already labelled"):
        session.append_label(labels, row)
    assert labels.read_text().splitlines() == [
        LABEL_HEADER,
        's1,no-ai,false,false,false,1,"typed, then ran pytest"',
    ]
    (tmp_path / "bad.csv").write_text("id,label\n")
    with pytest.raises(session.Refused, match="must start with"):
        session.append_label(tmp_path / "bad.csv", {**row, "sessionId": "s2"})


def test_workspace_is_never_replaced_outside_the_calibration_home(tmp_path):
    session = load_script("calibration_session")
    places = session.Places(tmp_path / "home")
    with pytest.raises(session.Refused, match="run setup first"):
        session.fresh_workspace(places, "s1", "no-ai")
    (tmp_path / "home").mkdir()
    (tmp_path / "home" / "env.sh").write_text("")
    places.work = tmp_path / "elsewhere"
    with pytest.raises(session.Refused, match="outside"):
        session.fresh_workspace(places, "s1", "no-ai")


@pytest.fixture
def session(tmp_path, monkeypatch):
    module = load_script("calibration_session")
    monkeypatch.setattr(module, "LABELS", tmp_path / "real-labels.csv")
    monkeypatch.setattr(module, "VSIX", tmp_path / "tern.vsix")
    module.VSIX.write_bytes(b"packaged instrument")
    monkeypatch.setattr(module, "EXTENSIONS_ROOT", tmp_path / "extensions")
    installed = module.EXTENSIONS_ROOT / "idreesrazak.tern-1.0.1"
    (installed / "out").mkdir(parents=True)
    (installed / "package.json").write_text('{"version":"1.0.1"}')
    (installed / "out" / "extension.js").write_bytes(b"installed instrument")
    task = tmp_path / "task-fixture"
    task.mkdir()
    (task / "inventory.py").write_text("count = 0\n")
    monkeypatch.setattr(module, "TASK", task)
    plan = tmp_path / "plan-fixture.md"
    plan.write_text(
        "## 8. Scenario scripts\n\n"
        + "\n\n".join(
            f"**{scenario}**\n1. Synthetic procedure for {scenario}."
            for scenario in (NO_AI, *AI_ROUTES, *BENIGN, *PROBES)
        )
        + "\n## 9. Collection\n"
    )
    monkeypatch.setattr(module, "PLAN", plan)
    return module


@pytest.mark.parametrize("dry", [False, True])
def test_prepare_refuses_pending_session_before_touching_workspace(
    tmp_path, session, dry
):
    places = session.Places(tmp_path / "home", dry=dry)
    places.current.parent.mkdir(parents=True)
    pending = '{"sessionId":"crashed"}'
    places.current.write_text(pending)
    places.work.mkdir(exist_ok=True)
    sentinel = places.work / "unfinished.py"
    sentinel.write_text("work before the crash")
    with pytest.raises(session.Refused, match="finish it first") as error:
        session.cmd_prepare(places, "next", "no-ai", 1, False, 2)
    assert "actually happened" in str(error.value)
    assert "crash in the note" in str(error.value)
    assert sentinel.read_text() == "work before the crash"
    assert places.current.read_text() == pending


def test_installed_hash_covers_paths_bytes_and_ignores_ds_store(tmp_path, session):
    baseline = session.installed_instrument(session.EXTENSIONS_ROOT)
    installed = session.EXTENSIONS_ROOT / "idreesrazak.tern-1.0.1"
    (installed / ".DS_Store").write_bytes(b"Finder")
    (installed / "out" / ".DS_Store").write_bytes(b"more Finder")
    assert session.installed_instrument() == baseline
    code = installed / "out" / "extension.js"
    code.rename(code.with_name("renamed.js"))
    renamed = session.installed_instrument()
    assert renamed["installedSha256"] != baseline["installedSha256"]
    code = code.with_name("renamed.js")
    code.write_bytes(b"different bytes")
    assert (
        session.installed_instrument()["installedSha256"] != renamed["installedSha256"]
    )
    assert baseline["vsixSha256"] == hashlib.sha256(b"packaged instrument").hexdigest()
    with pytest.raises(session.Refused, match="no installed TERN"):
        session.installed_instrument(tmp_path / "missing")


def test_setup_saves_installed_and_vsix_hashes(tmp_path, session, monkeypatch):
    places = session.Places(tmp_path / "home")
    monkeypatch.setattr(session, "code_cli", lambda: "code")
    monkeypatch.setattr(
        session.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    session.cmd_setup(places, install=True, extensions_root=session.EXTENSIONS_ROOT)
    assert (
        json.loads((places.home / "tern-installed.sha256").read_text())
        == session.installed_instrument()
    )


@pytest.mark.parametrize("dry", [False, True])
def test_prepare_records_hashes_and_real_sessions_refuse_changed_install(
    tmp_path, session, monkeypatch, dry
):
    places = session.Places(tmp_path / "home", dry=dry)
    places.home.mkdir()
    (places.home / "env.sh").write_text("")
    saved = session.installed_instrument()
    (places.home / "tern-installed.sha256").write_text(json.dumps(saved))
    (session.EXTENSIONS_ROOT / "idreesrazak.tern-1.0.1" / "package.json").write_text(
        "changed"
    )
    monkeypatch.setattr(session, "check_freeze", lambda: None)
    task = tmp_path / "task"
    task.mkdir()
    (task / "inventory.py").write_text("pass\n")
    monkeypatch.setattr(session, "TASK", task)
    monkeypatch.setattr(session, "operator_sheet", lambda *args: "session instructions")
    monkeypatch.setattr(session, "code_cli", lambda: "code")
    monkeypatch.setattr(
        session.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "versions\n", ""
        ),
    )
    if dry:
        session.cmd_prepare(places, "s1", "no-ai", 0, False, None)
        assert places.current.is_file()
    else:
        with pytest.raises(session.Refused, match="installed TERN instrument differs"):
            session.cmd_prepare(places, "s1", "no-ai", 1, False, 1)
        assert not places.current.exists()
        assert not places.work.exists()
    record = (places.rows / "s1.env.txt").read_text()
    assert session.installed_instrument()["installedSha256"] in record
    assert saved["vsixSha256"] in record


def prepared_agent(session, tmp_path, monkeypatch, scenario, dry):
    # These tests isolate transcript import; task evidence has its own coverage.
    monkeypatch.setattr(session, "save_task_evidence", lambda *args: None)
    places = session.Places(tmp_path / "home", dry=dry)
    places.rows.mkdir(parents=True)
    order = next(n for n in range(1, 32) if session.session_for(n)[1] == scenario)
    sid, _, rep = session.session_for(order)
    if dry:
        sid = f"dry-{scenario}-1117100000"
    prepared = {
        "sessionId": sid,
        "scenario": scenario,
        "rep": rep,
        "preparedAtEpoch": 100,
    }
    (places.rows / f"{sid}.prepared.json").write_text(json.dumps(prepared))
    places.current.write_text(json.dumps(prepared))
    folder = tmp_path / "transcripts"
    folder.mkdir()
    for name, mtime in [("old.jsonl", 99), ("a.jsonl", 100), ("b.jsonl", 101)]:
        path = folder / name
        path.write_text(f'{{"transcript":"{name}"}}\n')
        os.utime(path, (mtime, mtime))
    monkeypatch.setattr(session, "transcript_dir", lambda work: folder)
    monkeypatch.setenv("CALIBRATION_HOME", str(places.home))
    # These tests isolate transcript import; post-session checks have their own
    # synthetic integration coverage below.
    monkeypatch.setattr(session, "save_task_evidence", lambda *args: None)
    monkeypatch.setattr(session, "cmd_verify", lambda *args: 0)
    return places, sid, order, folder


@pytest.mark.parametrize("scenario", ["cli-agent-hooks", "probe-agent-explain"])
@pytest.mark.parametrize("dry", [False, True])
def test_agent_finish_archives_all_transcripts_and_retry_is_idempotent(
    tmp_path, session, monkeypatch, dry, scenario
):
    places, sid, order, folder = prepared_agent(
        session, tmp_path, monkeypatch, scenario, dry
    )
    calls = []

    def importer(args, **kwargs):
        assert not places.current.exists()
        assert len(session.read_labels(places.labels)) == 1
        transcript = Path(args[args.index("agent_capture.import_transcript") + 1])
        calls.append(transcript.name)
        rows = [event(sid, "agent_turn", 0), event(sid, "tool_call", 1)]
        return subprocess.CompletedProcess(args, 0, json.dumps(rows), "")

    monkeypatch.setattr(session.subprocess, "run", importer)
    finish = "dry" if dry else str(order)
    assert (
        session.main(
            [
                "finish",
                finish,
                "--ai-used",
                "true",
                "--exposed",
                "true",
                "--assisted",
                "true",
                "--note",
                "crashed after AI use",
            ]
        )
        == 0
    )
    output = places.rows / f"{sid}.agent.json"
    imported = json.loads(output.read_text())
    assert [r["seq"] for r in imported] == [0, 1, 2, 3]
    assert {r["source"] for r in imported} == {"agent-capture"}
    assert calls == ["a.jsonl", "b.jsonl"]
    archive = places.rows / f"{sid}.transcripts"
    assert sorted(p.name for p in archive.iterdir()) == ["a.jsonl", "b.jsonl"]
    for name in ("a.jsonl", "b.jsonl"):
        assert (archive / name).read_bytes() == (folder / name).read_bytes()
    prepared = json.loads((places.rows / f"{sid}.prepared.json").read_text())
    assert prepared["transcripts"] == ["a.jsonl", "b.jsonl"]
    labels_before = places.labels.read_bytes()
    output_before = output.read_bytes()
    command = ["import-agent", "dry", sid] if dry else ["import-agent", str(order)]
    assert session.main(command) == 0
    assert output.read_bytes() == output_before
    assert places.labels.read_bytes() == labels_before
    assert len(session.read_labels(places.labels)) == 1
    assert (
        session.read_labels(places.labels)[0]["operatorNote"] == "crashed after AI use"
    )


@pytest.mark.parametrize("dry", [False, True])
@pytest.mark.parametrize("failure", ["exit", "invalid-json", "missing", "oserror"])
def test_failed_agent_import_keeps_label_clears_pending_and_can_retry(
    tmp_path, session, monkeypatch, capsys, dry, failure
):
    places, sid, order, folder = prepared_agent(
        session, tmp_path, monkeypatch, "cli-agent-hooks", dry
    )
    if failure == "missing":
        for transcript in folder.iterdir():
            transcript.unlink()

    def failed_import(args, **kwargs):
        if failure == "oserror":
            raise OSError("import command unavailable")
        return subprocess.CompletedProcess(
            args,
            1 if failure == "exit" else 0,
            "invalid JSON",
            "Traceback: child failure",
        )

    monkeypatch.setattr(session.subprocess, "run", failed_import)
    output = places.rows / f"{sid}.agent.json"
    output.write_text("[]\n")
    assert (
        session.main(
            [
                "finish",
                "dry" if dry else str(order),
                "--ai-used",
                "true",
                "--exposed",
                "true",
                "--assisted",
                "true",
            ]
        )
        == 1
    )
    stderr = capsys.readouterr().err
    retry = f"import-agent dry {sid}" if dry else f"import-agent {order}"
    assert retry in stderr and "agent import failed" in stderr
    assert "Traceback" not in stderr
    assert not places.current.exists()
    assert len(session.read_labels(places.labels)) == 1
    assert output.read_text() == "[]\n"
    before = places.labels.read_bytes()
    path = folder / "retry.jsonl"
    path.write_text("{}\n")
    os.utime(path, (102, 102))
    monkeypatch.setattr(
        session.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, "[]", ""),
    )
    command = ["import-agent", "dry", sid] if dry else ["import-agent", str(order)]
    assert session.main(command) == 0
    assert places.labels.read_bytes() == before


@pytest.mark.parametrize("scenario", ["cli-agent-no-hooks", "probe-agent-closed-file"])
def test_no_hooks_archives_raw_transcripts_without_importing(
    tmp_path, session, monkeypatch, scenario
):
    places, sid, _, _ = prepared_agent(session, tmp_path, monkeypatch, scenario, True)

    def forbidden_import(*args, **kwargs):
        pytest.fail("no-hooks transcripts must never be imported")

    monkeypatch.setattr(session.subprocess, "run", forbidden_import)
    session.cmd_finish(places, "true", "true", "true", "external agent without hooks")
    assert not places.current.exists()
    assert not (places.rows / f"{sid}.agent.json").exists()
    assert len(list((places.rows / f"{sid}.transcripts").glob("*.jsonl"))) == 2
    prepared = json.loads((places.rows / f"{sid}.prepared.json").read_text())
    assert prepared["transcripts"] == ["a.jsonl", "b.jsonl"]
    assert session.main(["import-agent", "dry", sid]) == 0


def test_finish_without_pending_session_is_a_clean_refusal(
    tmp_path, session, monkeypatch, capsys
):
    monkeypatch.setenv("CALIBRATION_HOME", str(tmp_path / "home"))
    assert (
        session.main(
            [
                "finish",
                "1",
                "--ai-used",
                "false",
                "--exposed",
                "false",
                "--assisted",
                "false",
            ]
        )
        == 1
    )
    error = capsys.readouterr().err
    assert "no prepared session" in error and "Traceback" not in error


@pytest.mark.parametrize(
    ("used", "exposed", "assisted", "message"),
    [
        ("true", "false", "false", "aiUsed=true requires"),
        ("true", "true", "false", "aiUsed=true requires"),
        ("true", "false", "true", "aiUsed=true requires"),
        ("false", "false", "true", "assisted=true requires"),
        ("maybe", "true", "true", "aiUsed must be"),
        ("false", "maybe", "false", "exposed must be"),
        ("false", "false", "maybe", "assisted must be"),
    ],
)
def test_finish_refuses_invalid_labels_without_changing_pending_session(
    tmp_path, session, used, exposed, assisted, message
):
    places = session.Places(tmp_path / "home", dry=True)
    places.current.parent.mkdir(parents=True)
    pending = '{"sessionId":"s1","scenario":"no-ai","rep":1}'
    places.current.write_text(pending)
    with pytest.raises(session.Refused, match=message):
        session.cmd_finish(places, used, exposed, assisted, "")
    assert places.current.read_text() == pending
    assert not places.labels.exists()


@pytest.mark.parametrize("missing", ["--exposed", "--assisted"])
def test_finish_requires_exposure_and_assistance(missing):
    options = {"--ai-used": "false", "--exposed": "false", "--assisted": "false"}
    del options[missing]
    args = [arg for pair in options.items() for arg in pair]
    result = run_script("calibration_session.py", "finish", "dry", *args)
    assert result.returncode == 2
    assert missing in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("scenario", [NO_AI, *AI_ROUTES, *BENIGN, *PROBES])
def test_agent_settings_exports_and_version_are_scoped_to_agent_sets(
    tmp_path, session, monkeypatch, scenario
):
    places = session.Places(tmp_path / "home", dry=True)
    session.cmd_setup(places, install=False)
    task = tmp_path / "task"
    task.mkdir()
    monkeypatch.setattr(session, "TASK", task)
    monkeypatch.setattr(session, "code_cli", lambda: "code")
    monkeypatch.setattr(session, "BUILTIN_COPILOT", tmp_path / "absent.json")
    monkeypatch.setattr(session.shutil, "which", lambda command: command)
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "{}", "")

    monkeypatch.setattr(session.subprocess, "run", run)
    session.fresh_workspace(places, "s1", scenario)
    session.record_environment(places, "s1", scenario, session.installed_instrument())
    hooked = scenario in {"cli-agent-hooks", "probe-agent-explain"}
    agent = hooked or scenario in {"cli-agent-no-hooks", "probe-agent-closed-file"}
    assert {"cli-agent-hooks", "probe-agent-explain"} == session.HOOKED
    assert (
        session.HOOKED
        | {
            "cli-agent-no-hooks",
            "probe-agent-closed-file",
        }
        == session.AGENT
    )
    assert (places.work / ".claude" / "settings.json").exists() is hooked
    shell = (places.home / "session.sh").read_text()
    assert ("export STUDY_PARTICIPANT=" in shell) is hooked
    assert ("STUDY_SESSION=s1" in shell) is hooked
    assert (["claude", "--version"] in calls) is agent


@pytest.mark.parametrize("dry", [False, True])
@pytest.mark.parametrize("scenario", ["cli-agent-hooks", "probe-agent-explain"])
def test_prepare_exports_hook_endpoint_and_finish_keeps_last_event(
    tmp_path, session, monkeypatch, dry, scenario
):
    places = session.Places(tmp_path / "home", dry=dry)
    session.cmd_setup(places, install=False)
    (places.home / "tern-installed.sha256").write_text(
        json.dumps(session.installed_instrument())
    )
    task = tmp_path / "task"
    task.mkdir()
    plan = tmp_path / "plan.md"
    plan.write_text(f"## 8. Scenario scripts\n\n**{scenario}**\n1. Use the agent.\n")
    monkeypatch.setattr(session, "PLAN", plan)
    monkeypatch.setattr(session, "TASK", task)
    monkeypatch.setattr(session, "check_freeze", lambda: None)
    monkeypatch.setattr(session, "code_cli", lambda: "code")
    monkeypatch.setattr(session, "cmd_import_agent", lambda *args: None)

    def receiver(places, sid):
        (places.rows / f"{sid}.hook.port").write_text("12345\n")
        (places.rows / f"{sid}.hook.pid").write_text("12345\n")
        (places.rows / f"{sid}.hook.log").write_text("")
        return 12345

    def stop_receiver(pid, sig):
        assert pid == 12345
        for path in places.rows.glob("*.hook.port"):
            path.unlink()

    monkeypatch.setattr(session, "start_hook_receiver", receiver)
    monkeypatch.setattr(session.os, "kill", stop_receiver)
    monkeypatch.setattr(session, "save_task_evidence", lambda *args: None)
    monkeypatch.setattr(session, "cmd_verify", lambda *args: 0)

    def fake_receiver(places, sid):
        (places.rows / f"{sid}.hook.log").touch()
        return 43210

    monkeypatch.setattr(session, "start_hook_receiver", fake_receiver)
    monkeypatch.setattr(
        session.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, "{}", ""),
    )
    sid = "hook-session"
    try:
        session.cmd_prepare(places, sid, scenario, 1, False, None)
        shell = (places.home / "session.sh").read_text()
        endpoint = next(
            line.split("=", 1)[1]
            for line in shell.splitlines()
            if line.startswith("export STUDY_INGEST_ENDPOINT=")
        )
        assert endpoint.startswith("http://127.0.0.1:")
        assert endpoint.endswith("/ingest/events")
        first = [
            event(sid, "tool_call", 2),
            event(sid, "agent_turn", 0, {"content": "old"}),
            {**event(sid, "agent_turn", 0), "source": "another-agent"},
        ]
        last = event(sid, "agent_turn", 0, {"content": "replacement"})
        with (places.rows / f"{sid}.hook-batches.jsonl").open("w") as handle:
            for batch in (first, [last, event(sid, "tool_call", 1)]):
                handle.write(
                    json.dumps(
                        {
                            "receivedAt": "2026-11-17T10:00:00Z",
                            "body": {"events": batch, "source": "agent-capture"},
                        }
                    )
                    + "\n"
                )
        append = session.append_label

        def label_after_stopping(path, row):
            assert not (places.rows / f"{sid}.hook.port").exists()
            assert (places.rows / f"{sid}.hook.json").exists()
            append(path, row)

        monkeypatch.setattr(session, "append_label", label_after_stopping)
        session.cmd_finish(places, "true", "true", "true", "tested live delivery")
    finally:
        if (places.rows / f"{sid}.hook.pid").exists():
            session.finish_hook_receiver(places, sid)
    rows = json.loads((places.rows / f"{sid}.hook.json").read_text())
    assert [row["seq"] for row in rows] == [0, 0, 1, 2]
    by_key = {(row["source"], row["seq"]): row for row in rows}
    assert by_key[("agent-capture", 0)] == {**last, "source": "agent-capture"}
    assert ("another-agent", 0) in by_key
    raw = (places.rows / f"{sid}.hook-batches.jsonl").read_text().splitlines()
    assert len(raw) == 2
    assert all(json.loads(line)["receivedAt"] for line in raw)
    assert not (places.rows / f"{sid}.hook.pid").exists()
    assert (places.rows / f"{sid}.hook.log").exists()
    assert session.read_labels(places.labels)[0]["assisted"] == "true"
    sheet = session.operator_sheet(places, sid, scenario, 1)
    assert "--exposed true|false --assisted true|false" in sheet


def test_hook_finish_without_deliveries_tolerates_gone_receiver(
    tmp_path, session, monkeypatch, capsys
):
    places = session.Places(tmp_path / "home", dry=True)
    places.rows.mkdir(parents=True)
    (places.rows / "s1.hook.pid").write_text("12345\n")

    def gone(pid, sig):
        raise ProcessLookupError

    monkeypatch.setattr(session.os, "kill", gone)
    session.finish_hook_receiver(places, "s1")
    assert json.loads((places.rows / "s1.hook.json").read_text()) == []
    assert "warning: no live hook events" in capsys.readouterr().err


def test_check_dry_uses_live_events_and_excludes_batches_and_overlapping_imports(
    tmp_path, session, monkeypatch
):
    places = session.Places(tmp_path / "home", dry=True)
    places.rows.mkdir(parents=True)
    for name in (
        "s1.jsonl",
        "s1.hook-batches.jsonl",
        "s1.hook.json",
        "s1.agent.json",
        "s2.agent.json",
    ):
        (places.rows / name).write_text("[]\n")
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(session.subprocess, "run", run)
    assert session.cmd_check_dry(places) == 0
    args = calls[0]
    inputs = args[args.index("--rows") + 1 : args.index("--labels")]
    assert {Path(path).name for path in inputs} == {
        "s1.jsonl",
        "s1.hook.json",
        "s2.agent.json",
    }


# --- blinded post-session checks -------------------------------------------


def healthy_capture_rows(session_id, *extra, minutes=10):
    rows = session_rows(session_id, *extra)
    start = dt.datetime(2026, 11, 17, 10, tzinfo=dt.UTC)
    for index, row in enumerate(rows):
        stamp = start + dt.timedelta(minutes=minutes * index / (len(rows) - 1))
        row["ts"] = stamp.isoformat()
    return rows


@pytest.fixture
def finished_session(tmp_path, session, monkeypatch):
    def make(scenario="no-ai", note="", dry=True):
        places = session.Places(tmp_path / "home", dry=dry)
        places.rows.mkdir(parents=True, exist_ok=True)
        order = next(n for n in range(1, 32) if session.session_for(n)[1] == scenario)
        sid, _, rep = session.session_for(order)
        if dry:
            sid = f"dry-{scenario}-1117100000"
        label = {
            "sessionId": sid,
            "scenario": scenario,
            "aiUsed": "false",
            "exposed": "false",
            "assisted": "false",
            "rep": str(rep),
            "operatorNote": note,
        }
        session.append_label(places.labels, label)
        (places.rows / f"{sid}.prepared.json").write_text(json.dumps(label))
        write_jsonl(
            places.rows / f"operator_unspecified_{sid}.jsonl",
            healthy_capture_rows(sid),
        )
        (places.rows / f"{sid}.settings.json").write_text(
            json.dumps(session.workspace_settings(sid, scenario, places.rows))
        )
        hashes = session.installed_instrument()
        (places.rows / f"{sid}.env.txt").write_text(
            session.instrument_record(hashes) + "vscode@1.0\n"
        )
        (places.home / "tern-installed.sha256").write_text(json.dumps(hashes))
        (places.rows / f"{sid}.inventory.diff").write_text("-pass\n+return 1\n")
        (places.rows / f"{sid}.pytest.txt").write_text("2 failed, 3 passed in 0.01s\n")
        plan = tmp_path / "plan.md"
        plan.write_text(
            f"## 8. Scenario scripts\n\n**{scenario}**\n1. Test procedure.\n\n"
            "**other-scenario**\nPRIVATE_OTHER_SCENARIO\n\n## 9. Next section\n"
        )
        monkeypatch.setattr(session, "PLAN", plan)
        monkeypatch.setenv("CALIBRATION_HOME", str(places.home))
        return places, sid, order

    return make


def verification(places, sid):
    report = json.loads((places.rows / f"{sid}.verify.json").read_text())
    return {check["check"]: check for check in report["checks"]}


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("scenario", ["no-ai", "cli-agent-hooks"])
def test_verify_outputs_and_review_bundle_are_blinded_to_signals(
    tmp_path, session, finished_session, monkeypatch, capsys, reviewer, scenario
):
    places, sid, _ = finished_session(scenario)
    secret = "INSTRUMENT_SIGNAL_SECRET"
    signals = [
        ("edit_burst", {"origin": "ai", "text": "PRIVATE_AI_EDIT_731"}),
        ("clipboard_paste", {"text": "PRIVATE_CLIPBOARD_842"}),
        ("ai_suggestion", {"action": "accepted", "text": "PRIVATE_SUGGESTION_953"}),
        ("agent_turn", {"response": "PRIVATE_AGENT_TURN_164"}),
        ("tool_call", {"arguments": "PRIVATE_TOOL_CALL_275"}),
    ]
    rows = healthy_capture_rows(sid, *signals)
    # Only auditCapture is allowed through from an environment snapshot.
    rows[1]["payload"]["extensionVersions"] = secret
    rows[0]["payload"] = {"text": secret}
    rows[-1]["payload"] = {"text": secret}
    write_jsonl(places.rows / f"operator_unspecified_{sid}.jsonl", rows)

    forbidden = [
        places.rows / f"{sid}.hook.json",
        places.rows / f"{sid}.agent.json",
    ]
    for path in forbidden:
        path.write_text(secret)
    archive = places.rows / f"{sid}.transcripts"
    archive.mkdir()
    transcript = archive / "chat.jsonl"
    transcript.write_text(secret)
    forbidden.append(transcript)
    # A batch is counted as a line; its body is never parsed or exposed.
    (places.rows / f"{sid}.hook-batches.jsonl").write_text(secret + "\n\n")
    original_open = Path.open

    def blinded_open(path, *args, **kwargs):
        assert path not in forbidden, f"unblinded file read: {path.name}"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", blinded_open)
    executable = tmp_path / f"fake-{reviewer}"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, pathlib, sys\n"
        "assert sys.stdin.read() == ''\n"
        "assert sys.argv[-1] == os.environ['EXPECTED_REVIEW_PROMPT']\n"
        "files = {p.name: p.read_text() for p in pathlib.Path.cwd().iterdir()}\n"
        "pathlib.Path(os.environ['BUNDLE_CAPTURE']).write_text(json.dumps(files))\n"
        "reply = json.dumps({'verdict': 'ok', 'concerns': [], "
        "'suggestedDeviation': None})\n"
        "if '-o' in sys.argv:\n"
        "    assert sys.argv[1:8] == ['exec', '--skip-git-repo-check', '-s', "
        "'read-only', '-m', 'gpt-6.1-sol', '-o']\n"
        "    pathlib.Path(sys.argv[sys.argv.index('-o') + 1]).write_text(reply)\n"
        "else:\n"
        "    assert sys.argv[1:4] == ['-p', '--model', 'sonnet']\n"
        "    print(reply)\n"
    )
    executable.chmod(0o700)
    captured = tmp_path / "captured-bundle.json"
    monkeypatch.setenv("BUNDLE_CAPTURE", str(captured))
    monkeypatch.setenv("EXPECTED_REVIEW_PROMPT", session.REVIEW_PROMPT)
    monkeypatch.setenv(f"CALIBRATION_{reviewer.upper()}", str(executable))
    monkeypatch.setenv("CALIBRATION_REVIEWER", reviewer)
    labels_before = places.labels.read_bytes()
    assert session.main(["verify", "dry", sid]) == 0
    assert places.labels.read_bytes() == labels_before
    files = json.loads(captured.read_text())
    assert json.loads((places.rows / f"{sid}.review.json").read_text()) == {
        "verdict": "ok",
        "concerns": [],
        "suggestedDeviation": None,
    }
    expected = {
        "scenario.md",
        "label.json",
        "verify.json",
        "inventory.diff",
        "pytest.txt",
    }
    if scenario in session.AGENT:
        expected.add("transcripts.txt")
        assert files["transcripts.txt"] == f"chat.jsonl\t{len(secret)} bytes\n"
        assert verification(places, sid)["hooks"]["count"] == 1
        assert verification(places, sid)["transcripts"]["count"] == 1
    assert set(files) == expected
    assert "PRIVATE_OTHER_SCENARIO" not in json.dumps(files)
    checks = verification(places, sid)
    assert checks["capture"]["status"] == "ok"
    assert checks["duration"]["status"] == "ok"
    assert checks["sensors"]["status"] == "ok"
    assert checks["settings"]["status"] == "ok"
    assert checks["reviewer"]["status"] == "ok"
    assert checks["task"]["status"] == "ok"
    assert checks["task"]["counts"] == {"failed": 2, "passed": 3}
    output = capsys.readouterr()
    assert output.out.rstrip().endswith(session.DEVIATIONS)
    outputs = {
        "stdout": output.out,
        "stderr": output.err,
        "verify.json": (places.rows / f"{sid}.verify.json").read_text(),
        "review.json": (places.rows / f"{sid}.review.json").read_text(),
        **{f"bundle/{name}": content for name, content in files.items()},
    }
    signal_secrets = [secret, '"origin": "ai"']
    for kind, payload in signals:
        signal_secrets.append(kind)
        signal_secrets.extend(value for value in payload.values() if value != "ai")
    for name, content in outputs.items():
        for value in signal_secrets:
            assert value not in content, f"signal leaked into {name}: {value}"


@pytest.mark.parametrize("dry", [False, True])
def test_verify_healthy_session_passes_all_checks(session, finished_session, dry):
    places, sid, _ = finished_session(dry=dry)

    assert session.cmd_verify(places, sid, "none") == 0

    checks = verification(places, sid)
    assert {"capture", "duration", "sensors", "settings", "drift"} <= checks.keys()
    assert all(check["status"] == "ok" for check in checks.values())
    assert checks["duration"]["detail"] == "10.0 minutes"
    if not dry:
        assert checks["instrument"]["status"] == "ok"


@pytest.mark.parametrize(
    ("failure", "detail"),
    [
        ("no-file", "no TERN rows"),
        ("empty-file", "no TERN rows"),
        ("missing-end", "no session_end"),
        ("sequence-gap", "1 sequence gap(s)"),
        ("aiLifecycle", "capture switch aiLifecycle off"),
        ("editBursts", "capture switch editBursts off"),
        ("clipboard", "capture switch clipboard off"),
    ],
)
def test_capture_health_failures_are_saved(session, finished_session, failure, detail):
    places, sid, _ = finished_session()
    path = places.rows / f"operator_unspecified_{sid}.jsonl"
    rows = healthy_capture_rows(sid)
    if failure == "no-file":
        path.unlink()
    else:
        if failure == "empty-file":
            rows = []
        elif failure == "missing-end":
            rows.pop()
        elif failure == "sequence-gap":
            rows[-1]["seq"] += 1
        else:
            rows[1]["payload"]["auditCapture"][failure] = False
        write_jsonl(path, rows)

    assert session.cmd_verify(places, sid, "none") == 1

    check = verification(places, sid)["capture"]
    assert check["status"] == "fail"
    assert detail in check["detail"]


@pytest.mark.parametrize(
    ("warning", "check_name", "detail"),
    [
        ("sensor-errors", "sensors", "2 sensor error(s)"),
        ("short-session", "duration", "4.5 minutes"),
        ("foreign-rows", "files", "1 row(s) of other sessions in the same file"),
    ],
)
def test_capture_health_warnings_do_not_fail_verification(
    session, finished_session, capsys, warning, check_name, detail
):
    places, sid, _ = finished_session()
    secret = "PRIVATE_INFRASTRUCTURE_PAYLOAD_386"
    if warning == "sensor-errors":
        rows = healthy_capture_rows(
            sid,
            ("behavior_sensor_error", {"message": secret}),
            ("behavior_sensor_error", {"message": secret}),
        )
    elif warning == "short-session":
        rows = healthy_capture_rows(sid, minutes=4.5)
    else:
        rows = healthy_capture_rows(sid)
        foreign = event("other-session", "tool_call", 100, {"text": secret})
        foreign["ts"] = "2000-01-01T00:00:00Z"
        rows.insert(1, foreign)
    write_jsonl(places.rows / f"operator_unspecified_{sid}.jsonl", rows)

    assert session.cmd_verify(places, sid, "none") == 0

    checks = verification(places, sid)
    assert checks["capture"]["status"] == "ok"
    assert checks[check_name]["status"] == "warn"
    assert checks[check_name]["detail"] == detail
    if warning == "foreign-rows":
        assert checks["duration"]["detail"] == "10.0 minutes"
        assert checks["duration"]["status"] == "ok"
    output = capsys.readouterr()
    assert secret not in output.out + output.err
    assert secret not in (places.rows / f"{sid}.verify.json").read_text()


def test_settings_check_fails_and_names_differing_keys(session, finished_session):
    places, sid, _ = finished_session()
    path = places.rows / f"{sid}.settings.json"
    settings = json.loads(path.read_text())
    settings["chat.disableAIFeatures"] = False
    del settings["tern.session.id"]
    settings["unexpected.setting"] = "PRIVATE_SETTING_VALUE_497"
    path.write_text(json.dumps(settings))

    assert session.cmd_verify(places, sid, "none") == 1

    assert verification(places, sid)["settings"] == {
        "check": "settings",
        "status": "fail",
        "detail": "differ: chat.disableAIFeatures, tern.session.id, unexpected.setting",
    }


def test_environment_drift_compares_later_real_session_to_first(
    session, finished_session
):
    places, sid, order = finished_session(dry=False)
    assert order > 2
    current = places.rows / f"{sid}.env.txt"
    baseline = current.read_text()
    first_sid = session.session_for(1)[0]
    previous_sid = session.session_for(order - 1)[0]
    (places.rows / f"{first_sid}.env.txt").write_text(baseline)
    changed = baseline.replace("vscode@1.0", "vscode@2.0")
    (places.rows / f"{previous_sid}.env.txt").write_text(changed)
    current.write_text(changed)

    assert session.cmd_verify(places, sid, "none") == 0

    checks = verification(places, sid)
    assert checks["drift"] == {
        "check": "drift",
        "status": "warn",
        "detail": "versions differ from the first session: vscode@1.0, vscode@2.0",
    }
    assert checks["instrument"]["status"] == "ok"

    current.write_text(baseline)
    assert session.cmd_verify(places, sid, "none") == 0
    assert verification(places, sid)["drift"]["status"] == "ok"


def test_environment_drift_fails_real_installed_hash_mismatch(
    session, finished_session
):
    places, sid, _ = finished_session(dry=False)
    saved = json.loads((places.home / "tern-installed.sha256").read_text())
    path = places.rows / f"{sid}.env.txt"
    path.write_text(path.read_text().replace(saved["installedSha256"], "0" * 64))

    assert session.cmd_verify(places, sid, "none") == 1

    assert verification(places, sid)["instrument"] == {
        "check": "instrument",
        "status": "fail",
        "detail": "installed TERN differs from setup",
    }


@pytest.mark.parametrize(
    "scenario", list(load_script("calibration_session").REQUIRED_NOTE)
)
@pytest.mark.parametrize("note", ["", "   ", "recorded: http://example.test/answer"])
def test_required_notes_warn_without_failing(session, finished_session, scenario, note):
    places, sid, _ = finished_session(scenario, note)
    assert session.cmd_verify(places, sid, "none") == 0
    checks = verification(places, sid)
    assert checks["note"]["status"] == ("ok" if note.strip() else "warn")
    if scenario in session.HOOKED:
        assert checks["hooks"]["status"] == "warn"
    if scenario in session.AGENT:
        assert checks["transcripts"]["status"] == "warn"


def test_stackoverflow_note_requires_url(session, finished_session):
    places, sid, _ = finished_session("benign-stackoverflow-paste", "answer 123")
    assert session.cmd_verify(places, sid) == 0
    assert verification(places, sid)["note"]["status"] == "warn"


@pytest.mark.parametrize(
    "failure", ["missing", "duplicate", "inconsistent", "malformed", "rep", "scenario"]
)
def test_bad_label_is_a_saved_failure(session, finished_session, capsys, failure):
    places, sid, _ = finished_session()
    if failure == "missing":
        places.labels.unlink()
    elif failure == "malformed":
        places.labels.write_text("not,a,label\n")
    else:
        labels = session.read_labels(places.labels)
        if failure == "duplicate":
            labels *= 2
        elif failure == "inconsistent":
            labels[0]["assisted"] = "true"
        elif failure == "rep":
            labels[0]["rep"] = "999"
        else:
            labels[0]["scenario"] = "retype"
        with places.labels.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, session.LABEL_HEADER)
            writer.writeheader()
            writer.writerows(labels)
    assert session.main(["verify", "dry", sid, "--reviewer", "none"]) == 1
    assert verification(places, sid)["label"]["status"] == "fail"
    output = capsys.readouterr()
    assert "Traceback" not in output.out + output.err
    assert output.out.rstrip().endswith(session.DEVIATIONS)


@pytest.mark.parametrize("dry", [False, True])
def test_verify_command_resolves_sessions_and_missing_task_is_information(
    session, finished_session, dry
):
    places, sid, order = finished_session(dry=dry)
    (places.rows / f"{sid}.pytest.txt").unlink()
    command = ["verify", "dry", sid] if dry else ["verify", str(order)]
    assert session.main(command) == 0
    checks = verification(places, sid)
    assert checks["task"]["status"] == "ok"
    assert checks["task"]["counts"] == {}


@pytest.mark.parametrize("reviewer", ["codex", "claude"])
@pytest.mark.parametrize("failure", ["missing", "timeout", "exit", "raw", "concern"])
def test_reviewer_errors_are_warnings(
    session, finished_session, monkeypatch, capsys, reviewer, failure
):
    places, sid, _ = finished_session()

    def run(args, **kwargs):
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["timeout"] == 300
        if failure == "missing":
            raise FileNotFoundError
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 300, output="SECRET")
        reply = (
            "not json"
            if failure == "raw"
            else json.dumps(
                {
                    "verdict": "concern",
                    "concerns": ["note unclear"],
                    "suggestedDeviation": None,
                }
            )
        )
        if reviewer == "codex":
            Path(args[args.index("-o") + 1]).write_text(reply)
        return subprocess.CompletedProcess(
            args, 1 if failure == "exit" else 0, reply, ""
        )

    monkeypatch.setattr(session.subprocess, "run", run)
    assert session.cmd_verify(places, sid, reviewer) == 0
    assert verification(places, sid)["reviewer"]["status"] == "warn"
    if failure == "raw":
        assert json.loads((places.rows / f"{sid}.review.json").read_text()) == {
            "raw": "not json"
        }
    assert "SECRET" not in capsys.readouterr().out


def test_finish_captures_task_and_passes_reviewer(
    tmp_path, session, finished_session, monkeypatch
):
    places, sid, _ = finished_session()
    current = places.rows / f"{sid}.prepared.json"
    places.current.write_bytes(current.read_bytes())
    places.labels.unlink()
    task = tmp_path / "task"
    task.mkdir()
    (task / "inventory.py").write_text("pass\n")
    places.work.mkdir()
    (places.work / "inventory.py").write_text("def count():\n    return 1\n")
    monkeypatch.setattr(session, "TASK", task)
    calls = []

    def run(args, **kwargs):
        assert args == [sys.executable, "-m", "pytest", "-q"]
        assert kwargs["cwd"] == places.work
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert not places.current.exists()
        assert len(session.read_labels(places.labels)) == 1
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "2 failed, 4 passed in 0.01s\n", "")

    monkeypatch.setattr(session.subprocess, "run", run)
    reviewers = []

    def review(*args):
        reviewers.append(args[-1])
        return "ok", "fake review"

    monkeypatch.setattr(session, "blinded_review", review)
    assert (
        session.main(
            [
                "finish",
                "dry",
                "--ai-used",
                "false",
                "--exposed",
                "false",
                "--assisted",
                "false",
                "--reviewer",
                "codex",
            ]
        )
        == 0
    )
    assert len(calls) == 1
    assert reviewers == ["codex"]
    assert "+def count():" in (places.rows / f"{sid}.inventory.diff").read_text()
    assert verification(places, sid)["task"]["counts"] == {"failed": 2, "passed": 4}
    monkeypatch.setenv("CALIBRATION_REVIEWER", "claude")
    assert session.cmd_verify(places, sid, "none") == 0
    assert reviewers == ["codex"]
    assert len(calls) == 1  # Rechecking never reruns the workspace task.


@pytest.mark.parametrize(
    "scenario",
    [
        "browser-paste",
        "retype",
        "probe-menu-paste",
        "benign-stackoverflow-paste",
        "benign-formatter",
        "benign-rename",
        "probe-word-accept",
        "probe-rename-many",
        "probe-format-large",
    ],
)
def test_required_notes_warn_on_whitespace_then_accept_evidence(
    session, finished_session, scenario
):
    places, sid, _ = finished_session(scenario)
    row = session.read_labels(places.labels)[0]
    for note, status in [
        ("  ", "warn"),
        ("http://example.test: procedure details", "ok"),
    ]:
        row["operatorNote"] = note
        with places.labels.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, session.LABEL_HEADER)
            writer.writeheader()
            writer.writerow(row)
        assert session.cmd_verify(places, sid) == 0
        assert verification(places, sid)["note"]["status"] == status


def test_missing_agent_evidence_warns_without_reading_payloads(
    session, finished_session
):
    places, sid, _ = finished_session("cli-agent-hooks")
    assert session.cmd_verify(places, sid) == 0
    checks = verification(places, sid)
    assert checks["hooks"]["status"] == "warn"
    assert checks["hooks"]["count"] == 0
    assert checks["transcripts"]["status"] == "warn"
    assert checks["transcripts"]["count"] == 0


@pytest.mark.parametrize("failure", ["missing", "timeout"])
def test_task_execution_errors_remain_information(
    tmp_path, session, finished_session, monkeypatch, failure
):
    places, sid, _ = finished_session()
    monkeypatch.setattr(session, "TASK", tmp_path / "missing-task")

    def run(args, **kwargs):
        if failure == "missing":
            raise FileNotFoundError
        raise subprocess.TimeoutExpired(args, 300)

    monkeypatch.setattr(session.subprocess, "run", run)
    session.save_task_evidence(places, sid)
    assert session.cmd_verify(places, sid) == 0
    assert verification(places, sid)["task"]["status"] == "ok"
    assert verification(places, sid)["task"]["counts"] == {}


def test_freeze_without_a_commit_records_that_it_is_hash_only(tmp_path):
    freeze = load_script("freeze_calibration")
    exp, manifest = fake_experiment(tmp_path), tmp_path / "freeze.json"
    root = tmp_path / "repo"
    for path in freeze.PROCEDURE_PATHS:
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(f"# {path}\n")

    def dirty_git(*args):
        return b"scripts/calibration_session.py\n"

    refused = freeze.write(exp, manifest, CLEAN_BUILD, root=root, run_git=dirty_git)
    assert any("commit them first" in p for p in refused)
    assert not manifest.exists()

    assert (
        freeze.write(
            exp, manifest, CLEAN_BUILD, root=root, run_git=dirty_git, uncommitted=True
        )
        == []
    )
    body = json.loads(manifest.read_text())
    assert body["procedureCommitted"] is False
    assert "hashes" not in body["note"] or "sha256" in body["note"]
    assert set(body["procedure"]) == set(freeze.PROCEDURE_PATHS)
