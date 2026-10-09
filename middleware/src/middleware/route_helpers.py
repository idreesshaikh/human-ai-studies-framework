"""Shared protocol, event, and export helpers for the API routes."""

import itertools
import json
import re
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from middleware.db import (
    IMPLICIT_PROJECT_ID,
    Event,
    Study,
)

# Event schema versions this service is written against; other versions are stored and
# flagged, never rejected (FR-PROT-2 discipline).
KNOWN_EVENT_SCHEMA_VERSIONS = {2, 3, 4, 5, 6}

# Agent-capture producers set their own ``source`` so their ``seq`` stream never
# collides (see db.py).
DEFAULT_SOURCE = "tern"

# Renaming the stream would otherwise split one session across two ``source`` values:
# ``(session_id, source, seq)`` is the uniqueness key (db.py), so a mid-study upgrade
# would restart the seq stream and read as a gap.
LEGACY_SOURCES = {"cognitive-overlay"}


def canonical_source(source: str) -> str:
    """The producer stream under its current name."""
    return DEFAULT_SOURCE if source in LEGACY_SOURCES else source


Clock = Callable[[], datetime]


class _ProtocolCheck:
    """Validates join keys against the loaded study protocol (FR-ING-6)."""

    def __init__(self, protocol: dict | None):
        self.protocol = protocol
        self.study_id = protocol["study"]["id"] if protocol else None
        self.conditions = set(protocol["conditions"]) if protocol else None
        self.planned = protocol["participants"]["planned"] if protocol else None

    def flags_for(self, participant_id: str, condition: str, v: int | None) -> list:
        flags = []
        if not participant_id or not condition:
            flags.append("malformed")
        if self.conditions is not None and condition not in self.conditions:
            flags.append("unknown-condition")
        if self.planned is not None and participant_id:
            m = re.fullmatch(r"P(\d+)", participant_id)
            if not m or not (1 <= int(m.group(1)) <= self.planned):
                flags.append("unknown-participant")
        if v is not None and v not in KNOWN_EVENT_SCHEMA_VERSIONS:
            flags.append("unknown-schema-version")
        return flags


def _sse(event: str, data: dict) -> str:
    """One server-sent event frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _slug_from_text(text: str, max_len: int) -> str:
    """A URL-safe id from free text  -  a project or study name, often a whole
    typed sentence (e.g. the "describe your study" opening question) rather
    than a short title. A hard character cut lands mid-word as often as not
    ("...debuggin"), which then sits as the study's permanent id; back off to
    the last word boundary within the limit instead, keeping the hard cut
    only when the text has no boundary to back off to at all."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(slug) <= max_len:
        return slug
    truncated = slug[:max_len]
    boundary = truncated.rfind("-")
    return truncated[:boundary] if boundary > 0 else truncated


def _ensure_study_row(s: Session, study_id: str, protocol_doc: dict) -> None:
    """Create or backfill a study row for the loaded protocol."""

    row = s.scalar(select(Study).where(Study.id == study_id))
    if row is not None:
        if not row.project_id:
            row.project_id = IMPLICIT_PROJECT_ID
        return
    pv = str(protocol_doc.get("protocolVersion", "")) if protocol_doc else ""
    s.add(
        Study(
            id=study_id,
            project_id=IMPLICIT_PROJECT_ID,
            protocol_version=pv,
        )
    )


def _gap_summary(seqs: list[int]) -> dict:
    """
    Seq-gap integrity summary for one session's sorted ``seq`` list (FR-ING-3): loss is
    never silent, it is a report.
    """
    missing = []
    for prev, nxt in itertools.pairwise(seqs):
        if nxt > prev + 1:
            missing.append(
                {"afterSeq": prev, "beforeSeq": nxt, "missing": nxt - prev - 1}
            )
    return {
        "firstSeq": seqs[0],
        "lastSeq": seqs[-1],
        "received": len(seqs),
        "expected": seqs[-1] - seqs[0] + 1,
        "gaps": missing,
        "complete": not missing and seqs[0] == 0,
    }


def _session_gap_facts(seqs_by_source: dict[str, list[int]]) -> dict:
    """Aggregate one session's per-producer gap facts."""
    gap_count = missing = 0
    completes = []
    for seqs in seqs_by_source.values():
        summary = _gap_summary(sorted(seqs))
        gap_count += len(summary["gaps"])
        missing += summary["expected"] - summary["received"]
        completes.append(summary["complete"])
    return {
        "gapCount": gap_count,
        "missingEvents": missing,
        "complete": bool(completes) and all(completes),
    }


def _capture_payload(payload: dict, raw_code: bool = False) -> dict:
    return {key: value for key, value in payload.items() if raw_code or key != "diff"}


def _event_json(e: Event, *, raw_code: bool = False) -> dict:
    return {
        "v": e.v,
        "ts": e.ts,
        "mono": e.mono,
        "sessionId": e.session_id,
        "source": e.source,
        "participantId": e.participant_id,
        "condition": e.condition,
        "taskId": e.task_id,
        "seq": e.seq,
        "type": e.type,
        "payload": _capture_payload(e.payload, raw_code),
        "flags": e.flags,
    }
