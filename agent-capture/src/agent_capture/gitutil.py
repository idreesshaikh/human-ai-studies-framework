"""Thin, tolerant git wrapper shared by the snapshotter and harness.

git is the snapshot store (D14) and the participant's own VCS: we shell out
rather than depend on a library. Everything is best-effort - a git failure
must never interrupt the participant (NFR-1), so callers get empty output,
not exceptions.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

#: Repo-context variables an *enclosing* git process exports to its hooks
#: (commit -> pre-commit, etc.). Inheriting them would silently redirect our
#: snapshot/harness git calls at the enclosing repo's index instead of the
#: shadow repo we point at - scrub them so ``--git-dir``/``cwd`` always win.
_GIT_CONTEXT_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
)


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in _GIT_CONTEXT_VARS}


def git(*args: str, cwd: str | Path | None = None, check: bool = False) -> str:
    """Run ``git <args>`` and return stdout (stripped). Returns ``""`` on
    failure unless ``check`` is set."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            env=_clean_env(),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        if check:
            raise
        return ""
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def numstat(commit_args: list[str], cwd: str | Path) -> dict:
    """``{filesChanged, insertions, deletions}`` for ``git diff --numstat
    <commit_args>`` (content-free - counts only, never paths or text)."""
    out = git("diff", "--numstat", *commit_args, cwd=cwd)
    files = insertions = deletions = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        files += 1
        # Binary files show "-" for counts.
        insertions += int(parts[0]) if parts[0].isdigit() else 0
        deletions += int(parts[1]) if parts[1].isdigit() else 0
    return {"filesChanged": files, "insertions": insertions, "deletions": deletions}


def show_numstat(commit_hash: str, cwd: str | Path) -> dict:
    """Same shape for a single commit (``git show --numstat``)."""
    out = git("show", "--numstat", "--format=", commit_hash, cwd=cwd)
    files = insertions = deletions = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        files += 1
        insertions += int(parts[0]) if parts[0].isdigit() else 0
        deletions += int(parts[1]) if parts[1].isdigit() else 0
    return {"filesChanged": files, "insertions": insertions, "deletions": deletions}
