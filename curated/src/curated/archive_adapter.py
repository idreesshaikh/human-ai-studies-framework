"""Archive / replication-package importer (FR-CUR-4)."""

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
    NormalizedEvent,
    RunItem,
    SamplingFrame,
)
from curated.heuristics import ActorSignal, classify, tokenize_slug
from curated.pseudonymize import pseudonym

SOURCE = "archive"

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
    text = p.read_text(encoding="utf-8", errors="replace")
    try:
        value = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        value = None
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("events", "records", "items"):
            items = value.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return [value]
    out: list[dict] = []
    for line in text.splitlines():
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


def _values(record: dict, *keys: str) -> tuple[str, ...]:
    """Read structured string values without inspecting free-form prose."""
    values: list[str] = []
    for key in keys:
        value = record.get(key)
        if isinstance(value, (list, tuple, set)):
            for item in value:
                if isinstance(item, dict):
                    item = item.get("login") or item.get("name") or ""
                if item:
                    values.append(str(item))
        elif isinstance(value, dict):
            item = value.get("login") or value.get("name") or ""
            if item:
                values.append(str(item))
        elif value:
            values.append(str(value))
    return tuple(values)


def _author_signal(record: dict) -> tuple[str, ActorSignal]:
    """Build an authorship signal from provider metadata only."""
    actor = record.get("actor") or record.get("author") or record.get("user")
    if isinstance(actor, dict):
        raw_author = str(actor.get("login") or actor.get("name") or "unknown")
        actor_bot = actor.get("bot") is True or (
            str(actor.get("type", "")).lower() == "bot"
        )
    else:
        raw_author = str(actor or "unknown")
        actor_bot = False

    bot_flagged = actor_bot or any(
        record.get(key) is True for key in ("isBot", "is_bot", "bot")
    )
    coauthors = _values(record, "coauthors", "coauthorLogins", "co_authors")
    structured_fields = _values(
        record,
        "app",
        "appSlug",
        "application",
        "authorType",
        "actorType",
    )
    signature_tokens = tuple(
        token for value in structured_fields for token in tokenize_slug(value)
    )
    return raw_author, ActorSignal(
        login=raw_author,
        is_bot_flagged=bot_flagged,
        coauthor_logins=tuple(value.lower() for value in coauthors),
        signature_tokens=signature_tokens,
    )


def _condition(frame: SamplingFrame, record: dict, is_agent: bool) -> str:
    """Use an explicit arm, or map clearly named agent/human arms."""
    explicit = str(record.get("condition", "")).strip()
    if explicit and explicit in frame.conditions:
        return explicit
    conditions = [str(value) for value in frame.conditions if str(value).strip()]
    if not conditions:
        return "default"
    if len(conditions) == 1:
        return conditions[0]
    tokens = ("agent", "ai", "bot", "automated") if is_agent else (
        "human",
        "unassisted",
        "manual",
    )
    for value in conditions:
        if any(token in value.lower() for token in tokens):
            return value
    return conditions[0]


class ArchiveAdapter:
    """Read a local replication archive into the experimental event schema."""

    source = SOURCE

    def __init__(self, path: str | Path | None = None, salt: str = "") -> None:
        self._path = path
        self._salt = salt
        self.retrieved = 0

    def plan(self, frame: SamplingFrame) -> CoverageEstimate:
        path = self._path or frame.query
        records = _load_json(path) or _load_csv(path)
        total = len(records)
        requested = min(total, frame.target_n) if frame.target_n else total
        return CoverageEstimate(
            requested=requested,
            note=f"{total} records in archive; targeting {requested or total}.",
        )

    def run(self, frame: SamplingFrame, cursor: Cursor | None) -> Iterator[RunItem]:
        path = self._path or frame.query
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
        raw_author, signal = _author_signal(record)
        verdict = classify(signal)
        pid = pseudonym(salt, raw_author, prefix="actor")
        condition = _condition(frame, record, verdict.is_agent)
        session_id = str(
            record.get("sessionId")
            or record.get("repo")
            or record.get("session_id", f"archive-{seq}")
        )
        ts = str(
            record.get("createdAt") or record.get("timestamp") or record.get("ts", "")
        )

        event_payload: dict[str, Any] = {
            "rawType": raw_type,
            "authorIsAgent": verdict.is_agent,
            "firedHeuristics": verdict.fired,
        }
        for key in (
            "additions",
            "deletions",
            "changedFiles",
            "commits",
            "reviewCount",
            "reviewComments",
            "lines",
            "chars",
            "size",
        ):
            if key in record:
                try:
                    event_payload[key] = int(record[key])
                except (ValueError, TypeError):
                    event_payload[key] = str(record[key])
        for key in ("state", "action"):
            if key in record and record[key] is not None:
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
