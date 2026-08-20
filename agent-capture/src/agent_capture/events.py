"""Agent-leg event contract (FR-AGENT-1) and the shared StudyEvent envelope."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

SCHEMA_VERSION = 4

SOURCE_AGENT = "agent-capture"
SOURCE_SNAPSHOT = "workspace-snapshot"
SOURCE_PARTICIPANT_GIT = "participant-git"
SOURCE_HARNESS = "task-harness"
SOURCE_DERIVED = "agent-derived"

EVENT_SESSION_META = "agent_session_meta"
EVENT_TURN = "agent_turn"
EVENT_TOOL_CALL = "tool_call"
EVENT_TASK_OUTCOME = "task_outcome"
EVENT_SNAPSHOT = "workspace_snapshot"
EVENT_GIT_COMMIT = "git_commit"
EVENT_RELIANCE_LOOP = "reliance_loop"
EVENT_BURST_ANNOTATION = "edit_burst_annotation"
EVENT_CODE_EVOLUTION = "code_evolution"


@dataclass(frozen=True)
class Keys:
    """The study join keys a producer stamps onto every event."""

    participant_id: str = ""
    condition: str = ""
    session_id: str = ""

    @classmethod
    def from_env(cls, environ: dict | None = None) -> Keys:
        env = environ if environ is not None else os.environ
        return cls(
            participant_id=env.get("STUDY_PARTICIPANT", ""),
            condition=env.get("STUDY_CONDITION", ""),
            session_id=env.get("STUDY_SESSION", ""),
        )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def study_event(
    keys: Keys,
    *,
    source: str,
    seq: int,
    type: str,
    payload: dict,
    ts: str | None = None,
    mono: float = -1.0,
) -> dict:
    """One StudyEvent in the middleware wire shape (FR-ING-1)."""
    return {
        "v": SCHEMA_VERSION,
        "ts": ts or _now_iso(),
        "mono": mono,
        "sessionId": keys.session_id,
        "source": source,
        "participantId": keys.participant_id,
        "condition": keys.condition,
        "seq": seq,
        "type": type,
        "payload": payload,
    }


def batch(source: str, events: list[dict]) -> dict:
    """The HttpSink envelope the middleware accepts (``{source, events}``)."""
    return {"source": source, "events": events}
