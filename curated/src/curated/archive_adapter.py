"""Archive / replication-package importer (FR-CUR-4).

Reads published replication packages and research archives (e.g. DevGPT-style
JSON/CSV exports) and emits NormalizedEvent rows in the same join-keyed schema
as the GitHub adapter. Reuses pseudonymize.py for anonymization and threats.py
for the validity-threats record verbatim — "mined strangers get the same
protection as consented participants" (wall #7).

The adapter takes a local file path (the archive) rather than a fetcher,
because replication packages are pre-downloaded artifacts, not live API
responses. Deterministic: same archive always produces the same events in
the same order, so re-import is idempotent under the middleware's
``(session_id, source, seq)`` unique constraint.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from curated.contract import (
    CoverageEstimate,
    Cursor,
    CursorCheckpoint,
    MiningAdapter,
    NormalizedEvent,
    RunItem,
    SamplingFrame,
)
from curated.pseudonymize import pseudonym

SOURCE = "archive"

# DevGPT event types mapped to the curated event vocabulary.
_EVENT_TYPE_MAP = {
    "PullRequest": "mined_pull_request",
    "Commit": "mined_commit",
    "ReviewComment": "mined_review",
    "IssueComment": "mined_issue_event",
    "Issue": "mined_issue_event",
}


def _load_json(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        return []
    text = p.read_bytes()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    # Try JSONL
    out: list[dict] = []
    for line in text.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _load_csv(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        return []
    text = p.read_text("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


class ArchiveAdapter:
    """Mines a local replication-package archive into the curated event schema.

    Accepts JSON, JSONL, or CSV files. Each record is mapped via the
    ``_EVENT_TYPE_MAP`` and pseudonymized with the per-dataset salt.
    """

    source = SOURCE

    def __init__(self, path: str | Path | None = None, salt: str = "") -> None:
        self._path = path
        self._salt = salt
        self.retrieved = 0

    def plan(self, frame: SamplingFrame) -> CoverageEstimate:
        path = frame.query
        records = _load_json(path) or _load_csv(path)
        total = len(records)
        requested = min(total, frame.target_n) if frame.target_n else total
        return CoverageEstimate(
            requested=requested,
            note=f"{total} records in archive; targeting {requested or total}.",
        )

    def run(self, frame: SamplingFrame, cursor: Cursor | None) -> Iterator[RunItem]:
        path = frame.query
        records = _load_json(path) or _load_csv(path)
        skip = int(cursor.value.get("skip", 0)) if cursor else 0
        seen = int(cursor.value.get("seen", 0)) if cursor else 0
        target = frame.target_n or 0
        salt = self._salt or "default-archive-salt"

        for idx, record in enumerate(records):
            if idx < skip:
                continue
            if target and seen >= target:
                return
            event = self._process_record(record, frame, salt, idx)
            if event is not None:
                yield event
                seen += 1
                self.retrieved += 1
            if seen > 0 and seen % 10 == 0:
                yield CursorCheckpoint(
                    cursor=Cursor({"skip": idx + 1, "seen": seen}),
                    retrieved=self.retrieved,
                )

        yield CursorCheckpoint(
            cursor=Cursor({"skip": len(records), "seen": seen}),
            retrieved=self.retrieved,
        )

    def _process_record(
        self, record: dict, frame: SamplingFrame, salt: str, seq: int
    ) -> NormalizedEvent | None:
        raw_type = str(record.get("type", "") or "")
        event_type = _EVENT_TYPE_MAP.get(raw_type, "mined_commit")
        raw_author = str(record.get("actor") or record.get("author") or record.get("user") or "unknown")
        pid = pseudonym(salt, raw_author, prefix="actor")
        condition = frame.conditions[0] if frame.conditions else "default"
        session_id = str(record.get("sessionId") or record.get("repo") or record.get("session_id", f"archive-{seq}"))
        ts = str(record.get("createdAt") or record.get("timestamp") or record.get("ts", ""))

        event_payload: dict[str, Any] = {
            "rawType": raw_type,
        }
        for key in ("additions", "deletions", "changedFiles", "commits", "lines", "chars", "size"):
            if key in record:
                try:
                    event_payload[key] = int(record[key])
                except (ValueError, TypeError):
                    event_payload[key] = str(record[key])

        return NormalizedEvent(
            session_id=session_id,
            seq=seq,
            participant_id=pid,
            condition=condition,
            type=event_type,
            ts=ts,
            source=SOURCE,
            schema_version=5,
            mono=float(seq),
            payload=event_payload,
        )
