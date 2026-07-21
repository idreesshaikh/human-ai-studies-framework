"""The unified study dataset a recipe consumes (FR-ING-4 -> FR-ANA-1).

One object wraps the middleware's one-timeline export: every row carries the
join keys (``sessionId``, ``participantId``, ``condition``, timestamp,
schema version - FR-INST-6), and the two legs a recipe distinguishes are

- **events** - StudyEvent rows (``source != "metrics"``): cognitive,
  behavioral, and (with) agent event types, and
- **metrics** - static-metrics rows (``source == "metrics"``), function- or
  file-level per the 9-metric matrix.

Loaders cover both deployment shapes: ``Dataset.fetch()`` pulls
``GET /studies/{id}/dataset`` from a running middleware; ``from_json()``
reads the same document exported to a file (replication kits, tests).
"""

from __future__ import annotations

import json
import urllib.request
from functools import cached_property
from pathlib import Path

import pandas as pd

#: Join-key columns every row of every leg carries (FR-INST-6).
JOIN_KEYS = ["sessionId", "participantId", "condition"]


class Dataset:
    """The one-timeline dataset for a single study."""

    def __init__(self, rows: list[dict], study_id: str = "", meta: dict | None = None):
        self.study_id = study_id
        self.rows = rows
        self.meta = meta or {}

    # ------------------------------------------------------------- loaders

    @classmethod
    def from_json(cls, path: str | Path) -> Dataset:
        doc = json.loads(Path(path).read_text())
        return cls(rows=doc["rows"], study_id=doc.get("studyId", ""))

    @classmethod
    def fetch(cls, server: str, study_id: str) -> Dataset:
        url = f"{server.rstrip('/')}/studies/{study_id}/dataset?format=json"
        with urllib.request.urlopen(url, timeout=30) as res:
            doc = json.loads(res.read())
        return cls(rows=doc["rows"], study_id=doc.get("studyId", study_id))

    # ------------------------------------------------------------- frames

    @cached_property
    def events(self) -> pd.DataFrame:
        """StudyEvent rows: join keys + ``ts`` (UTC datetime) + ``type`` +
        ``seq`` + raw ``payload`` dict."""
        rows = [r for r in self.rows if r.get("source") != "metrics"]
        if not rows:
            return pd.DataFrame(columns=[*JOIN_KEYS, "ts", "type", "seq", "payload"])
        df = pd.DataFrame(rows)[[*JOIN_KEYS, "ts", "type", "seq", "payload"]]
        df["ts"] = pd.to_datetime(df["ts"], utc=True, format="mixed")
        return df.sort_values(["sessionId", "seq"]).reset_index(drop=True)

    @cached_property
    def metrics(self) -> pd.DataFrame:
        """Static-metric rows with the payload's metric columns expanded.

        ``level`` is ``function_metrics`` or ``file_metrics`` (the middleware
        stores it as the row ``type``).
        """
        rows = [r for r in self.rows if r.get("source") == "metrics"]
        if not rows:
            return pd.DataFrame(columns=[*JOIN_KEYS, "ts", "level"])
        base = pd.DataFrame(
            [
                {
                    **{k: r.get(k) for k in JOIN_KEYS},
                    "ts": r.get("ts"),
                    "level": r.get("type"),
                    **{
                        k: v
                        for k, v in r.get("payload", {}).items()
                        if k not in JOIN_KEYS and k not in ("timestamp")
                    },
                }
                for r in rows
            ]
        )
        base["ts"] = pd.to_datetime(base["ts"], utc=True, format="mixed")
        return base

    # ------------------------------------------------------------ requires

    @cached_property
    def event_types(self) -> set[str]:
        return set(self.events["type"].unique()) if len(self.events) else set()

    @cached_property
    def metric_columns(self) -> set[str]:
        """Metric columns that exist AND carry at least one numeric value."""
        skip = {*JOIN_KEYS, "ts", "level", "file", "function", "schemaVersion"}
        cols = set()
        for col in self.metrics.columns:
            if col in skip:
                continue
            series = pd.to_numeric(self.metrics[col], errors="coerce")
            if series.notna().any():
                cols.add(col)
        return cols

    @cached_property
    def conditions(self) -> list[str]:
        """Conditions present in the data, stable order of first appearance."""
        seen: dict[str, None] = {}
        for frame in (self.events, self.metrics):
            if "condition" in frame.columns:
                for c in frame["condition"]:
                    if c:
                        seen.setdefault(c, None)
        return list(seen)

    # ------------------------------------------------------------- helpers

    def of_type(self, *types: str) -> pd.DataFrame:
        """Events of the given type(s) with payload keys expanded to columns."""
        df = self.events[self.events["type"].isin(types)]
        if df.empty:
            return df.drop(columns=["payload"]).copy()
        payload = pd.json_normalize(df["payload"]).set_index(df.index)
        clash = [c for c in payload.columns if c in df.columns]
        return pd.concat(
            [df.drop(columns=["payload"]), payload.drop(columns=clash)], axis=1
        )

    @cached_property
    def session_spans(self) -> pd.DataFrame:
        """Per session: join keys, first/last event ts, and duration minutes.

        The denominator recipes share; uses the full event span (an honest
        upper bound on active time - recipes must say so in methods when it
        matters).
        """
        if self.events.empty:
            return pd.DataFrame(columns=[*JOIN_KEYS, "start", "end", "durationMinutes"])
        g = self.events.groupby(JOIN_KEYS, as_index=False).agg(
            start=("ts", "min"), end=("ts", "max")
        )
        g["durationMinutes"] = (g["end"] - g["start"]).dt.total_seconds() / 60.0
        return g
