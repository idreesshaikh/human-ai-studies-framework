"""
Workspace snapshotter (FR-INST-15, D14) + participant commit observer (FR-INST-17).
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
        git(*self._args(), "config", "user.email", "snapshotter@study.local")
        git(*self._args(), "config", "user.name", "study-snapshotter")

    def commit(self, message: str) -> str | None:
        """Stage everything and commit."""
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
    """Snapshot commits + participant-commit observation for one session."""

    def __init__(
        self,
        keys: Keys,
        workspace: str | Path,
        git_dir: str | Path,
        *,
        clock: Clock | None = None,
        code_files: tuple[str, ...] = (),
    ):
        self.keys = keys
        self.workspace = Path(workspace)
        self.shadow = ShadowRepo(workspace, git_dir)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.code_files = code_files
        for name in code_files:
            path = Path(name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or any(part.startswith(".") for part in path.parts)
                or path.suffix.lower()
                not in {
                    ".py",
                    ".js",
                    ".ts",
                    ".tsx",
                    ".jsx",
                    ".java",
                    ".go",
                    ".rs",
                    ".c",
                    ".cpp",
                    ".h",
                    ".cs",
                }
                or not (self.workspace / path)
                .resolve()
                .is_relative_to(self.workspace.resolve())
            ):
                raise ValueError(
                    "Code capture requires explicit, non-secret task file paths"
                )
        self.shadow.init()

    def _ts(self) -> str:
        return self.clock().isoformat(timespec="milliseconds")

    def _hashes_oldest_first(self, cwd: Path | str) -> list[str]:
        out = git("log", "--reverse", "--format=%H", cwd=cwd)
        return out.splitlines() if out else []

    def snapshot(self, trigger: str = "timer") -> list[dict]:
        """
        Commit a snapshot (if the workspace changed), then emit the full deterministic
        event set for this session's shadow + participant history.
        """
        ts = self._ts()
        self.shadow.commit(f"snapshot:{trigger}:{ts}")
        events: list[dict] = []
        shadow_hashes = self._hashes_oldest_first(self.shadow.git_dir)
        for seq, h in enumerate(shadow_hashes):
            stat = self.shadow.commit_numstat(h)
            code = {}
            if self.code_files:
                patch = git(
                    "show",
                    "--format=",
                    "--no-ext-diff",
                    "--no-textconv",
                    "--unified=3",
                    h,
                    "--",
                    *(f":(literal){name}" for name in self.code_files),
                    cwd=self.shadow.git_dir,
                )
                code = {"codeCaptureEnabled": True}
                if len(patch) <= 64_000:
                    code["diff"] = patch
                else:
                    code["diffOmitted"] = "Patch exceeds 64,000 characters"
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
                        "trigger": trigger if last else "timer",
                        **stat,
                        **code,
                    },
                )
            )
        for seq, h in enumerate(self._hashes_oldest_first(self.workspace)):
            stat = show_numstat(h, cwd=self.workspace)
            events.append(
                study_event(
                    self.keys,
                    source=SOURCE_PARTICIPANT_GIT,
                    seq=seq,
                    type=EVENT_GIT_COMMIT,
                    ts=ts,
                    payload={"hash": h, **stat},
                )
            )
        return events
