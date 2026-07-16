"""Agent-leg event contract (FR-AGENT-1) and the shared StudyEvent envelope.

Every agent-leg row carries the same join keys and schema version as every
other leg (FR-INST-6): ``participantId``, ``condition``, ``sessionId``,
``ts``, ``v``. The agent leg is written by several independent
fire-and-forget producers - the Claude Code conversation capture, the
workspace snapshotter, the task harness, and the correlation job - and each
owns a private ``seq`` stream tagged with its ``source`` so they share the
session join key without colliding (see middleware/db.py).

Event-name reconciliation (deviation from the MP-12 draft table, noted in
`requirements/traceability.md`): the type/field names below match the
already-shipped MP-07 recipe consumers - ``tool_call`` (field ``tool``) and
``task_outcome.firstGreenMs`` - rather than the draft table's
``agent_tool_call``/``toolName``/``timeToFirstGreenMs``. The consumer
contract is tested; the producer conforms to it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

#: Agent-leg schema version (middleware KNOWN_EVENT_SCHEMA_VERSIONS includes
#: 4). Bumped from the extension's v3 because this leg adds event shapes.
SCHEMA_VERSION = 4

# Producer streams (each a private per-session ``seq`` space, db.py).
SOURCE_AGENT = "agent-capture"  # conversation capture (hooks + importer)
SOURCE_SNAPSHOT = "workspace-snapshot"  # shadow-git snapshotter
SOURCE_PARTICIPANT_GIT = "participant-git"  # observed participant commits
SOURCE_HARNESS = "task-harness"  # acceptance-test outcomes
SOURCE_DERIVED = "agent-derived"  # correlation + evolution derivations

# Event types (glossary/recipe-aligned).
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
    """The study join keys a producer stamps onto every event.

    Set by the facilitator's runbook as environment variables so the hook
    scripts and session-runner instruments inherit them without any
    hand-maintained side configuration (FR-PROT-4 discipline extends to the
    agent leg): ``STUDY_PARTICIPANT``, ``STUDY_CONDITION``, ``STUDY_SESSION``.
    """

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
    """One StudyEvent in the middleware wire shape (FR-ING-1).

    ``ts`` defaults to now (hook/snapshot/harness events); transcript-derived
    events pass the transcript line's own timestamp so the agent leg sits on
    the real session timeline.
    """
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
