#!/usr/bin/env python3
"""Run the offline demo gates and record reproducible verification metadata.

Run with the synced workspace interpreter:
    uv run --no-sync python scripts/check_demo.py

No live model, literature service, deployment or participant database is used.
The browser gate creates its own disposable backend. Logs and the report stay
under the ignored .research-artifacts directory unless --artifacts is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git") or "git"


def _output(args: list[str]) -> str:
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _source_hash() -> str:
    """Hash tracked and non-ignored new files, including uncommitted changes."""
    result = subprocess.run(
        [GIT, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    digest = hashlib.sha256()
    for name in sorted(set(result.stdout.split(b"\0")) - {b""}):
        path = ROOT / os.fsdecode(name)
        if not path.is_file():
            continue
        digest.update(name + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, help="Directory for logs/report.json")
    args = parser.parse_args()
    started = datetime.now(UTC)
    artifacts = args.artifacts or (
        ROOT
        / ".research-artifacts"
        / "demo-readiness"
        / started.strftime("%Y%m%dT%H%M%SZ")
    )
    artifacts = artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    checks = [
        ("python-lint", [python, "-m", "ruff", "check", "."]),
        ("workspace-config", [python, "scripts/check_workspace_config.py"]),
        (
            "python-tests",
            [
                python,
                "-m",
                "pytest",
                "--cov",
                "--cov-report=term-missing",
                "--cov-fail-under=79",
                "-q",
                "--tb=short",
            ],
        ),
        (
            "metrics-coverage",
            [
                python,
                "-m",
                "coverage",
                "report",
                "--include=metrics/src/*",
                "--fail-under=95",
            ],
        ),
        ("extension", ["npm", "--prefix", "extension", "run", "check"]),
        ("platform-and-browser", ["npm", "--prefix", "platform", "run", "check"]),
        (
            "documentation",
            [
                python,
                "-m",
                "mkdocs",
                "build",
                "--strict",
                "-f",
                "documentation/mkdocs.yml",
            ],
        ),
    ]
    report = {
        "startedAt": started.isoformat(),
        "commit": _output(["git", "rev-parse", "HEAD"]),
        "branch": _output(["git", "branch", "--show-current"]),
        "dirty": bool(_output(["git", "status", "--porcelain"])),
        "sourceSha256": _source_hash(),
        "python": sys.version,
        "node": _output(["node", "--version"]),
        "npm": _output(["npm", "--version"]),
        "checks": [],
        "complete": False,
        "passed": False,
        "scope": (
            "Offline software verification with synthetic fixtures; "
            "no empirical validity claim."
        ),
    }
    # Reusing a directory must invalidate its old success before any check runs.
    (artifacts / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    for name, command in checks:
        print(f"Running {name}...", flush=True)
        log = artifacts / f"{name}.log"
        tick = time.monotonic()
        with log.open("w") as stream:
            try:
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                code = result.returncode
            except OSError as exc:
                stream.write(str(exc) + "\n")
                code = 127
        report["checks"].append(
            {
                "name": name,
                "command": command,
                "returncode": code,
                "seconds": round(time.monotonic() - tick, 2),
                "log": str(log),
            }
        )
        print(f"{'PASS' if code == 0 else 'FAIL'} {name}: {log}", flush=True)
        if code:
            print(
                "\n".join(log.read_text(errors="replace").splitlines()[-25:]),
                flush=True,
            )
        report["complete"] = len(report["checks"]) == len(checks)
        report["passed"] = report["complete"] and all(
            c["returncode"] == 0 for c in report["checks"]
        )
        report["finishedAt"] = datetime.now(UTC).isoformat()
        (artifacts / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report: {artifacts / 'report.json'}", flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
