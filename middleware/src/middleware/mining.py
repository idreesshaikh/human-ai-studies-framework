"""The mining-job runner (FR-CUR-2, MP-16 Slice B).

Drives a mining adapter, ingests its normalized events into the events table
(the same rows a live instrument produces - the convergence contract), and
persists the job's cursor + coverage as it goes. Jobs run as background
asyncio tasks inside the one FastAPI process (NFR-7 - no worker fleet); the
state machine (``state-machines.md`` §3) is:

    declared -> running <-> paused_rate_limited / interrupted
             -> gated -> complete | failed_gate

Design choices that keep this honest and testable:

- **Ingestion reuses the middleware's own idempotent insert** (the same
  ``(session_id, source, seq)`` unique constraint as ``/ingest/events``), so
  re-mining after a resume drops duplicate rows silently (F1.2/F2.1) - no new
  dedup path.
- **The runner is a plain generator-driven loop** (``run_job``) with an
  injected sleep, so tests drive it synchronously against the cassette with
  no real waiting; the FastAPI layer wraps it in ``asyncio.to_thread``.
- **A rate-limit is a pause, never a crash** (F2.3): the adapter raises
  ``RateLimited``; the runner records a plain-language status, backs off, and
  retries from the persisted cursor.
- **The frame gate is upstream**: ``start_job`` refuses without a
  protocol-declared sampling frame (F2.2) before any state is created.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from curated.cassette import RateLimited
from curated.contract import CursorCheckpoint, MiningAdapter, SamplingFrame
from curated.threats import build_record

# States (kept as strings to match the DB column; grouped here for one
# vocabulary the endpoints and UI share).
DECLARED = "declared"
RUNNING = "running"
PAUSED_RATE_LIMITED = "paused_rate_limited"
INTERRUPTED = "interrupted"
GATED = "gated"
COMPLETE = "complete"
FAILED_GATE = "failed_gate"

MAX_RATE_LIMIT_RETRIES = 5


@dataclass
class JobState:
    """The mutable state a run threads through. Mirrors the ``MiningJob`` row;
    the caller persists it via ``on_update`` after each checkpoint so an
    interruption loses at most one un-checkpointed batch."""

    state: str = DECLARED
    cursor: dict | None = None
    requested: int = 0
    retrieved: int = 0
    dropped: dict[str, int] | None = None
    fired_heuristics: list[str] | None = None
    status_message: str = ""

    def __post_init__(self) -> None:
        if self.dropped is None:
            self.dropped = {}
        if self.fired_heuristics is None:
            self.fired_heuristics = []


#: An ingest callback: given a list of `/ingest/events`-shaped rows, insert
#: them idempotently. The runner stays ignorant of the DB.
IngestFn = Callable[[list[dict]], None]
#: A persistence callback: called after each checkpoint with the current
#: JobState so progress survives an interruption.
UpdateFn = Callable[[JobState], None]


def run_job(
    adapter: MiningAdapter,
    frame: SamplingFrame,
    state: JobState,
    ingest: IngestFn,
    on_update: UpdateFn,
    *,
    sleep: Callable[[float], None] = time.sleep,
    max_retries: int = MAX_RATE_LIMIT_RETRIES,
) -> JobState:
    """Run (or resume) a mining job to completion or a gate.

    Reuses ``state.cursor`` as the resume point, so calling ``run_job`` again
    after an interruption continues without duplicates. Returns the final
    :class:`JobState` (``gated`` on success - the threats record is written by
    the caller, which then advances to ``complete``).
    """
    from curated.contract import Cursor

    state.requested = adapter.plan(frame).requested
    state.state = RUNNING
    on_update(state)

    retries = 0
    batch: list[dict] = []

    def flush() -> None:
        if batch:
            ingest(list(batch))
            batch.clear()

    while True:
        cursor = Cursor(state.cursor) if state.cursor else None
        try:
            for item in adapter.run(frame, cursor):
                if isinstance(item, CursorCheckpoint):
                    flush()
                    state.cursor = item.cursor.value
                    state.retrieved = item.retrieved
                    _sync_adapter_stats(adapter, state)
                    on_update(state)
                else:
                    batch.append(item.to_ingest_row())
            flush()
            _sync_adapter_stats(adapter, state)
            state.state = GATED
            state.status_message = "fetch complete — awaiting validity-threats record"
            on_update(state)
            return state
        except RateLimited as rl:
            flush()
            retries += 1
            if retries > max_retries:
                state.state = INTERRUPTED
                state.status_message = (
                    "paused: the source's rate limit did not clear after "
                    f"{max_retries} backoffs — resume later to continue."
                )
                on_update(state)
                return state
            state.state = PAUSED_RATE_LIMITED
            state.status_message = (
                "paused: the source's API rate limit was hit. Waiting "
                f"{rl.retry_after:g}s before continuing — nothing is lost, "
                "the job resumes from where it stopped."
            )
            on_update(state)
            sleep(rl.retry_after)
            state.state = RUNNING
            on_update(state)


def _sync_adapter_stats(adapter: MiningAdapter, state: JobState) -> None:
    """Pull the adapter's accumulated coverage/heuristics into the state."""
    fired = getattr(adapter, "fired_heuristics", None)
    if fired is not None:
        state.fired_heuristics = sorted(fired)
    dropped = getattr(adapter, "dropped", None)
    if dropped is not None:
        state.dropped = dict(dropped.counts)
    retrieved = getattr(adapter, "retrieved", None)
    if retrieved is not None:
        state.retrieved = max(state.retrieved, retrieved)


def default_threats_doc(frame: SamplingFrame, state: JobState) -> dict:
    """The machine-filled part of the threats record (coverage + heuristics +
    starter biases). The researcher revises the biases before the gate opens;
    coverage and the heuristic list are generated, not authored."""
    record = build_record(
        frame,
        fired_heuristic_ids=set(state.fired_heuristics or []),
        requested=state.requested,
        retrieved=state.retrieved,
        dropped=dict(state.dropped or {}),
    )
    return record.to_doc()
