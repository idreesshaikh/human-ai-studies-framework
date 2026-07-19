"""Workspace snapshotter (FR-INST-15, D14) + participant commit observer
(FR-INST-17).

A *shadow* git repository (``--git-dir=<study-data>/shadow.git
--work-tree=<task workspace>``) commits the whole task workspace on a save
webhook and every N minutes. This gives the metrics leg a free time series
 and lets code evolution be reconstructed, not
just its final state - with no custom snapshot format to invent, and
without touching the participant's own git (separate git-dir, same
worktree).

The participant's *own* commits in the task repo are content-free
telemetry, not touched but *observed*: each new hash in the task repo's
``git log`` becomes a ``git_commit`` event carrying hash + files-changed +
insertions/deletions + timing - never the message text (FR-ETH-2,
FR-INST-17).

Two independent producers write here, each with its own ``seq`` stream but
the shared session join key: this module emits under ``workspace-snapshot``.
Time-dependent triggering uses an injected clock so the timer is testable
(CLAUDE.md).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from agent_capture.events import (
    EVENT_GIT_COMMIT,
    EVENT_SNAPSHOT,
    SOURCE_PARTICIPANT_GIT,
    SOURCE_SNAPSHOT,
    Keys,
    study_event,
)
from agent_capture.gitutil import git, show_numstat

Clock = Callable[[], datetime]


class ShadowRepo:
    """The hidden snapshot repo over the task workspace."""

    def __init__(self, workspace: str | Path, git_dir: str | Path):
        self.workspace = Path(workspace)
        self.git_dir = Path(git_dir)

    def _args(self) -> list[str]:
        return [
            f"--git-dir={self.git_dir}",
            f"--work-tree={self.workspace}",
        ]

    def init(self) -> None:
        if not (self.git_dir / "HEAD").exists():
            self.git_dir.parent.mkdir(parents=True, exist_ok=True)
            git("init", "--bare", str(self.git_dir))
        # Identity is local to the shadow repo so the participant's global
        # git config is untouched.
        git(*self._args(), "config", "user.email", "snapshotter@study.local")
        git(*self._args(), "config", "user.name", "study-snapshotter")

    def commit(self, message: str) -> str | None:
        """Stage everything and commit. Returns the new hash, or ``None`` when
        the workspace is unchanged (git makes no commit)."""
        git(*self._args(), "add", "-A")
        head_before = git(*self._args(), "rev-parse", "HEAD")
        git(*self._args(), "commit", "--allow-empty-message", "-m", message)
        head_after = git(*self._args(), "rev-parse", "HEAD")
        if not head_after or head_after == head_before:
            return None
        return head_after

    def commit_numstat(self, commit_hash: str) -> dict:
        return show_numstat(commit_hash, cwd=self.git_dir)


class Snapshotter:
    """Snapshot commits + participant-commit observation for one session.

    ``seq`` is *derived from git ordinals*, never an in-process counter, so
    the snapshotter can run as a long-lived timer **or** be re-invoked
    single-shot on every save (the runbook's choice) and either way the same
    logical commit always lands at the same ``(session, source, seq)`` -
    repeated ticks reconcile idempotently rather than duplicating (FR-ING-2).
    Two producer streams: shadow snapshots (``workspace-snapshot``) and the
    participant's own observed commits (``participant-git``), each with its
    own contiguous ordinal.
    """

    def __init__(
        self,
        keys: Keys,
        workspace: str | Path,
        git_dir: str | Path,
        *,
        clock: Clock | None = None,
    ):
        self.keys = keys
        self.workspace = Path(workspace)
        self.shadow = ShadowRepo(workspace, git_dir)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.shadow.init()

    def _ts(self) -> str:
        return self.clock().isoformat(timespec="milliseconds")

    def _hashes_oldest_first(self, cwd: Path | str) -> list[str]:
        out = git("log", "--reverse", "--format=%H", cwd=cwd)
        return out.splitlines() if out else []

    def snapshot(self, trigger: str = "timer") -> list[dict]:
        """Commit a snapshot (if the workspace changed), then emit the full
        deterministic event set for this session's shadow + participant
        history. ``trigger`` is ``save`` or ``timer``. Re-emitting the whole
        history each tick is safe (idempotent) and self-healing."""
        ts = self._ts()
        self.shadow.commit(f"snapshot:{trigger}:{ts}")
        events: list[dict] = []
        # Shadow snapshots: seq = commit ordinal in the shadow repo.
        shadow_hashes = self._hashes_oldest_first(self.shadow.git_dir)
        for seq, h in enumerate(shadow_hashes):
            stat = self.shadow.commit_numstat(h)
            last = seq == len(shadow_hashes) - 1
            events.append(
                study_event(
                    self.keys,
                    source=SOURCE_SNAPSHOT,
                    seq=seq,
                    type=EVENT_SNAPSHOT,
                    ts=ts,
                    payload={
                        "commitHash": h,
                        # Only the freshest commit's trigger is meaningful this
                        # tick; earlier ones were captured on prior triggers.
                        "trigger": trigger if last else "timer",
                        **stat,
                    },
                )
            )
        # Participant commits: seq = commit ordinal in the task repo.
        for seq, h in enumerate(self._hashes_oldest_first(self.workspace)):
            stat = show_numstat(h, cwd=self.workspace)
            events.append(
                study_event(
                    self.keys,
                    source=SOURCE_PARTICIPANT_GIT,
                    seq=seq,
                    type=EVENT_GIT_COMMIT,
                    ts=ts,
                    payload={"hash": h, **stat},  # no message text (FR-ETH-2)
                )
            )
        return events
