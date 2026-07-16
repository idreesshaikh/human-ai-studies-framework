"""FastAPI ingestion service (FR-ING-1..6).

Design rules inherited from the extension (NFR-2, "never lose data"):

- **Idempotent** - the DB's unique constraints drop replayed rows silently;
  re-sent batches create no duplicates (FR-ING-2).
- **Never drop** - rows with unknown conditions/participants/schema versions
  are stored and *flagged*, and each flagged batch is logged as an
  operational finding (FR-ING-6, FR-META-1). Malformed rows missing join
  keys are stored with a ``malformed`` flag where the idempotency key
  (sessionId, seq) allows it.
- **Loss is visible** - ``GET /sessions/{id}/gaps`` reports seq gaps
  (FR-ING-3); the extension's ``seq`` exists precisely for this.

The extension's HttpSink POSTs ``{"source": "cognitive-overlay",
"events": [...]}`` (see extension/src/vscode/sinks.ts) - that payload is
accepted unchanged (FR-ING-1).
"""

import csv
import io
import json
import re
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import quote as _urlquote

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from protocol.lifecycle import PHASE_ORDER, current_phase
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from middleware import assistant, auth, paper_index, pdf, semantic_scholar, zotero
from middleware.db import (
    Event,
    Finding,
    MetricRow,
    Paper,
    PaperEdge,
    PaperLink,
    RecipeRun,
    S2Cache,
    StoredFile,
    TaskCard,
    make_session_factory,
)
from middleware.redocs import parse_glossary, parse_srs
from middleware.settings import Settings

#: Event schema versions this service is written against; other versions are
#: stored and flagged, never rejected (FR-PROT-2 discipline). v2 = cognitive
#: leg; v3 = + behavioral telemetry leg (MP-05); v4 = + agent-interaction
#: leg, snapshots, task harness (MP-12).
KNOWN_EVENT_SCHEMA_VERSIONS = {2, 3, 4}

#: The default producer stream when an event/batch names none - the
#: extension's HttpSink envelope value. Agent-capture producers set their
#: own ``source`` so their ``seq`` stream never collides (see db.py).
DEFAULT_SOURCE = "cognitive-overlay"

Clock = Callable[[], datetime]


class StudyEventIn(BaseModel):
    """Extension StudyEvent (schema v2). Only the idempotency key is hard-
    required; missing join keys are flagged, not rejected (never-drop)."""

    sessionId: str
    seq: int
    v: int = -1
    ts: str = ""
    mono: float = -1
    participantId: str = ""
    condition: str = ""
    type: str = ""
    payload: dict = Field(default_factory=dict)
    #: Producer stream; falls back to the batch's ``source`` then
    #: DEFAULT_SOURCE. Its own ``seq`` counter (db.py).
    source: str = ""


class EventBatch(BaseModel):
    """The HttpSink wire format; a bare event array is also accepted."""

    source: str = ""
    events: list[StudyEventIn]


class FindingIn(BaseModel):
    source: str = ""
    kind: str = ""
    requirementId: str = ""
    message: str
    context: dict = Field(default_factory=dict)
    status: str = "open"


class TaskIn(BaseModel):
    title: str
    note: str = ""


class RecipeRunIn(BaseModel):
    """One recipe run recorded by the analysis runner (MP-07)."""

    recipeId: str
    status: str = "ok"
    answers: list[str] = Field(default_factory=list)
    note: str = ""


class TaskPatch(BaseModel):
    status: str  # open | done


class ZoteroImportIn(BaseModel):
    """Import one Zotero collection into the paper set (FR-LIT-5, MP-09)."""

    collection: str  # collection name (case-insensitive) or 8-char key


class PaperIngestIn(BaseModel):
    """Ingest one paper by identifier (FR-LIT-1 id path). One of the two."""

    arxivId: str = ""
    doi: str = ""


class PaperLinksIn(BaseModel):
    """Replace a paper's protocol-element links (FR-LIT-3)."""

    targets: list[str] = Field(default_factory=list)


class AssistantIn(BaseModel):
    """One knowledge-assistant turn (FR-LIT-4). ``history`` is prior
    ``{role, content}`` turns (text only). ``model`` picks a Mistral tier
    (D32 rev 2); unset or unknown = the server's default."""

    question: str
    history: list[dict] = Field(default_factory=list)
    model: str | None = None


