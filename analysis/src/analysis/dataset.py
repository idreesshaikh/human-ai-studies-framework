"""The exported study dataset consumed by analysis recipes."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import pandas as pd

JOIN_KEYS = ["sessionId", "participantId", "condition"]


@dataclass(frozen=True)
class Provenance:
    """
    How many of a dataset's rows are dry-run rows.

    Synthetic rows are labelled at ingest so a rehearsal can never be mistaken for
    a finding. Every artefact the runner writes carries this verdict.
    """

    total: int
    synthetic: int

    @property
    def participant(self) -> int:
        return self.total - self.synthetic

    @property
    def kind(self) -> str:
        """``empty``, ``participant``, ``synthetic``, or ``mixed``."""
        if not self.total:
            return "empty"
        if not self.synthetic:
            return "participant"
        return "synthetic" if self.synthetic == self.total else "mixed"

    @property
    def banner(self) -> str | None:
        """
        The warning every artefact must carry, or ``None`` for participant data.

        Mixed provenance is the worse case, not the milder one: the numbers below
        such a banner blend rehearsal rows into real ones, so the reader cannot
        recover the finding by mentally discounting a fraction.
        """
        if self.kind == "synthetic":
            return (
                "> **⚠ SYNTHETIC DATA — not a research finding.**  \n"
                f"> All {self.total} rows are dry-run rows generated to rehearse "
                "the capture and analysis path. The statistics below describe "
                "simulated input. They say the pipeline connects; they say "
                "nothing about how developers work."
            )
        if self.kind == "mixed":
            return (
                "> **⚠ MIXED PROVENANCE — not a research finding.**  \n"
                f"> {self.synthetic} of {self.total} rows are synthetic dry-run "
                f"rows and {self.participant} are participant rows. Re-run against "
                "a dataset that excludes dry-run sessions before reporting "
                "anything below."
            )
        return None


class Dataset:
    """The one-timeline dataset for a single study."""

    def __init__(self, rows: list[dict], study_id: str = "", meta: dict | None = None):
        self.study_id = study_id
        self.rows = rows
        self.meta = meta or {}

    @classmethod
    def from_json(cls, path: str | Path) -> Dataset:
        doc = json.loads(Path(path).read_text())
        return cls(rows=doc["rows"], study_id=doc.get("studyId", ""))

    @classmethod
    def fetch(
        cls, server: str, study_id: str, *, include_synthetic: bool = False
    ) -> Dataset:
        url = f"{server.rstrip('/')}/studies/{study_id}/dataset?format=json"
        if include_synthetic:
            url += "&includeSynthetic=true"
        token = os.environ.get("MIDDLEWARE_TOKEN")
        request = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {token}"} if token else {}
        )
        with urllib.request.urlopen(request, timeout=30) as res:
            doc = json.loads(res.read())
        return cls(rows=doc["rows"], study_id=doc.get("studyId", study_id))

    @cached_property
    def provenance(self) -> Provenance:
        """Whether these rows are participant data, dry-run rows, or both."""
        return Provenance(
            total=len(self.rows),
            synthetic=sum(1 for r in self.rows if r.get("synthetic")),
        )

    @cached_property
    def events(self) -> pd.DataFrame:
        """
        StudyEvent rows: join keys + ``ts`` (UTC datetime) + ``type`` + ``seq`` +
        ``flags`` (integrity marks stamped at ingest; the export always carries the key,
        empty list when clean) + raw ``payload``.
        """
        rows = [r for r in self.rows if r.get("source") != "metrics"]
        if not rows:
            return pd.DataFrame(
                columns=[*JOIN_KEYS, "ts", "type", "seq", "flags", "payload"]
            )
        df = pd.DataFrame(rows)
        current_survey = df["type"] == "end_survey_response"
        df.loc[current_survey, "payload"] = df.loc[current_survey, "payload"].map(
            lambda payload: dict(payload.get("responses") or {})
        )
        df.loc[current_survey, "type"] = "end_survey"
        df["ts"] = pd.to_datetime(df["ts"], utc=True, format="mixed")
        return df.sort_values(["sessionId", "seq"]).reset_index(drop=True)

    @cached_property
    def metrics(self) -> pd.DataFrame:
        """Static-metric rows with the payload's metric columns expanded."""
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
                        if k not in JOIN_KEYS and k != "timestamp"
                    },
                    **{k: r[k] for k in ("taskId", "schemaVersion") if k in r},
                }
                for r in rows
            ]
        )
        base["ts"] = pd.to_datetime(base["ts"], utc=True, format="mixed")
        return base

    @cached_property
    def event_types(self) -> set[str]:
        return set(self.events["type"].unique()) if len(self.events) else set()

    @cached_property
    def metric_columns(self) -> set[str]:
        """Metric columns that exist AND carry at least one numeric value."""
        skip = {
            *JOIN_KEYS,
            "ts",
            "level",
            "file",
            "function",
            "taskId",
            "schemaVersion",
            "synthetic",
        }
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
        """Per session: join keys, first/last event ts, and duration minutes."""
        if self.events.empty:
            return pd.DataFrame(columns=[*JOIN_KEYS, "start", "end", "durationMinutes"])
        g = self.events.groupby(JOIN_KEYS, as_index=False).agg(
            start=("ts", "min"), end=("ts", "max")
        )
        g["durationMinutes"] = (g["end"] - g["start"]).dt.total_seconds() / 60.0
        return g
