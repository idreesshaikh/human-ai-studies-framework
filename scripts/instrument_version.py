"""Print which TERN build a calibration ran on, as JSON.

    head                   `git rev-parse HEAD`
    uncommittedDiffSha256  sha256 of `git diff HEAD -- extension agent-capture
                           analysis/src/analysis/recipes/control_arm_audit.py`
                           (the hash of an empty diff means the build is exactly
                           the committed one)
    vsixVersion            "version" in extension/package.json
    untrackedFiles         files under those paths that git does not track.
                           `git diff` cannot see them, so a new source file would
                           otherwise be missing from the hash.

Read-only: only `git rev-parse`, `git diff` and `git ls-files` are ever run, with
optional locks off so the index is never touched.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git") or "git"
READ_ONLY = frozenset({"rev-parse", "diff", "ls-files"})
INSTRUMENT_PATHS = (
    "extension",
    "agent-capture",
    "analysis/src/analysis/recipes/control_arm_audit.py",
)


def git(*args: str, cwd: Path = ROOT) -> bytes:
    """Run one read-only git command and return its stdout bytes."""
    if not args or args[0] not in READ_ONLY:
        raise ValueError(
            f"read-only git commands only ({', '.join(sorted(READ_ONLY))}); "
            f"refusing git {' '.join(args)}"
        )
    return subprocess.run(
        [GIT, "--no-optional-locks", *args],
        cwd=cwd,
        capture_output=True,
        check=True,
    ).stdout


def collect(root: Path = ROOT, run_git=None) -> dict:
    def run(*args: str) -> bytes:
        return git(*args, cwd=root) if run_git is None else run_git(*args)

    package = json.loads((root / "extension" / "package.json").read_text())
    diff = run("diff", "HEAD", "--", *INSTRUMENT_PATHS)
    untracked = run(
        "ls-files", "--others", "--exclude-standard", "--", *INSTRUMENT_PATHS
    )
    return {
        "head": run("rev-parse", "HEAD").decode().strip(),
        "uncommittedDiffSha256": hashlib.sha256(diff).hexdigest(),
        "vsixVersion": package["version"],
        "untrackedFiles": sorted(untracked.decode().splitlines()),
    }


def main() -> int:
    print(json.dumps(collect(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