class _ProtocolCheck:
    """Validates join keys against the loaded study protocol (FR-ING-6).

    Participants are not enumerated in the protocol (it declares a planned
    *count*), so participant validation uses the documented pilot convention
    ``P<number>`` with 1 <= number <= participants.planned; anything else is
    flagged ``unknown-participant``. Conditions are validated exactly.
    With no protocol configured every value passes.
    """

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


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or Settings()
    clock = clock or (lambda: datetime.now(UTC))
    session_factory = make_session_factory(settings.db_path)

    protocol_doc = None
    if settings.protocol_path is not None:
        from protocol.loader import load_protocol

        protocol_doc = load_protocol(settings.protocol_path)
    check = _ProtocolCheck(protocol_doc)

    app = FastAPI(title="Study ingestion middleware", version="0.1.0")

    # Cross-origin access is opt-in per origin (FR-OPS-6): unset = the
    # same-origin-only default; set = e.g. a v0/Vercel dashboard preview
    # calling the demo middleware during design iteration (D30).
    if settings.cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def db() -> Session:  # FastAPI dependency
        session = session_factory()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    def now() -> str:
        return clock().isoformat(timespec="milliseconds")

    def log_finding(
        s: Session,
        source: str,
        requirement_id: str,
        message: str,
        context: dict,
        *,
        kind: str = "",
    ) -> None:
        s.add(
            Finding(
                at=now(),
                source=source,
                kind=kind,
                requirement_id=requirement_id,
                message=message,
                context=context,
            )
        )

    def check_study_id(study_id: str) -> None:
        if check.study_id is not None and study_id != check.study_id:
            raise HTTPException(
                404, f"unknown study {study_id!r}; this deployment serves "
                f"{check.study_id!r}"
            )

    # Sign-in gate on the dashboard-facing endpoints (FR-OPS-5): pluggable
    # provider (none/token/clerk), built once at startup so misconfiguration
    # fails loudly here, not on first request. Ingest stays open: sensors
    # are fire-and-forget (NFR-1) on a local-first deployment (NFR-5).
    verify_view_auth = auth.verifier_from_settings(settings)

    def view_auth(authorization: str = Header(default="")) -> None:
        verify_view_auth(authorization)

    def require_protocol() -> dict:
        if protocol_doc is None:
            raise HTTPException(
                404, "no protocol loaded; set MIDDLEWARE_PROTOCOL"
            )
        return protocol_doc

    # ---------------------------------------------------------------- ingest

    @app.post("/ingest/events")
    def ingest_events(
        batch: EventBatch | list[StudyEventIn], s: Session = Depends(db)
    ) -> dict:
        events = batch if isinstance(batch, list) else batch.events
        batch_source = "" if isinstance(batch, list) else batch.source
        received = now()
        flagged = 0
        rows = []
        for e in events:
            flags = check.flags_for(e.participantId, e.condition, e.v)
            flagged += bool(flags)
            rows.append(
                dict(
                    session_id=e.sessionId,
                    source=e.source or batch_source or DEFAULT_SOURCE,
                    seq=e.seq,
                    participant_id=e.participantId,
                    condition=e.condition,
                    v=e.v,
                    ts=e.ts,
                    mono=e.mono,
                    type=e.type,
                    payload=e.payload,
                    flags=flags,
                    received_at=received,
                )
            )
        inserted = 0
        if rows:
            stmt = (
                sqlite_insert(Event)
                .values(rows)
                .on_conflict_do_nothing(
                    index_elements=["session_id", "source", "seq"]
                )
            )
            inserted = s.execute(stmt).rowcount
        if flagged:
            log_finding(
                s,
                source="ingest/events",
                requirement_id="FR-ING-6",
                message=f"{flagged}/{len(rows)} events stored with integrity flags",
                context={"sessions": sorted({r["session_id"] for r in rows})},
                kind="integrity-flag",
            )
        return {
            "received": len(rows),
            "inserted": inserted,
            "duplicates": len(rows) - inserted,
            "flagged": flagged,
        }

    @app.post("/ingest/metrics")
    def ingest_metrics(rows: list[dict], s: Session = Depends(db)) -> dict:
        received = now()
        inserted = flagged = 0
        for row in rows:
            table = "function_metrics" if "function" in row else "file_metrics"
            flags = check.flags_for(
                str(row.get("participantId", "")), str(row.get("condition", "")), None
            )
            flagged += bool(flags)
            stmt = (
                sqlite_insert(MetricRow)
                .values(
                    table=table,
                    session_id=str(row.get("sessionId", "")),
                    participant_id=str(row.get("participantId", "")),
                    condition=str(row.get("condition", "")),
                    timestamp=str(row.get("timestamp", "")),
                    schema_version=int(row.get("schemaVersion", -1)),
                    row=row,
                    row_hash=MetricRow.hash_row(table, row),
                    flags=flags,
                    received_at=received,
                )
                .on_conflict_do_nothing(index_elements=["row_hash"])
            )
            inserted += s.execute(stmt).rowcount
        if flagged:
            log_finding(
                s,
                source="ingest/metrics",
                requirement_id="FR-ING-6",
                message=f"{flagged}/{len(rows)} metric rows stored with flags",
                context={},
                kind="integrity-flag",
            )
        return {
            "received": len(rows),
            "inserted": inserted,
            "duplicates": len(rows) - inserted,
            "flagged": flagged,
        }

    @app.post("/ingest/files")
    async def ingest_files(
        file: UploadFile,
        sessionId: str | None = None,
        participantId: str | None = None,
        s: Session = Depends(db),
    ) -> dict:
        content = await file.read()
        digest = sha256(content).hexdigest()
        existing = s.scalar(
            select(StoredFile).where(
                StoredFile.sha256 == digest,
                StoredFile.filename == (file.filename or "unnamed"),
            )
        )
        if existing:
            return {"id": existing.id, "sha256": digest, "duplicate": True}
        settings.files_dir.mkdir(parents=True, exist_ok=True)
        stored = settings.files_dir / f"{digest[:16]}-{file.filename}"
        stored.write_bytes(content)
        record = StoredFile(
            filename=file.filename or "unnamed",
            stored_path=str(stored),
            content_type=file.content_type or "",
            size=len(content),
            sha256=digest,
            session_id=sessionId,
            participant_id=participantId,
            uploaded_at=now(),
        )
        s.add(record)
        s.flush()
        return {"id": record.id, "sha256": digest, "duplicate": False}

    # ----------------------------------------------------------------- query

    @app.get("/studies/{study_id}/sessions", dependencies=[Depends(view_auth)])
    def list_sessions(study_id: str, s: Session = Depends(db)) -> list[dict]:
        check_study_id(study_id)
        out = {}
        event_rows = s.execute(
            select(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                func.count(),
                func.min(Event.ts),
                func.max(Event.ts),
            ).group_by(Event.session_id, Event.participant_id, Event.condition)
        ).all()
        for sid, pid, cond, n, first, last in event_rows:
            out[sid] = {
                "sessionId": sid,
                "participantId": pid,
                "condition": cond,
                "events": n,
                "metricRows": 0,
                "firstTs": first,
                "lastTs": last,
            }
        metric_rows = s.execute(
            select(
                MetricRow.session_id,
                MetricRow.participant_id,
                MetricRow.condition,
                func.count(),
            ).group_by(
                MetricRow.session_id, MetricRow.participant_id, MetricRow.condition
            )
        ).all()
        for sid, pid, cond, n in metric_rows:
            entry = out.setdefault(
                sid,
                {
                    "sessionId": sid,
                    "participantId": pid,
                    "condition": cond,
                    "events": 0,
                    "metricRows": 0,
                    "firstTs": None,
                    "lastTs": None,
                },
            )
            entry["metricRows"] = n
        return sorted(out.values(), key=lambda e: e["sessionId"])

    @app.get("/sessions/{session_id}/events", dependencies=[Depends(view_auth)])
    def session_events(
        session_id: str,
        type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 10_000,
        s: Session = Depends(db),
    ) -> list[dict]:
        q = select(Event).where(Event.session_id == session_id)
        if type:
            q = q.where(Event.type == type)
        if since:
            q = q.where(Event.ts >= since)
        if until:
            q = q.where(Event.ts <= until)
        q = q.order_by(Event.seq).limit(limit)
        return [_event_json(e) for e in s.scalars(q)]

    @app.get("/sessions/{session_id}/gaps", dependencies=[Depends(view_auth)])
    def session_gaps(session_id: str, s: Session = Depends(db)) -> dict:
        by_source: dict[str, list[int]] = defaultdict(list)
        for src, seq in s.execute(
            select(Event.source, Event.seq).where(Event.session_id == session_id)
        ):
            by_source[src].append(seq)
        if not by_source:
            raise HTTPException(404, f"no events for session {session_id!r}")
        # Each producer owns a ``seq`` stream; gaps are per (session, source).
        # The default producer's summary stays at the top level so the flat
        # shape is unchanged for single-producer sessions; ``sources`` breaks
        # every stream out (MP-12: agent legs write the same session).
        summaries = {
            src: _gap_summary(sorted(seqs)) for src, seqs in by_source.items()
        }
        primary = DEFAULT_SOURCE if DEFAULT_SOURCE in summaries else min(summaries)
        return {
            "sessionId": session_id,
            **summaries[primary],
            "sources": [
                {"source": src, **summaries[src]} for src in sorted(summaries)
            ],
        }

    @app.get("/studies/{study_id}/dataset", dependencies=[Depends(view_auth)])
    def dataset(study_id: str, format: str = "json", s: Session = Depends(db)):
        """The joined one-timeline export all legs share (FR-ING-4).

        Every row: source, ts, sessionId, participantId, condition, type,
        payload - sorted by (ts, source, seq). JSON by default, ``?format=csv``
        for the flat file (payload JSON-encoded in one column).
        """
        check_study_id(study_id)
        rows = [
            {
                "source": e.source,
                "ts": e.ts,
                "sessionId": e.session_id,
                "participantId": e.participant_id,
                "condition": e.condition,
                "type": e.type,
                "seq": e.seq,
                "flags": e.flags,
                "payload": e.payload,
            }
            for e in s.scalars(select(Event))
        ] + [
            {
                "source": "metrics",
                "ts": m.timestamp,
                "sessionId": m.session_id,
                "participantId": m.participant_id,
                "condition": m.condition,
                "type": m.table,
                "seq": None,
                "flags": m.flags,
                "payload": m.row,
            }
            for m in s.scalars(select(MetricRow))
        ]
        rows.sort(key=lambda r: (r["ts"], r["source"], r["seq"] or 0))
        if format == "json":
            return {"studyId": study_id, "rows": rows}
        if format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            header = ["source", "ts", "sessionId", "participantId", "condition",
                      "type", "seq", "flags", "payload"]
            writer.writerow(header)
            for r in rows:
                writer.writerow(
                    [r[k] if k not in ("flags", "payload") else json.dumps(r[k])
                     for k in header]
                )
            return PlainTextResponse(buf.getvalue(), media_type="text/csv")
        raise HTTPException(400, "format must be 'json' or 'csv'")

    # ------------------------------------- dashboard support (MP-06, FR-DASH)

    def _stored_files(s: Session) -> dict[str, StoredFile]:
        """Uploaded artifacts by filename - the lifecycle's evidence set.

        Later uploads win on filename collision (re-upload supersedes).
        """
        files = s.scalars(select(StoredFile).order_by(StoredFile.id))
        return {f.filename: f for f in files}

    def _lifecycle_doc(s: Session) -> dict:
        """The computed lifecycle (FR-DASH-2): the current phase is derived
        from uploaded gate artifacts via the lifecycle engine, never hand-set.
        """
        proto = require_protocol()
        files = _stored_files(s)
        declared = {p["name"]: list(p.get("gates", [])) for p in proto["phases"]}
        current = current_phase(proto, set(files))
        cur_i = PHASE_ORDER.index(current)
        phases = []
        for i, name in enumerate(PHASE_ORDER):
            gates = [
                {
                    "artifact": g,
                    "satisfied": g in files,
                    "satisfiedBy": (
                        {
                            "fileId": files[g].id,
                            "uploadedAt": files[g].uploaded_at,
                            "size": files[g].size,
                        }
                        if g in files
                        else None
                    ),
                }
                for g in declared.get(name, [])
            ]
            phases.append(
                {
                    "name": name,
                    "status": (
                        "complete" if i < cur_i
                        else "current" if i == cur_i
                        else "upcoming"
                    ),
                    "gates": gates,
                }
            )
        return {"currentPhase": current, "phases": phases}

    @app.get("/studies/{study_id}/protocol", dependencies=[Depends(view_auth)])
    def study_protocol(study_id: str) -> dict:
        """Protocol summary for the overview card (FR-DASH-1) and the
        traceability chips (FR-DASH-6): RQ -> planned recipes comes verbatim
        from the protocol's analysis plan."""
        check_study_id(study_id)
        proto = require_protocol()
        recipes_by_rq = {
            p["rq"]: list(p.get("recipes", []))
            for p in proto.get("analysisPlan", [])
        }
        return {
            "studyId": proto["study"]["id"],
            "protocolVersion": proto.get("protocolVersion"),
            "title": proto["study"].get("title", ""),
            "researchers": proto["study"].get("researchers", []),
            "ethicsRef": proto["study"].get("ethicsRef", ""),
            "conditions": list(proto.get("conditions", [])),
            "participants": proto.get("participants", {}),
            "session": proto.get("session", {}),
            "researchQuestions": [
                {
                    "id": rq["id"],
                    "text": rq["text"],
                    "recipes": recipes_by_rq.get(rq["id"], []),
                }
                for rq in proto.get("researchQuestions", [])
            ],
            "phases": [
                {"name": p["name"], "gates": list(p.get("gates", []))}
                for p in proto["phases"]
            ],
        }

    @app.get("/studies/{study_id}/lifecycle", dependencies=[Depends(view_auth)])
    def study_lifecycle(study_id: str, s: Session = Depends(db)) -> dict:
        check_study_id(study_id)
        return _lifecycle_doc(s)

    @app.get("/studies/{study_id}/status", dependencies=[Depends(view_auth)])
    def study_status(study_id: str, s: Session = Depends(db)) -> dict:
        """One factual status document (FR-DASH-7).

        The task board is a *projection* of this document: the dashboard
        derives cards from it and they clear themselves when the fact that
        spawned them disappears. Facts only - no card state lives here.
        """
        check_study_id(study_id)
        proto = require_protocol()

        # ``seq`` is per (session, source); gap facts aggregate over the
        # session's producer streams (each owns a contiguous stream).
        seqs_by_session: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for sid, src, seq in s.execute(
            select(Event.session_id, Event.source, Event.seq)
        ):
            seqs_by_session[sid][src].append(seq)

        flag_kinds: dict[str, set[str]] = defaultdict(set)
        flagged_events: dict[str, int] = defaultdict(int)
        for sid, flags in s.execute(
            select(Event.session_id, Event.flags).where(
                func.json_array_length(Event.flags) > 0
            )
        ):
            flagged_events[sid] += 1
            flag_kinds[sid].update(flags)

        sessions = {}
        for sid, pid, cond, n, last_recv in s.execute(
            select(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                func.count(),
                func.max(Event.received_at),
            ).group_by(Event.session_id, Event.participant_id, Event.condition)
        ):
            agg = _session_gap_facts(seqs_by_session[sid])
            sessions[sid] = {
                "sessionId": sid,
                "participantId": pid,
                "condition": cond,
                "events": n,
                "metricRows": 0,
                "flaggedEvents": flagged_events.get(sid, 0),
                "flagKinds": sorted(flag_kinds.get(sid, ())),
                "gapCount": agg["gapCount"],
                "missingEvents": agg["missingEvents"],
                "complete": agg["complete"],
                "lastReceivedAt": last_recv,
            }
        for sid, pid, cond, n in s.execute(
            select(
                MetricRow.session_id,
                MetricRow.participant_id,
                MetricRow.condition,
                func.count(),
            ).group_by(
                MetricRow.session_id, MetricRow.participant_id, MetricRow.condition
            )
        ):
            entry = sessions.setdefault(
                sid,
                {
                    "sessionId": sid,
                    "participantId": pid,
                    "condition": cond,
                    "events": 0,
                    "metricRows": 0,
                    "flaggedEvents": 0,
                    "flagKinds": [],
                    "gapCount": 0,
                    "missingEvents": 0,
                    "complete": False,
                    "lastReceivedAt": None,
                },
            )
            entry["metricRows"] = n

        participants = proto.get("participants", {})
        within = participants.get("design") == "within-subjects"
        conditions = list(proto.get("conditions", []))
        recipes_by_rq = {
            p["rq"]: list(p.get("recipes", []))
            for p in proto.get("analysisPlan", [])
        }
        ran = set(
            s.scalars(
                select(RecipeRun.recipe_id).where(
                    RecipeRun.study_id == proto["study"]["id"],
                    RecipeRun.status == "ok",
                )
            )
        )
        return {
            "studyId": proto["study"]["id"],
            "generatedAt": now(),
            "lifecycle": _lifecycle_doc(s),
            "conditions": conditions,
            "plannedParticipants": int(participants.get("planned", 0)),
            "plannedSessionsPerParticipant": len(conditions) if within else 1,
            "sessions": sorted(sessions.values(), key=lambda e: e["sessionId"]),
            "researchQuestions": [
                {
                    "id": rq["id"],
                    "recipes": recipes_by_rq.get(rq["id"], []),
                    # Recorded by `analysis run` (MP-07); planned recipes
                    # without a recorded ok run read as un-run.
                    "recipeRuns": [
                        r for r in recipes_by_rq.get(rq["id"], []) if r in ran
                    ],
                }
                for rq in proto.get("researchQuestions", [])
            ],
        }

    @app.get("/studies/{study_id}/live", dependencies=[Depends(view_auth)])
    def live_sessions(
        study_id: str,
        windowSeconds: int = 300,
        bucketSeconds: int = 10,
        s: Session = Depends(db),
    ) -> dict:
        """Sessions with ingests inside the window (FR-DASH-3), with per-
        bucket receive counts for the event-rate sparkline. Keyed on
        ``received_at`` (when the middleware saw the row), not event ``ts``:
        liveness is about ingestion, and replayed sessions show up too."""
        check_study_id(study_id)
        now_dt = clock()
        cutoff = (now_dt - timedelta(seconds=windowSeconds)).astimezone(UTC)
        cutoff_s = cutoff.isoformat(timespec="milliseconds")
        buckets = max(1, windowSeconds // bucketSeconds)

        recent = s.scalars(
            select(Event)
            .where(Event.received_at >= cutoff_s)
            .order_by(Event.received_at, Event.seq)
        ).all()
        by_session: dict[str, list[Event]] = defaultdict(list)
        for e in recent:
            by_session[e.session_id].append(e)

        out = []
        for sid, events in sorted(by_session.items()):
            rate = [0] * buckets
            for e in events:
                age = (now_dt - datetime.fromisoformat(e.received_at)).total_seconds()
                idx = buckets - 1 - min(int(age // bucketSeconds), buckets - 1)
                rate[idx] += 1
            last = events[-1]
            per_source: dict[str, list[int]] = defaultdict(list)
            for src, seq in s.execute(
                select(Event.source, Event.seq).where(Event.session_id == sid)
            ):
                per_source[src].append(seq)
            agg = _session_gap_facts(per_source)
            out.append(
                {
                    "sessionId": sid,
                    "participantId": last.participant_id,
                    "condition": last.condition,
                    "eventsInWindow": len(events),
                    "lastEventType": last.type,
                    "lastReceivedAt": last.received_at,
                    "lastSeq": last.seq,
                    "rate": rate,
                    "gapCount": agg["gapCount"],
                    "missingEvents": agg["missingEvents"],
                }
            )
        return {
            "now": now(),
            "windowSeconds": windowSeconds,
            "bucketSeconds": bucketSeconds,
            "sessions": out,
        }

    @app.post(
        "/studies/{study_id}/recipe-runs", dependencies=[Depends(view_auth)]
    )
    def add_recipe_run(
        study_id: str, run: RecipeRunIn, s: Session = Depends(db)
    ) -> dict:
        """Record one analysis-recipe run (MP-07 runner -> FR-DASH-7 cards)."""
        check_study_id(study_id)
        row = RecipeRun(
            study_id=study_id,
            recipe_id=run.recipeId,
            answers=run.answers,
            status=run.status,
            note=run.note,
            at=now(),
        )
        s.add(row)
        s.flush()
        return {"id": row.id}

    @app.get(
        "/studies/{study_id}/recipe-runs", dependencies=[Depends(view_auth)]
    )
    def list_recipe_runs(study_id: str, s: Session = Depends(db)) -> list[dict]:
        check_study_id(study_id)
        return [
            {
                "id": r.id,
                "recipeId": r.recipe_id,
                "answers": r.answers,
                "status": r.status,
                "note": r.note,
                "at": r.at,
            }
            for r in s.scalars(
                select(RecipeRun)
                .where(RecipeRun.study_id == study_id)
                .order_by(RecipeRun.id)
            )
        ]

    @app.get("/files", dependencies=[Depends(view_auth)])
    def list_files(s: Session = Depends(db)) -> list[dict]:
        return [
            {
                "id": f.id,
                "filename": f.filename,
                "contentType": f.content_type,
                "size": f.size,
                "sha256": f.sha256,
                "sessionId": f.session_id,
                "participantId": f.participant_id,
                "uploadedAt": f.uploaded_at,
            }
            for f in s.scalars(select(StoredFile).order_by(StoredFile.id))
        ]

    # ---------------------------------------------------------------- papers

    @app.post(
        "/studies/{study_id}/papers/zotero-import",
        dependencies=[Depends(view_auth)],
    )
    def import_zotero_collection(
        study_id: str, body: ZoteroImportIn, s: Session = Depends(db)
    ) -> dict:
        """Read one Zotero collection (local API, web fallback) into the
        study's paper set (FR-LIT-5, D9). Idempotent on (study, paperRef):
        re-importing a grown collection adds only the new papers."""
        check_study_id(study_id)
        try:
            items, source = zotero.fetch_collection_items(
                body.collection,
                local_url=settings.zotero_local_url,
                user_id=settings.zotero_user_id,
                api_key=settings.zotero_api_key,
            )
        except zotero.ZoteroError as exc:
            raise HTTPException(502, str(exc)) from exc
        received = now()
        imported = duplicates = skipped = 0
        refs = []
        for item in items:
            record = zotero.normalize_item(item)
            if record is None:
                skipped += 1
                continue
            stmt = (
                sqlite_insert(Paper)
                .values(
                    study_id=study_id,
                    paper_ref=record["paperRef"],
                    title=record["title"],
                    authors=record["authors"],
                    year=record["year"],
                    venue=record["venue"],
                    abstract=record["abstract"],
                    doi=record["doi"],
                    arxiv_id=record["arxivId"],
                    url=record["url"],
                    item_type=record["itemType"],
                    source="zotero",
                    zotero_key=record["zoteroKey"],
                    added_at=received,
                )
                .on_conflict_do_nothing(
                    index_elements=["study_id", "paper_ref"]
                )
            )
            inserted = s.execute(stmt).rowcount
            imported += inserted
            duplicates += 1 - inserted
            refs.append(record["paperRef"])
        return {
            "received": len(items),
            "imported": imported,
            "duplicates": duplicates,
            "skipped": skipped,
            "source": source,
            "paperRefs": refs,
        }

    @app.get("/studies/{study_id}/papers", dependencies=[Depends(view_auth)])
    def list_papers(study_id: str, s: Session = Depends(db)) -> list[dict]:
        """The study's paper set. ``inProtocolLiterature`` marks papers the
        protocol's ``literature:`` list already cites - links join on the
        canonical paperRef (FR-LIT-3 builds on this in MP-10)."""
        check_study_id(study_id)
        proto_refs = {
            entry.get("paperRef")
            for entry in (protocol_doc or {}).get("literature", [])
        }
        links_by_ref: dict[str, list[str]] = defaultdict(list)
        for ref, target in s.execute(
            select(PaperLink.paper_ref, PaperLink.target).where(
                PaperLink.study_id == study_id
            )
        ):
            links_by_ref[ref].append(target)
        return [
            {
                "paperRef": p.paper_ref,
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "venue": p.venue,
                "abstract": p.abstract,
                "doi": p.doi,
                "arxivId": p.arxiv_id,
                "url": p.url,
                "itemType": p.item_type,
                "source": p.source,
                "zoteroKey": p.zotero_key,
                "citationCount": p.citation_count,
                "hasFullText": bool(p.full_text),
                "links": sorted(links_by_ref.get(p.paper_ref, [])),
                "addedAt": p.added_at,
                "inProtocolLiterature": p.paper_ref in proto_refs,
            }
            for p in s.scalars(
                select(Paper)
                .where(Paper.study_id == study_id)
                .order_by(Paper.id)
            )
        ]

    # --------------------------------------- paper ingest + graph (MP-10)

    def cached_fetch(s: Session):
        """A Semantic Scholar GET wrapped in the DB cache (D8, NFR-7): the
        graph renders offline after the first fetch. Tests monkeypatch
        ``semantic_scholar.get_json``, which this calls on a cache miss."""

        def fetch(url: str) -> object:
            hit = s.scalar(select(S2Cache).where(S2Cache.url == url))
            if hit is not None:
                return hit.body
            body = semantic_scholar.get_json(url)
            s.add(S2Cache(url=url, body=body, fetched_at=now()))
            return body

        return fetch

    def upsert_paper(s: Session, study_id: str, record: dict, *, source: str) -> None:
        """Insert-or-update one paper record and (re)index its text."""
        stmt = (
            sqlite_insert(Paper)
            .values(
                study_id=study_id,
                paper_ref=record["paperRef"],
                title=record.get("title", ""),
                authors=record.get("authors", []),
                year=record.get("year"),
                venue=record.get("venue", ""),
                abstract=record.get("abstract", ""),
                doi=record.get("doi", ""),
                arxiv_id=record.get("arxivId", ""),
                url=record.get("url", ""),
                item_type=record.get("itemType", "paper"),
                source=source,
                s2_id=record.get("s2Id", ""),
                citation_count=record.get("citationCount"),
                full_text=record.get("fullText", ""),
                added_at=now(),
            )
            .on_conflict_do_update(
                index_elements=["study_id", "paper_ref"],
                set_={
                    "title": record.get("title", ""),
                    "abstract": record.get("abstract", ""),
                    "s2_id": record.get("s2Id", ""),
                    "citation_count": record.get("citationCount"),
                    **(
                        {"full_text": record["fullText"]}
                        if record.get("fullText")
                        else {}
                    ),
                },
            )
        )
        s.execute(stmt)
        paper_index.index_paper(
            s,
            record["paperRef"],
            record.get("title", ""),
            record.get("fullText") or record.get("abstract", ""),
        )
        _seed_links(s, study_id, record["paperRef"])

    def _seed_links(s: Session, study_id: str, paper_ref: str) -> None:
        """Seed a newly-ingested paper's protocol links from the protocol's
        ``literature:`` list (FR-LIT-3), idempotently."""
        for target in assistant.protocol_literature_targets(protocol_doc).get(
            paper_ref, []
        ):
            s.execute(
                sqlite_insert(PaperLink)
                .values(study_id=study_id, paper_ref=paper_ref, target=target)
                .on_conflict_do_nothing(
                    index_elements=["study_id", "paper_ref", "target"]
                )
            )

    def harvest_edges(s: Session, study_id: str, paper_ref: str) -> int:
        """Fetch and store the paper's graph neighbourhood (FR-LIT-2). Best
        effort - S2 failure leaves any existing edges intact."""
        try:
            edges = semantic_scholar.fetch_edges(paper_ref, fetch=cached_fetch(s))
        except semantic_scholar.SemanticScholarError as exc:
            log_finding(
                s, "papers/graph", "FR-LIT-2",
                f"edge harvest failed for {paper_ref}: {exc}", {},
            )
            return 0
        n = 0
        for kind, neighbours in edges.items():
            for nb in neighbours:
                dst = nb["paperRef"]
                if dst == paper_ref:
                    continue
                stmt = (
                    sqlite_insert(PaperEdge)
                    .values(
                        study_id=study_id, src_ref=paper_ref, dst_ref=dst,
                        kind=kind, dst_title=nb.get("title", ""),
                        dst_year=nb.get("year"),
                        dst_citation_count=nb.get("citationCount"),
                    )
                    .on_conflict_do_nothing(
                        index_elements=["study_id", "src_ref", "dst_ref", "kind"]
                    )
                )
                n += s.execute(stmt).rowcount
        return n

    @app.post("/studies/{study_id}/papers", dependencies=[Depends(view_auth)])
    def ingest_paper(
        study_id: str, body: PaperIngestIn, s: Session = Depends(db)
    ) -> dict:
        """Ingest one paper by arXiv id / DOI (FR-LIT-1 id path): fetch S2
        metadata, index it, and harvest its graph neighbourhood (FR-LIT-2).
        PDF upload is the sibling ``/papers/upload`` route."""
        check_study_id(study_id)
        if body.arxivId:
            ref = f"arxiv:{body.arxivId.strip()}"
        elif body.doi:
            ref = f"doi:{body.doi.strip().lower()}"
        else:
            raise HTTPException(400, "provide arxivId or doi")
        try:
            record = semantic_scholar.fetch_paper(ref, fetch=cached_fetch(s))
        except semantic_scholar.SemanticScholarError as exc:
            raise HTTPException(502, f"Semantic Scholar: {exc}") from exc
        upsert_paper(s, study_id, record, source="id")
        edges = harvest_edges(s, study_id, record["paperRef"])
        return {"paperRef": record["paperRef"], "title": record["title"],
                "edges": edges}

    @app.post(
        "/studies/{study_id}/papers/upload", dependencies=[Depends(view_auth)]
    )
    async def ingest_paper_pdf(
        study_id: str, file: UploadFile, s: Session = Depends(db)
    ) -> dict:
        """Ingest a paper from a PDF (FR-LIT-1 PDF path): extract text + a
        title guess locally (D21), then enrich by DOI/title via S2 when
        possible. Falls back to metadata-from-PDF if S2 can't resolve it."""
        check_study_id(study_id)
        content = await file.read()
        extracted = pdf.extract(content)
        record = None
        title = extracted["title"] or (file.filename or "uploaded.pdf")
        try:
            hits = semantic_scholar.get_json(
                f"{semantic_scholar.GRAPH_API}/paper/search?"
                f"query={_urlquote(title)}&fields={semantic_scholar.PAPER_FIELDS}&limit=1"
            )
            papers = hits.get("data") if isinstance(hits, dict) else None
            if papers:
                record = semantic_scholar.normalize_paper(papers[0])
        except semantic_scholar.SemanticScholarError:
            record = None
        if record is None:
            digest = sha256(content).hexdigest()[:16]
            record = {"paperRef": f"pdf:{digest}", "title": title,
                      "authors": [], "abstract": ""}
        record["fullText"] = extracted["text"]
        upsert_paper(s, study_id, record, source="upload")
        edges = 0
        if not record["paperRef"].startswith("pdf:"):
            edges = harvest_edges(s, study_id, record["paperRef"])
        return {"paperRef": record["paperRef"], "title": record["title"],
                "textChars": len(extracted["text"]), "edges": edges}

    @app.delete(
        "/studies/{study_id}/papers/{paper_ref:path}",
        dependencies=[Depends(view_auth)],
    )
    def delete_paper(
        study_id: str, paper_ref: str, s: Session = Depends(db)
    ) -> dict:
        check_study_id(study_id)
        deleted = s.execute(
            select(Paper).where(
                Paper.study_id == study_id, Paper.paper_ref == paper_ref
            )
        ).scalar_one_or_none()
        if deleted is None:
            raise HTTPException(404, f"no paper {paper_ref!r}")
        s.delete(deleted)
        for edge in s.scalars(
            select(PaperEdge).where(
                PaperEdge.study_id == study_id,
                (PaperEdge.src_ref == paper_ref) | (PaperEdge.dst_ref == paper_ref),
            )
        ):
            s.delete(edge)
        for link in s.scalars(
            select(PaperLink).where(
                PaperLink.study_id == study_id, PaperLink.paper_ref == paper_ref
            )
        ):
            s.delete(link)
        paper_index.deindex_paper(s, paper_ref)
        return {"deleted": paper_ref}

    @app.get(
        "/studies/{study_id}/papers/graph", dependencies=[Depends(view_auth)]
    )
    def papers_graph(study_id: str, s: Session = Depends(db)) -> dict:
        """The related-papers graph (FR-LIT-2): ingested nodes (solid) plus
        suggested stub nodes (hollow, un-ingested), and the typed edges
        between them - the ResearchRabbit-style view's data."""
        check_study_id(study_id)
        ingested = {
            p.paper_ref: p
            for p in s.scalars(select(Paper).where(Paper.study_id == study_id))
        }
        edges = list(
            s.scalars(select(PaperEdge).where(PaperEdge.study_id == study_id))
        )
        nodes: dict[str, dict] = {}
        for ref, p in ingested.items():
            nodes[ref] = {
                "paperRef": ref, "title": p.title, "year": p.year,
                "citationCount": p.citation_count, "ingested": True,
            }
        for e in edges:
            if e.dst_ref not in nodes:
                nodes[e.dst_ref] = {
                    "paperRef": e.dst_ref, "title": e.dst_title,
                    "year": e.dst_year, "citationCount": e.dst_citation_count,
                    "ingested": False,
                }
        return {
            "studyId": study_id,
            "nodes": sorted(nodes.values(), key=lambda n: not n["ingested"]),
            "edges": [
                {"src": e.src_ref, "dst": e.dst_ref, "kind": e.kind}
                for e in edges
            ],
        }

    @app.get(
        "/studies/{study_id}/papers/{paper_ref:path}/links",
        dependencies=[Depends(view_auth)],
    )
    def get_paper_links(
        study_id: str, paper_ref: str, s: Session = Depends(db)
    ) -> dict:
        check_study_id(study_id)
        targets = sorted(
            s.scalars(
                select(PaperLink.target).where(
                    PaperLink.study_id == study_id,
                    PaperLink.paper_ref == paper_ref,
                )
            )
        )
        return {"paperRef": paper_ref, "links": targets}

    @app.put(
        "/studies/{study_id}/papers/{paper_ref:path}/links",
        dependencies=[Depends(view_auth)],
    )
    def set_paper_links(
        study_id: str, paper_ref: str, body: PaperLinksIn,
        s: Session = Depends(db),
    ) -> dict:
        """Replace a paper's protocol-element links (FR-LIT-3). Targets use
        the protocol's justification vocabulary (``RQ-P2``,
        ``metric:parameter_count``, ...)."""
        check_study_id(study_id)
        for link in s.scalars(
            select(PaperLink).where(
                PaperLink.study_id == study_id, PaperLink.paper_ref == paper_ref
            )
        ):
            s.delete(link)
        s.flush()
        wanted = sorted({t.strip() for t in body.targets if t.strip()})
        for target in wanted:
            s.add(PaperLink(study_id=study_id, paper_ref=paper_ref, target=target))
        return {"paperRef": paper_ref, "links": wanted}

    @app.get(
        "/studies/{study_id}/assistant/config", dependencies=[Depends(view_auth)]
    )
    def assistant_config(study_id: str) -> dict:
        """Whether the assistant is configured and which Mistral model tiers
        the dashboard may pick (D32 rev 2). Never exposes the key itself."""
        check_study_id(study_id)
        ready = assistant.configured()
        return {
            "configured": ready,
            "models": list(assistant.MISTRAL_MODELS) if ready else [],
            "defaultModel": assistant.MISTRAL_MODEL,
        }

    @app.post("/studies/{study_id}/assistant", dependencies=[Depends(view_auth)])
    def knowledge_assistant(
        study_id: str, body: AssistantIn, s: Session = Depends(db)
    ) -> dict:
        """Grounded Q&A over papers + protocol + dataset *aggregates*
        (FR-LIT-4). FR-ETH-4 is enforced in ``assistant.build_tools`` - no
        tool can return a row-level participant event. Absent an API key the
        endpoint degrades gracefully (503); everything else stays offline."""
        check_study_id(study_id)
        client = assistant.make_client(body.model)
        if client is None:
            raise HTTPException(
                503,
                "knowledge assistant unavailable: set MISTRAL_API_KEY. "
                "All other views work offline.",
            )
        tools = assistant.build_tools(s, protocol_doc)
        try:
            return assistant.answer_question(
                body.question, body.history, tools=tools, client=client
            )
        except Exception as exc:  # noqa: BLE001 - never 500 the panel
            raise HTTPException(502, f"assistant error: {exc}") from exc

    # ------------------------------------- operational findings (FR-META-1)

    @app.post("/findings")
    def add_finding(finding: FindingIn, s: Session = Depends(db)) -> dict:
        """Record one operational finding (FR-META-1). Open to the facilitator
        (their friction notes during a session) and to researcher tools like
        the analysis runner (recipe requires-failures)."""
        s.add(
            Finding(
                at=now(), source=finding.source, kind=finding.kind,
                requirement_id=finding.requirementId, message=finding.message,
                context=finding.context, status=finding.status,
            )
        )
        return {"ok": True}

    @app.get("/findings", dependencies=[Depends(view_auth)])
    def list_findings(s: Session = Depends(db)) -> list[dict]:
        rows = s.scalars(select(Finding).order_by(Finding.id))
        return [_finding_json(f) for f in rows]

    @app.post(
        "/studies/{study_id}/findings/scan", dependencies=[Depends(view_auth)]
    )
    def scan_findings(study_id: str, s: Session = Depends(db)) -> dict:
        """Auto-write the read-detectable operational findings (FR-META-1):
        per-producer seq gaps (FR-ING-3) and unsatisfied current-phase gate
        blocks (FR-PROT-3). Idempotent - each defect is logged once (keyed on
        ``(kind, context)``), so re-scanning reflects the current state
        without duplicating rows."""
        check_study_id(study_id)
        existing = {
            (f.kind, json.dumps(f.context, sort_keys=True))
            for f in s.scalars(select(Finding))
        }
        written = 0

        def emit(kind: str, req: str, message: str, context: dict) -> None:
            nonlocal written
            key = (kind, json.dumps(context, sort_keys=True))
            if key in existing:
                return
            existing.add(key)
            log_finding(s, source="findings/scan", requirement_id=req,
                        message=message, context=context, kind=kind)
            written += 1

        # Seq gaps, per (session, source).
        by: dict[tuple[str, str], list[int]] = defaultdict(list)
        for sid, src, seq in s.execute(
            select(Event.session_id, Event.source, Event.seq)
        ):
            by[(sid, src)].append(seq)
        for (sid, src), seqs in by.items():
            summary = _gap_summary(sorted(seqs))
            if summary["gaps"]:
                missing = summary["expected"] - summary["received"]
                emit(
                    "seq-gap", "FR-ING-3",
                    f"{sid} ({src}): {len(summary['gaps'])} seq gap(s), "
                    f"{missing} event(s) missing",
                    {"session": sid, "source": src},
                )

        # Gate blocks: the current phase's unsatisfied gates.
        if protocol_doc is not None:
            files = _stored_files(s)
            declared = {
                p["name"]: list(p.get("gates", [])) for p in protocol_doc["phases"]
            }
            current = current_phase(protocol_doc, set(files))
            for gate in declared.get(current, []):
                if gate not in files:
                    emit(
                        "gate-block", "FR-PROT-3",
                        f"phase {current!r} blocked: gate artifact {gate!r} missing",
                        {"phase": current, "gate": gate},
                    )
        return {"written": written}

    @app.post("/tasks", dependencies=[Depends(view_auth)])
    def add_task(task: TaskIn, s: Session = Depends(db)) -> dict:
        card = TaskCard(title=task.title, note=task.note, created_at=now())
        s.add(card)
        s.flush()
        return {"id": card.id}

    @app.get("/tasks", dependencies=[Depends(view_auth)])
    def list_tasks(status: str | None = None, s: Session = Depends(db)) -> list[dict]:
        q = select(TaskCard).order_by(TaskCard.id)
        if status:
            q = q.where(TaskCard.status == status)
        return [
            {"id": t.id, "title": t.title, "status": t.status, "note": t.note,
             "createdAt": t.created_at}
            for t in s.scalars(q)
        ]

    @app.patch("/tasks/{task_id}", dependencies=[Depends(view_auth)])
    def patch_task(task_id: int, patch: TaskPatch, s: Session = Depends(db)) -> dict:
        card = s.get(TaskCard, task_id)
        if card is None:
            raise HTTPException(404, f"no task {task_id}")
        card.status = patch.status
        return {"id": card.id, "status": card.status}

    # ------------------------- requirements of record (FR-DASH-9 tooltips)

    @app.get("/requirements", dependencies=[Depends(view_auth)])
    def list_requirements() -> list[dict]:
        """The SRS, parsed live from ``srs.md`` - dashboard tooltip text
        comes from the document of record and cannot drift."""
        return parse_srs(settings.requirements_dir / "srs.md")

    @app.get("/glossary", dependencies=[Depends(view_auth)])
    def list_glossary() -> list[dict]:
        """The project glossary, parsed live from ``glossary.md``."""
        return parse_glossary(settings.requirements_dir / "glossary.md")

    # ---------------------------------------------------------------- health

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "studyId": check.study_id,
            "protocolLoaded": protocol_doc is not None,
            "knownEventSchemaVersions": sorted(KNOWN_EVENT_SCHEMA_VERSIONS),
        }

    @app.get("/auth/config")
    def auth_config() -> dict:
        """Which sign-in surface the dashboard should render (FR-OPS-5).

        Open by necessity (the dashboard asks before it can sign in);
        carries no secrets - see ``auth.public_config``.
        """
        return auth.public_config(settings)

    # ---------------------------------------------- dashboard SPA (NFR-7)
    # Production mode serves the built dashboard from the same process:
    # `docker compose up` is the whole stack. Dev mode uses the Vite proxy
    # instead, so a missing build directory just means API-only.

    dist = settings.dashboard_dist
    index_html = dist / "index.html"
    if index_html.is_file():

        @app.get("/", include_in_schema=False)
        def spa_index() -> FileResponse:
            return FileResponse(index_html)

        @app.get("/study/{rest:path}", include_in_schema=False)
        def spa_route(rest: str) -> FileResponse:
            # Client-side routing (MP-06): deep links re-serve the shell.
            return FileResponse(index_html)

        app.mount("/", StaticFiles(directory=dist), name="dashboard")

    return app


def _gap_summary(seqs: list[int]) -> dict:
    """Seq-gap integrity summary for one session's sorted ``seq`` list
    (FR-ING-3): loss is never silent, it is a report."""
    missing = []
    for prev, nxt in zip(seqs, seqs[1:], strict=False):
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
    """Aggregate one session's per-producer gap facts (MP-12).

    Each ``source`` owns a contiguous ``seq`` stream, so gaps are counted
    within a stream and summed; the session is ``complete`` only when every
    producer stream is (and there is at least one).
    """
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


def _finding_json(f: Finding) -> dict:
    return {
        "id": f.id,
        "at": f.at,
        "source": f.source,
        "kind": f.kind,
        "requirementId": f.requirement_id,
        "message": f.message,
        "context": f.context,
        "status": f.status,
    }


def _event_json(e: Event) -> dict:
    return {
        "v": e.v,
        "ts": e.ts,
        "mono": e.mono,
        "sessionId": e.session_id,
        "source": e.source,
        "participantId": e.participant_id,
        "condition": e.condition,
        "seq": e.seq,
        "type": e.type,
        "payload": e.payload,
        "flags": e.flags,
    }
