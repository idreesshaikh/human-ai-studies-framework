"""Freeze the private calibration materials by committing only their hashes.

The calibration plan, predictions, task and reference solution live in
`docs/experiments/ai-use-calibration/`, which `.gitignore` keeps private. To
freeze them without publishing them, this script writes a manifest of sha256
hashes to a tracked file, `docs/calibration-freeze.json`. Committing that
manifest is the freeze: its commit fixes the date, and anyone later given the
files can rerun `check` to confirm they are the ones that were frozen.

    write   hash the materials and write the manifest. Refuses if a
            `TODO-BEFORE-FREEZE:` line remains, if the TERN build has
            uncommitted changes, or if a manifest already exists.
    check   rehash and compare. Exits 1 and names every file that changed,
            disappeared or appeared, and fails if the instrument paths
            changed since the frozen commit.

`plan.md` and `predictions.md` are hashed only up to their `## Deviations`
heading, so dated deviations can be appended after the freeze without
breaking it. Every other byte is hashed exactly.

Read-only towards git: only the commands `instrument_version.py` allows.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "docs" / "experiments" / "ai-use-calibration"
MANIFEST = ROOT / "docs" / "calibration-freeze.json"
PROCEDURE_PATHS = (
    "scripts/calibration_session.py",
    "scripts/calibration_order.py",
    "scripts/run_calibration.py",
    "scripts/freeze_calibration.py",
    "scripts/instrument_version.py",
    "analysis/src/analysis/adherence_sim.py",
    "protocol/examples/pilot-study.yaml",
)

# Documents that may grow a dated "Deviations" section after the freeze.
APPENDABLE = ("plan.md", "predictions.md")
FROZEN_DIRS = ("task", "reference")
DEVIATIONS_HEADING = b"## Deviations"
TODO_MARKER = "TODO-BEFORE-FREEZE" + ":"
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store"}


def _instrument_version():
    path = Path(__file__).resolve().parent / "instrument_version.py"
    spec = importlib.util.spec_from_file_location("instrument_version", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_bytes(path: Path) -> bytes:
    """The part of a file the freeze covers."""
    data = path.read_bytes()
    if path.name in APPENDABLE:
        for offset, line in _line_starts(data):
            if line.startswith(DEVIATIONS_HEADING):
                return data[:offset]
    return data


def _line_starts(data: bytes):
    offset = 0
    for line in data.splitlines(keepends=True):
        yield offset, line
        offset += len(line)


def frozen_files(experiment: Path) -> list[Path]:
    files = [experiment / name for name in APPENDABLE]
    for folder in FROZEN_DIRS:
        files.extend(
            p
            for p in sorted((experiment / folder).rglob("*"))
            if p.is_file() and not SKIP_PARTS & set(p.relative_to(experiment).parts)
        )
    missing = [str(p.relative_to(experiment)) for p in files if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"missing from the experiment folder: {', '.join(missing)}"
        )
    return files


def hashes(experiment: Path) -> dict[str, str]:
    return {
        p.relative_to(experiment).as_posix(): hashlib.sha256(
            frozen_bytes(p)
        ).hexdigest()
        for p in frozen_files(experiment)
    }


def open_todos(experiment: Path) -> list[str]:
    found = []
    for name in APPENDABLE:
        text = frozen_bytes(experiment / name).decode()
        for number, line in enumerate(text.splitlines(), start=1):
            if TODO_MARKER in line:
                found.append(f"{name}:{number}: {line.strip()}")
    return found


def instrument_problems(instrument: dict) -> list[str]:
    problems = []
    empty = hashlib.sha256(b"").hexdigest()
    if instrument["uncommittedDiffSha256"] != empty:
        problems.append("the TERN build has uncommitted changes; commit them first")
    if instrument["untrackedFiles"]:
        problems.append(
            "untracked files under the instrument paths: "
            + ", ".join(instrument["untrackedFiles"])
        )
    return problems


def procedure_problems(root: Path, run_git=None) -> list[str]:
    """Refuse a procedure that differs from HEAD or contains untracked files."""

    def run(*args: str) -> bytes:
        if run_git is not None:
            return run_git(*args)
        return _instrument_version().git(*args, cwd=root)

    problems = []
    if run("diff", "HEAD", "--", *PROCEDURE_PATHS):
        problems.append("the procedure has uncommitted changes; commit them first")
    untracked = run("ls-files", "--others", "--", *PROCEDURE_PATHS)
    if untracked:
        problems.append(
            "untracked procedure files: " + ", ".join(untracked.decode().splitlines())
        )
    return problems


def procedure_hashes(root: Path) -> dict[str, str]:
    return {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path in PROCEDURE_PATHS
    }


def write(
    experiment: Path,
    manifest: Path,
    instrument: dict,
    *,
    root: Path | None = None,
    run_git=None,
    uncommitted: bool = False,
) -> list[str]:
    """Write the manifest; return the reasons it was refused (empty on success).

    With ``uncommitted`` the procedure may differ from git HEAD: it is then fixed
    only by the content hashes in the manifest, and the manifest says so.
    """
    if manifest.exists():
        return [f"{manifest} already exists; a freeze is never rewritten"]
    problems = [f"open item: {t}" for t in open_todos(experiment)]
    problems += instrument_problems(instrument)
    root = ROOT if root is None else root
    if not uncommitted:
        problems += procedure_problems(root, run_git)
    if problems:
        return problems
    body = {
        "description": (
            "sha256 of the private AI-use calibration materials, frozen before "
            "the first session; see scripts/freeze_calibration.py"
        ),
        "rule": (
            "plan.md and predictions.md are hashed up to their '## Deviations' heading"
        ),
        "instrument": {k: instrument[k] for k in ("head", "vsixVersion")},
        "files": hashes(experiment),
        "procedure": procedure_hashes(root),
        "frozenAtUtc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "procedureCommitted": not uncommitted,
    }
    if uncommitted:
        body["note"] = (
            "Frozen without a commit: the procedure and materials are fixed by the "
            "sha256 values above, not by a git revision, and the date is local."
        )
    manifest.write_text(json.dumps(body, indent=2) + "\n")
    return []


def check(
    experiment: Path,
    manifest: Path,
    instrument_changes: list[str],
    *,
    root: Path | None = None,
) -> list[str]:
    """Compare the materials with the manifest; return every difference."""
    body = json.loads(manifest.read_text())
    frozen = body["files"]
    now = hashes(experiment)
    problems = [
        f"changed: {f}" for f in sorted(frozen) if f in now and now[f] != frozen[f]
    ]
    problems += [f"missing: {f}" for f in sorted(frozen) if f not in now]
    problems += [f"not in the freeze: {f}" for f in sorted(now) if f not in frozen]
    root = ROOT if root is None else root
    for path in PROCEDURE_PATHS:
        file = root / path
        expected = body.get("procedure", {}).get(path)
        if (
            not file.is_file()
            or hashlib.sha256(file.read_bytes()).hexdigest() != expected
        ):
            problems.append(f"procedure changed: {path}")
    return problems + instrument_changes


def live_instrument_changes(manifest: Path) -> list[str]:
    iv = _instrument_version()
    frozen_head = json.loads(manifest.read_text())["instrument"]["head"]
    problems = instrument_problems(iv.collect())
    diff = iv.git("diff", frozen_head, "HEAD", "--", *iv.INSTRUMENT_PATHS)
    if diff:
        problems.append(
            f"the instrument paths changed since the frozen commit {frozen_head[:12]}"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("write", "check"))
    parser.add_argument("--experiment", type=Path, default=EXPERIMENT)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument(
        "--uncommitted",
        action="store_true",
        help="write: freeze a procedure that is not committed (hashes only)",
    )
    args = parser.parse_args(argv)

    try:
        if args.command == "write":
            problems = write(
                args.experiment,
                args.manifest,
                _instrument_version().collect(),
                uncommitted=args.uncommitted,
            )
        else:
            if not args.manifest.is_file():
                print(
                    f"no manifest at {args.manifest}; run write first", file=sys.stderr
                )
                return 1
            problems = check(
                args.experiment, args.manifest, live_instrument_changes(args.manifest)
            )
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1

    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print(f"{args.command}: ok ({args.manifest})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
