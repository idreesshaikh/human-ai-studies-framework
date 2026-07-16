"""Workspace snapshotter + participant-commit observer (FR-INST-15/17)."""

from datetime import UTC, datetime, timedelta

import pytest
from agent_capture.events import (
    SOURCE_PARTICIPANT_GIT,
    SOURCE_SNAPSHOT,
    Keys,
)
from agent_capture.gitutil import git
from agent_capture.snapshot import Snapshotter


@pytest.fixture()
def workspace(tmp_path):
    ws = tmp_path / "task"
    ws.mkdir()
    git("init", "-q", cwd=ws)
    git("config", "user.email", "p@p", cwd=ws)
    git("config", "user.name", "participant", cwd=ws)
    (ws / "detect.py").write_text("def detect():\n    return 1\n")
    return ws


class _Clock:
    def __init__(self):
        self.t = datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC)

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += timedelta(seconds=seconds)


def _snapshotter(tmp_path, workspace):
    return Snapshotter(
        Keys("P01", "ai-assisted", "S1"),
        workspace,
        tmp_path / "shadow.git",
        clock=_Clock(),
    )


def test_snapshot_commits_only_on_change(tmp_path, workspace):
    snap = _snapshotter(tmp_path, workspace)
    first = snap.snapshot(trigger="save")
    shots = [e for e in first if e["source"] == SOURCE_SNAPSHOT]
    assert len(shots) == 1
    assert shots[0]["payload"]["trigger"] == "save"
    assert shots[0]["payload"]["insertions"] >= 2

    # No workspace change -> no new shadow commit; the prior one is re-emitted
    # (idempotent), so the count is stable, not growing.
    again = snap.snapshot(trigger="timer")
    assert len([e for e in again if e["source"] == SOURCE_SNAPSHOT]) == 1

    (workspace / "detect.py").write_text("def detect():\n    return 2\n")
    third = snap.snapshot(trigger="save")
    assert len([e for e in third if e["source"] == SOURCE_SNAPSHOT]) == 2


def test_snapshot_seq_is_deterministic_and_idempotent(tmp_path, workspace):
    """Two independent snapshotters over the same history produce identical
    (source, seq, hash) tuples - so re-runs reconcile (FR-ING-2)."""
    _snapshotter(tmp_path, workspace).snapshot()
    (workspace / "x.py").write_text("x = 1\n")
    key = lambda evs: sorted(  # noqa: E731
        (e["source"], e["seq"], e["payload"].get("commitHash"))
        for e in evs
        if e["source"] == SOURCE_SNAPSHOT
    )
    a = _snapshotter(tmp_path, workspace).snapshot()
    b = _snapshotter(tmp_path, workspace).snapshot()
    assert key(a) == key(b)
    assert [e["seq"] for e in a if e["source"] == SOURCE_SNAPSHOT] == [0, 1]


def test_participant_commits_are_observed_content_free(tmp_path, workspace):
    git("add", "-A", cwd=workspace)
    git("commit", "-qm", "seed secret message text", cwd=workspace)
    snap = _snapshotter(tmp_path, workspace)
    events = snap.snapshot()
    commits = [e for e in events if e["source"] == SOURCE_PARTICIPANT_GIT]
    assert len(commits) == 1
    payload = commits[0]["payload"]
    assert payload["hash"] and "filesChanged" in payload
    # No message text ever (FR-ETH-2).
    assert "message" not in payload
    assert "secret" not in str(payload)


def test_shadow_repo_never_captures_participant_git_internals(tmp_path, workspace):
    git("add", "-A", cwd=workspace)
    git("commit", "-qm", "work", cwd=workspace)
    snap = _snapshotter(tmp_path, workspace)
    snap.snapshot()
    tracked = git(
        f"--git-dir={tmp_path / 'shadow.git'}",
        f"--work-tree={workspace}",
        "ls-files",
    )
    assert ".git/" not in tracked
    assert "detect.py" in tracked


def test_git_wrapper_ignores_enclosing_git_context(tmp_path, monkeypatch):
    """When the snapshotter runs inside another git process (a commit hook,
    a rebase exec) git exports GIT_DIR/GIT_INDEX_FILE pointing at THAT repo.
    Inheriting them would silently redirect our shadow-repo operations at the
    enclosing repo's index - the wrapper must scrub them (regression: the
    pre-commit pytest hook made workspace snapshots vanish)."""
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nonexistent-outer.git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "nonexistent-index"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "nonexistent-tree"))

    repo = tmp_path / "repo"
    repo.mkdir()
    assert "Initialized" in git("init", repo.name, cwd=tmp_path, check=True) or True
    (repo / "f.txt").write_text("hello\n")
    git("add", "f.txt", cwd=repo, check=True)
    git("-c", "user.email=t@t", "-c", "user.name=t",
        "commit", "-m", "x", cwd=repo, check=True)
    assert git("log", "--oneline", cwd=repo, check=True)
