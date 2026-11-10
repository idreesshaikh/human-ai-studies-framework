"""Verification must not report success for interrupted or failed checks."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def verifier(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "check_demo", ROOT / "scripts/check_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_output", lambda _args: "test-version")
    monkeypatch.setattr(module, "_source_hash", lambda: "synthetic-source-hash")
    return module


def test_interrupted_first_check_invalidates_an_old_success(
    verifier, tmp_path, monkeypatch
):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"complete": True, "passed": True}))
    monkeypatch.setattr(sys, "argv", ["check_demo", "--artifacts", str(tmp_path)])

    def interrupted(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(verifier.subprocess, "run", interrupted)
    with pytest.raises(KeyboardInterrupt):
        verifier.main()
    saved = json.loads(report.read_text())
    assert saved["complete"] is False and saved["passed"] is False
    assert saved["checks"] == []


@pytest.mark.parametrize("missing_executable", [False, True])
def test_failed_gate_cannot_be_hidden_by_later_successes(
    verifier, tmp_path, monkeypatch, missing_executable
):
    monkeypatch.setattr(sys, "argv", ["check_demo", "--artifacts", str(tmp_path)])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1 and missing_executable:
            raise FileNotFoundError("synthetic missing tool")
        kwargs["stdout"].write("synthetic gate output\n")
        return subprocess.CompletedProcess(command, 1 if len(calls) == 1 else 0)

    monkeypatch.setattr(verifier.subprocess, "run", run)
    assert verifier.main() == 1
    saved = json.loads((tmp_path / "report.json").read_text())
    assert saved["complete"] is True and saved["passed"] is False
    assert len(saved["checks"]) == 7
    assert saved["checks"][0]["returncode"] == (127 if missing_executable else 1)
    assert all(row["returncode"] == 0 for row in saved["checks"][1:])
