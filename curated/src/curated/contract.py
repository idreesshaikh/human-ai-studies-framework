"""The mining adapter contract and the normalized-event shape (FR-CUR-1).

The architectural bet of the whole leg: **the join-key event schema is the
convergence contract**. A mining adapter reads some external source and
emits :class:`NormalizedEvent` rows that land in the exact one-timeline
shape a live instrument produces - so every downstream recipe, report,
figure, and paper-draft mechanism works on mined data unchanged.

Join keys, reinterpreted for mined units (and documented as such here so
the meaning travels with the code):

- ``participant_id`` - the anonymized *actor unit* (a developer, a repo, or
  an agent), declared per dataset, always a salted-hash pseudonym
  (:mod:`curated.pseudonymize`). Never a raw login/name/email.
- ``condition`` - the study's comparison arm (e.g. ``agent-pr`` vs
  ``human-pr``, ``pre-adoption`` vs ``post-adoption``).
- ``session_id`` - the mined *activity unit*: a PR, an issue thread, or a
  commit-batch window (the unit is declared in the sampling frame).
- ``ts`` - the source's own event time (an ISO-8601 string), **never**
  import time. Reproducibility depends on this.
- ``seq`` - the adapter's deterministic ordinal within a ``source`` stream.
  Re-mining yields the same ``(session_id, source, seq)`` for the same
  source event, so replay is idempotent under the middleware's existing
  unique constraint (FR-ING-2) - no new dedup machinery.

Every event type is one of :data:`CURATED_EVENT_TYPES` (schema v5), and
every payload is content-free by default: sizes, counts, timings, flags,
and salted hashes only. Raw identities, commit-message text, and code
content appear only when the protocol's content policy explicitly scopes
them (the FR-AGENT-5 mechanism, reused).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

#: The curated event vocabulary, registered in the versioned event schema as
#: **v5** (consumers branch on version, never guess - NFR-4). Content-free by
#: default; payload shapes are documented in ``curated/docs/event-vocab.md``.
CURATED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "mined_commit",
        "mined_pull_request",
        "mined_review",
        "mined_issue_event",
        "mined_actor_snapshot",
    }
)

#: The schema version curated events carry. Registered beside the live
#: vocabulary's v2/v3/v4 in the middleware's ``KNOWN_EVENT_SCHEMA_VERSIONS``.
CURATED_SCHEMA_VERSION: int = 5


@dataclass(frozen=True)
class NormalizedEvent:
    """One mined event in the one-timeline shape (mirrors the live event row).

    ``to_ingest_row`` renders the exact dict the middleware's ``/ingest/
    events`` endpoint accepts, so a mining job is just another producer of
    the same wire format - no special ingestion path.
    """

    session_id: str
    seq: int
    participant_id: str
    condition: str
    type: str
    ts: str
    payload: dict
    source: str
    schema_version: int = CURATED_SCHEMA_VERSION
    #: Monotonic ordinal within the job, for ordering ties at equal ``ts``.
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
    """The declared sampling frame - the mined equivalent of "the approved
    protocol is the executed protocol" (FR-ETH-1). An adapter refuses to run
    without one (F2.2).

    Parsed from the protocol's ``curated:`` section (:mod:`curated.frame`).
    """

    query: str
    window_start: str
    window_end: str
    inclusion_rules: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    target_n: int = 0
    #: The declared actor unit for ``participant_id``: "developer" | "repo"
    #: | "agent". Documented per dataset in the threats record.
    actor_unit: str = "developer"
    #: The comparison arms this frame populates (the ``condition`` values).
    conditions: list[str] = field(default_factory=list)
    #: Content policy (FR-AGENT-5 vocabulary): "metadata-only" (default) |
    #: "redacted" | "full". Governs whether any raw text may enter payloads.
    content_policy: str = "metadata-only"


@dataclass(frozen=True)
class CoverageEstimate:
    """What ``plan`` reports before a run: how many units the frame implies,
    so the UI can show a coverage bar and the researcher can sanity-check the
    frame before spending an API budget."""

    requested: int
    note: str = ""


@dataclass(frozen=True)
class Cursor:
    """An opaque, adapter-defined resume point. The job runner persists it
    verbatim and hands it back on resume - that is the *entire* resume story
    (F2.1), no separate machinery. Must be JSON-serializable."""

    value: dict


@dataclass(frozen=True)
class CursorCheckpoint:
    """Yielded by ``run`` between batches of events. When the runner sees one
    it persists ``cursor`` and records ``retrieved`` for coverage. Resuming
    replays from the last persisted cursor."""

    cursor: Cursor
    retrieved: int


#: What an adapter's ``run`` yields: events interleaved with periodic
#: checkpoints. The runner ingests events and persists checkpoints.
RunItem = NormalizedEvent | CursorCheckpoint


@runtime_checkable
class MiningAdapter(Protocol):
    """One source adapter (GitHub, later others). Adapters register by
    ``source`` in :data:`curated.registry.ADAPTERS`; the runner never names a
    concrete adapter."""

    source: str

    def plan(self, frame: SamplingFrame) -> CoverageEstimate:
        """Estimate coverage for ``frame`` without mining (cheap, for the UI
        and the frame sanity-check)."""
        ...

    def run(
        self, frame: SamplingFrame, cursor: Cursor | None
    ) -> Iterator[RunItem]:
        """Mine ``frame`` from ``cursor`` (or the start when ``None``),
        yielding normalized events and periodic cursor checkpoints. Must be
        deterministic given the same source data, so ``seq`` is stable and
        re-mining is idempotent."""
        ...
