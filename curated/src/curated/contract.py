"""The mining adapter contract and the normalized-event shape (FR-CUR-1)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# The curated event vocabulary, registered in the versioned event schema as **v5**
# (consumers branch on version, never guess - NFR-4).
CURATED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "mined_commit",
        "mined_pull_request",
        "mined_review",
        "mined_issue_event",
        "mined_actor_snapshot",
    }
)

CURATED_SCHEMA_VERSION: int = 5


@dataclass(frozen=True)
class NormalizedEvent:
    """One mined event in the one-timeline shape (mirrors the live event row)."""

    session_id: str
    seq: int
    participant_id: str
    condition: str
    type: str
    ts: str
    payload: dict
    source: str
    schema_version: int = CURATED_SCHEMA_VERSION
    mono: float = 0.0

    def __post_init__(self) -> None:
        if self.type not in CURATED_EVENT_TYPES:
            raise ValueError(
                f"unknown curated event type {self.type!r}; "
                f"expected one of {sorted(CURATED_EVENT_TYPES)}"
            )

    def to_ingest_row(self) -> dict:
        """The `/ingest/events` payload for this event (the wire format)."""
        return {
            "sessionId": self.session_id,
            "seq": self.seq,
            "v": self.schema_version,
            "ts": self.ts,
            "mono": self.mono,
            "participantId": self.participant_id,
            "condition": self.condition,
            "type": self.type,
            "payload": self.payload,
            "source": self.source,
        }


@dataclass(frozen=True)
class SamplingFrame:
    """
    The declared sampling frame - the mined equivalent of "the approved protocol is the
    executed protocol" (FR-ETH-1).
    """

    query: str
    window_start: str
    window_end: str
    inclusion_rules: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    target_n: int = 0
    actor_unit: str = "developer"
    conditions: list[str] = field(default_factory=list)
    content_policy: str = "metadata-only"


@dataclass(frozen=True)
class CoverageEstimate:
    """
    What ``plan`` reports before a run: how many units the frame implies, so the UI can
    show a coverage bar and the researcher can sanity-check the frame before spending an
    API budget.
    """

    requested: int
    note: str = ""


@dataclass(frozen=True)
class Cursor:
    """An opaque, adapter-defined resume point."""

    value: dict


@dataclass(frozen=True)
class CursorCheckpoint:
    """Yielded by ``run`` between batches of events."""

    cursor: Cursor
    retrieved: int


RunItem = NormalizedEvent | CursorCheckpoint


@runtime_checkable
class MiningAdapter(Protocol):
    """One source adapter (GitHub, later others)."""

    source: str

    def plan(self, frame: SamplingFrame) -> CoverageEstimate:
        """
        Estimate coverage for ``frame`` without mining (cheap, for the UI and the frame
        sanity-check).
        """
        ...

    def run(self, frame: SamplingFrame, cursor: Cursor | None) -> Iterator[RunItem]:
        """
        Mine ``frame`` from ``cursor`` (or the start when ``None``), yielding normalized
        events and periodic cursor checkpoints.
        """
        ...
