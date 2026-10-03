"""FastAPI ingestion service (FR-ING-1..6)."""

import copy
import itertools
import json
import logging
import os
import re
import secrets
from collections import defaultdict
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote as _urlquote

import yaml
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import (
    FileResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from protocol.assignment import assign, tasks_of
from protocol.capture import (
    producer_capabilities,
    required_producers,
)
from protocol.errors import ProtocolError
from sqlalchemy import func, select
from sqlalchemy import text as sqltext
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from middleware import (
    assistant,
    auth,
    authz,
    compiler,
    corpus_enrich,
    corpus_importer,
    design_assistant,
    elicitation,
    enrollment,
    matching,
    paper_index,
    pdf,
    semantic_scholar,
    template_registry,
    template_repertoire,
)
from middleware import demo as demo_mod
from middleware.db import (
    CORPUS_STUDY_ID,
    IMPLICIT_PROJECT_ID,
    ApprovalEvent,
    Compilation,
    ConversationTurn,
    DesignMoveRow,
    EnrollmentToken,
    Event,
    Invitation,
    Membership,
    MetricRow,
    Paper,
    PaperEdge,
    PaperLink,
    Project,
    ProtocolDraftRow,
    RecipeRun,
    S2Cache,
    SessionBlock,
    SessionOpen,
    StoredFile,
    Study,
    UserProfile,
    get_engine,
    make_session_factory,
)
from middleware.schemas import (
    ApproveIn,
    CompileIn,
    ConversationTurnIn,
    DecisionTriggerIn,
    EventBatch,
    FromGraphIn,
    FromMatchIn,
    MatchIn,
    MintTokensIn,
    MoveDecisionIn,
    PaperIngestIn,
    PaperLinksIn,
    QuickProtocolIn,
    RecipeRunIn,
    RedeemIn,
    SessionStartIn,
    SimulateIn,
    StudyEventIn,
    TemplateInstantiateIn,
    ToggleIn,
)
from middleware.settings import Settings

KNOWN_EVENT_SCHEMA_VERSIONS = {2, 3, 4, 5}

DEFAULT_SOURCE = "tern"

LEGACY_SOURCES = {"cognitive-overlay"}


def canonical_source(source: str) -> str:
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


log = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _slug_from_text(text: str, max_len: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(slug) <= max_len:
        return slug
    truncated = slug[:max_len]
    boundary = truncated.rfind("-")
    return truncated[:boundary] if boundary > 0 else truncated


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or Settings()
    clock = clock or (lambda: datetime.now(UTC))
    session_factory = make_session_factory(settings.db_url)

    protocol_doc = None
    if settings.protocol_path is not None:
        from protocol.loader import load_protocol

        protocol_doc = load_protocol(settings.protocol_path)
    check = _ProtocolCheck(protocol_doc)

    def _resolve_study_protocol(s: Session, study_id: str) -> dict | None:
        import yaml

        from middleware.db import ProtocolDraftRow

        draft = s.get(ProtocolDraftRow, study_id)
        if draft is not None and draft.yaml:
            return yaml.safe_load(draft.yaml)
        if protocol_doc is not None and protocol_doc["study"]["id"] == study_id:
            return protocol_doc
        return None

    if check.study_id is not None:
        with session_factory() as s:
            _ensure_study_row(s, check.study_id, protocol_doc)
            s.commit()

    app = FastAPI(title="Study ingestion middleware", version="0.1.0")

    bootstrap_override = os.environ.get("MIDDLEWARE_CORPUS_BOOTSTRAP")
    default_db = settings.db_path is not None and (
        Path(settings.db_path).name == "middleware.sqlite3"
    )
    should_bootstrap = (
        bootstrap_override.lower() not in {"0", "false", "no"}
        if bootstrap_override is not None
        else bool(settings.database_url or default_db)
    )
    if should_bootstrap:
        corpus_importer.start_background_import(settings.db_url, session_factory)

    if settings.cors_origins:
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def db() -> Session:
        session = session_factory()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    def now() -> str:
        return clock().isoformat(timespec="milliseconds")

    def check_study_id(study_id: str) -> None:
        if check.study_id is not None and study_id != check.study_id:
            raise HTTPException(
                404,
                f"unknown study {study_id!r}; this deployment serves "
                f"{check.study_id!r}",
            )

    verify_view_auth = auth.verifier_from_settings(settings)

    def view_auth(authorization: str = Header(default="")) -> None:
        verify_view_auth(authorization)

    authz_dep = authz.build_authz(
        session_factory, verify_view_auth, loaded_study_id=lambda: check.study_id
    )
    require_project = authz_dep["require_project"]
    require_project_for_study = authz_dep["require_project_for_study"]
    require_project_for_session = authz_dep["require_project_for_session"]
    resolve_identity = authz_dep["resolve_identity"]

    def require_protocol() -> dict:
        if protocol_doc is None:
            raise HTTPException(404, "no protocol loaded; set MIDDLEWARE_PROTOCOL")
        return protocol_doc

    @app.post("/ingest/events")
    def ingest_events(
        batch: EventBatch | list[StudyEventIn],
        authorization: str = Header(default=""),
        s: Session = Depends(db),
    ) -> dict:
        events = batch if isinstance(batch, list) else batch.events
        batch_source = "" if isinstance(batch, list) else batch.source
        received = now()
        cred_row = resolve_credential(s, authorization)
        bearer_present = authorization.startswith("Bearer ")
        flagged = 0
        rows = []
        blocks = {
            b.session_id: b
            for b in s.scalars(
                select(SessionBlock).where(
                    SessionBlock.session_id.in_({e.sessionId for e in events})
                )
            )
        }
        for e in events:
            pid, cond = e.participantId, e.condition
            block = blocks.get(e.sessionId)
            extra_flags: list[str] = []
            if cred_row is not None:
                expected = block.condition if block else cred_row.condition
                if (e.participantId and e.participantId != cred_row.participant_id) or (
                    e.condition and e.condition != expected
                ):
                    extra_flags.append("credential-mismatch")
                pid, cond = cred_row.participant_id, expected
            elif bearer_present:
                extra_flags.append("unauthenticated")
            flags = check.flags_for(pid, cond, e.v) + extra_flags
            if block and e.taskId != block.task_id:
                flags.append("task-mismatch")
            flagged += bool(flags)
            rows.append(
                {
                    "session_id": e.sessionId,
                    "source": canonical_source(
                        e.source or batch_source or DEFAULT_SOURCE
                    ),
                    "seq": e.seq,
                    "participant_id": pid,
                    "condition": cond,
                    "task_id": block.task_id if block else "",
                    "v": e.v,
                    "ts": e.ts,
                    "mono": e.mono,
                    "type": e.type,
                    "payload": e.payload,
                    "flags": flags,
                    "received_at": received,
                }
            )
        from middleware.ingest_core import store_events

        inserted = store_events(s, rows, received)
        if flagged:
            log.warning(
                "%d/%d events stored with integrity flags (sessions: %s)",
                flagged,
                len(rows),
                ", ".join(sorted({r["session_id"] for r in rows})),
            )
        return {
            "received": len(rows),
            "inserted": inserted,
            "duplicates": len(rows) - inserted,
            "flagged": flagged,
        }

    @app.post("/ingest/metrics")
    def ingest_metrics(rows: list[dict], s: Session = Depends(db)) -> dict:
        from middleware.ingest_core import store_metric_rows

        received = now()
        flagged = 0
        flags_by_row: list[list[str]] = []
        for row in rows:
            participant_id = str(row.get("participantId", ""))
            condition = str(row.get("condition", ""))
            session_id = str(row.get("sessionId", ""))
            task_id = str(row.get("taskId", ""))
            flags = check.flags_for(participant_id, condition, None)
            if not session_id:
                flags.append("missing-session")
            if not row.get("metricId"):
                flags.append("missing-metric-identity")
            if not row.get("schemaVersion"):
                flags.append("missing-schema-version")
            if not row.get("timestamp"):
                flags.append("missing-timestamp")
            if row.get("source", "metrics") != "metrics":
                flags.append("source-mismatch")
            block = s.get(SessionBlock, session_id) if session_id else None
            if block:
                if participant_id and participant_id != block.participant_id:
                    flags.append("credential-mismatch")
                if condition and condition != block.condition:
                    flags.append("condition-mismatch")
                if task_id != block.task_id:
                    flags.append("task-mismatch")
            elif session_id:
                flags.append("unknown-session")
            flagged += bool(flags)
            flags_by_row.append(flags)
        inserted = store_metric_rows(s, rows, received, flags_by_row)
        if flagged:
            log.warning(
                "%d/%d metric rows stored with integrity flags", flagged, len(rows)
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
        sessionId: str | None = Form(default=None),
        participantId: str | None = Form(default=None),
        studyId: str | None = Form(default=None),
        s: Session = Depends(db),
    ) -> dict:
        content = await file.read()
        digest = sha256(content).hexdigest()
        existing = s.scalar(
            select(StoredFile).where(
                StoredFile.sha256 == digest,
                StoredFile.filename == (file.filename or "unnamed"),
                StoredFile.study_id == studyId,
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
            study_id=studyId,
            uploaded_at=now(),
        )
        s.add(record)
        s.flush()
        return {"id": record.id, "sha256": digest, "duplicate": False}

    from middleware.study_data import StudyData

    study_data = StudyData(check.study_id, settings.auth)
    _session_scope = study_data.scope
    _joined_rows = study_data.rows
    from middleware.routes.exports import export_router

    app.include_router(
        export_router(
            db, require_project_for_study, _resolve_study_protocol, study_data
        )
    )

    @app.get(
        "/studies/{study_id}/sessions",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def list_sessions(
        study_id: str, s: Session = Depends(db), includeSynthetic: bool = False
    ) -> list[dict]:
        in_this_study = _session_scope(study_id, includeSynthetic)

        out = {}
        event_rows = s.execute(
            select(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                Event.task_id,
                func.count(),
                func.min(Event.ts),
                func.max(Event.ts),
            )
            .where(in_this_study(Event.session_id))
            .group_by(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                Event.task_id,
            )
        ).all()
        for sid, pid, cond, task_id, n, first, last in event_rows:
            out[sid] = {
                "sessionId": sid,
                "participantId": pid,
                "condition": cond,
                "taskId": task_id,
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
                MetricRow.task_id,
                func.count(),
            )
            .where(in_this_study(MetricRow.session_id))
            .group_by(
                MetricRow.session_id,
                MetricRow.participant_id,
                MetricRow.condition,
                MetricRow.task_id,
            )
        ).all()
        for sid, pid, cond, task_id, n in metric_rows:
            entry = out.setdefault(
                sid,
                {
                    "sessionId": sid,
                    "participantId": pid,
                    "condition": cond,
                    "taskId": task_id,
                    "events": 0,
                    "metricRows": 0,
                    "firstTs": None,
                    "lastTs": None,
                },
            )
            entry["metricRows"] = n
            entry["taskId"] = entry.get("taskId") or task_id
        return sorted(out.values(), key=lambda e: e["sessionId"])

    @app.get(
        "/sessions/{session_id}/events",
        dependencies=[Depends(require_project_for_session("view"))],
    )
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

    @app.get(
        "/sessions/{session_id}/gaps",
        dependencies=[Depends(require_project_for_session("view"))],
    )
    def session_gaps(session_id: str, s: Session = Depends(db)) -> dict:
        by_source: dict[str, list[int]] = defaultdict(list)
        for src, seq in s.execute(
            select(Event.source, Event.seq).where(Event.session_id == session_id)
        ):
            by_source[src].append(seq)
        if not by_source:
            raise HTTPException(404, f"no events for session {session_id!r}")
        summaries = {src: _gap_summary(sorted(seqs)) for src, seqs in by_source.items()}
        primary = DEFAULT_SOURCE if DEFAULT_SOURCE in summaries else min(summaries)
        return {
            "sessionId": session_id,
            **summaries[primary],
            "sources": [{"source": src, **summaries[src]} for src in sorted(summaries)],
        }

    @app.get(
        "/studies/{study_id}/protocol",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def study_protocol(study_id: str, s: Session = Depends(db)) -> dict:

        proto = _resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")
        recipes_by_rq = {
            p["rq"]: list(p.get("recipes", [])) for p in proto.get("analysisPlan", [])
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
            "document": proto,
        }

    @app.get(
        "/studies/{study_id}/status",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def study_status(
        study_id: str, s: Session = Depends(db), includeSynthetic: bool = False
    ) -> dict:

        proto = _resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")

        in_this_study = _session_scope(study_id, includeSynthetic)

        seqs_by_session: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        source_counts_by_session: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        for sid, src, seq in s.execute(
            select(Event.session_id, Event.source, Event.seq).where(
                in_this_study(Event.session_id)
            )
        ):
            seqs_by_session[sid][src].append(seq)
            source_counts_by_session[sid][src] += 1

        flag_kinds: dict[str, set[str]] = defaultdict(set)
        flagged_events: dict[str, int] = defaultdict(int)
        for sid, flags in s.execute(
            select(Event.session_id, Event.flags).where(
                func.json_array_length(Event.flags) > 0,
                in_this_study(Event.session_id),
            )
        ):
            flagged_events[sid] += 1
            flag_kinds[sid].update(flags)

        sessions = {}
        for sid, pid, cond, task_id, n, last_recv in s.execute(
            select(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                Event.task_id,
                func.count(),
                func.max(Event.received_at),
            )
            .where(in_this_study(Event.session_id))
            .group_by(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                Event.task_id,
            )
        ):
            agg = _session_gap_facts(seqs_by_session[sid])
            sessions[sid] = {
                "sessionId": sid,
                "participantId": pid,
                "condition": cond,
                "taskId": task_id,
                "events": n,
                "metricRows": 0,
                "sourceCounts": dict(source_counts_by_session[sid]),
                "flaggedEvents": flagged_events.get(sid, 0),
                "flagKinds": sorted(flag_kinds.get(sid, ())),
                "gapCount": agg["gapCount"],
                "missingEvents": agg["missingEvents"],
                "complete": agg["complete"],
                "lastReceivedAt": last_recv,
            }
        for sid, pid, cond, task_id, n in s.execute(
            select(
                MetricRow.session_id,
                MetricRow.participant_id,
                MetricRow.condition,
                MetricRow.task_id,
                func.count(),
            )
            .where(in_this_study(MetricRow.session_id))
            .group_by(
                MetricRow.session_id,
                MetricRow.participant_id,
                MetricRow.condition,
                MetricRow.task_id,
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
                    "sourceCounts": {},
                    "flaggedEvents": 0,
                    "flagKinds": [],
                    "gapCount": 0,
                    "missingEvents": 0,
                    "complete": False,
                    "lastReceivedAt": None,
                },
            )
            entry["metricRows"] = n
            entry["taskId"] = entry.get("taskId") or task_id
            entry["sourceCounts"]["metrics"] = n

        participants = proto.get("participants", {})
        within = participants.get("design") == "within-subjects"
        conditions = list(proto.get("conditions", []))
        recipes_by_rq = {
            p["rq"]: list(p.get("recipes", [])) for p in proto.get("analysisPlan", [])
        }
        ran = set(
            s.scalars(
                select(RecipeRun.recipe_id).where(
                    RecipeRun.study_id == proto["study"]["id"], RecipeRun.status == "ok"
                )
            )
        )
        return {
            "studyId": proto["study"]["id"],
            "generatedAt": now(),
            "conditions": conditions,
            "plannedParticipants": int(participants.get("planned", 0)),
            "plannedSessionsPerParticipant": len(conditions) if within else 1,
            "sessions": sorted(sessions.values(), key=lambda e: e["sessionId"]),
            "researchQuestions": [
                {
                    "id": rq["id"],
                    "recipes": recipes_by_rq.get(rq["id"], []),
                    "recipeRuns": [
                        r for r in recipes_by_rq.get(rq["id"], []) if r in ran
                    ],
                }
                for rq in proto.get("researchQuestions", [])
            ],
            "producers": producer_capabilities(proto),
            "requiredProducers": required_producers(proto),
        }

    @app.get(
        "/studies/{study_id}/live",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def live_sessions(
        study_id: str,
        windowSeconds: int = 300,
        bucketSeconds: int = 10,
        s: Session = Depends(db),
    ) -> dict:

        now_dt = clock()
        cutoff = (now_dt - timedelta(seconds=windowSeconds)).astimezone(UTC)
        cutoff_s = cutoff.isoformat(timespec="milliseconds")
        buckets = max(1, windowSeconds // bucketSeconds)

        recent = s.scalars(
            select(Event)
            .where(
                Event.received_at >= cutoff_s,
                _session_scope(study_id)(Event.session_id),
            )
            .order_by(Event.received_at, Event.seq)
        ).all()
        by_session: dict[str, list[Event]] = defaultdict(list)
        for e in recent:
            by_session[e.session_id].append(e)

        protocol = _resolve_study_protocol(s, study_id)
        task_titles = {
            t.get("id"): t.get("title", "")
            for t in (tasks_of(protocol) if protocol else [])
        }
        session_blocks = {
            b.session_id: b
            for b in s.scalars(
                select(SessionBlock).where(SessionBlock.session_id.in_(set(by_session)))
            )
        }
        blocks_total: dict[str, int] = {}
        if protocol:
            for row in s.scalars(
                select(EnrollmentToken).where(EnrollmentToken.study_id == study_id)
            ):
                with suppress(ProtocolError):
                    blocks_total[row.participant_id] = len(
                        assign(protocol, row.participant_index or 0)
                    )

        out = []
        for sid, events in sorted(by_session.items()):
            block = session_blocks.get(sid)
            rate = [0] * buckets
            for e in events:
                age = (now_dt - datetime.fromisoformat(e.received_at)).total_seconds()
                offset = min(max(int(age // bucketSeconds), 0), buckets - 1)
                idx = buckets - 1 - offset
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
                    "taskId": last.task_id,
                    "taskTitle": (task_titles.get(last.task_id) or ""),
                    "blockIndex": (block.block_index if block else None),
                    "blocksTotal": blocks_total.get(last.participant_id),
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
        "/studies/{study_id}/recipe-runs",
        dependencies=[Depends(require_project_for_study("run_recipe"))],
    )
    def add_recipe_run(
        study_id: str, run: RecipeRunIn, s: Session = Depends(db)
    ) -> dict:

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
        "/studies/{study_id}/recipe-runs",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def list_recipe_runs(study_id: str, s: Session = Depends(db)) -> list[dict]:

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
                "studyId": f.study_id,
                "participantId": f.participant_id,
                "uploadedAt": f.uploaded_at,
            }
            for f in s.scalars(select(StoredFile).order_by(StoredFile.id))
        ]

    @app.get(
        "/studies/{study_id}/papers",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def list_papers(study_id: str, s: Session = Depends(db)) -> list[dict]:

        study_protocol = _resolve_study_protocol(s, study_id)
        proto_refs = {
            entry.get("paperRef")
            for entry in (study_protocol or {}).get("literature", [])
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
                "citationCount": p.citation_count,
                "hasFullText": bool(p.full_text),
                "links": sorted(links_by_ref.get(p.paper_ref, [])),
                "addedAt": p.added_at,
                "inProtocolLiterature": p.paper_ref in proto_refs,
            }
            for p in s.scalars(
                select(Paper).where(Paper.study_id == study_id).order_by(Paper.id)
            )
        ]

    def cached_fetch(s: Session):

        def fetch(url: str) -> object:
            hit = s.scalar(select(S2Cache).where(S2Cache.url == url))
            if hit is not None:
                return hit.body
            body = semantic_scholar.get_json(url)
            s.add(S2Cache(url=url, body=body, fetched_at=now()))
            return body

        return fetch

    def upsert_paper(s: Session, study_id: str, record: dict, *, source: str) -> None:
        _paper_vals = {
            "study_id": study_id,
            "paper_ref": record["paperRef"],
            "title": record.get("title", ""),
            "authors": record.get("authors", []),
            "year": record.get("year"),
            "venue": record.get("venue", ""),
            "abstract": record.get("abstract", ""),
            "doi": record.get("doi", ""),
            "arxiv_id": record.get("arxivId", ""),
            "url": record.get("url", ""),
            "item_type": record.get("itemType", "paper"),
            "source": source,
            "s2_id": record.get("s2Id", ""),
            "citation_count": record.get("citationCount"),
            "full_text": record.get("fullText", ""),
            "added_at": now(),
        }
        _update_vals = {
            "title": record.get("title", ""),
            "abstract": record.get("abstract", ""),
            "s2_id": record.get("s2Id", ""),
            "citation_count": record.get("citationCount"),
            **({"full_text": record["fullText"]} if record.get("fullText") else {}),
        }
        _engine = get_engine()
        if _engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as _pg_insert

            stmt = (
                _pg_insert(Paper)
                .values([_paper_vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=_update_vals
                )
            )
        else:
            from sqlalchemy.dialects.sqlite import insert as _sq_insert

            stmt = (
                _sq_insert(Paper)
                .values([_paper_vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=_update_vals
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
        _engine = get_engine()
        for target in assistant.protocol_literature_targets(protocol_doc).get(
            paper_ref, []
        ):
            if _engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as _pg_insert

                stmt = (
                    _pg_insert(PaperLink)
                    .values(study_id=study_id, paper_ref=paper_ref, target=target)
                    .on_conflict_do_nothing()
                )
            else:
                from sqlalchemy.dialects.sqlite import insert as _sq_insert

                stmt = (
                    _sq_insert(PaperLink)
                    .values(study_id=study_id, paper_ref=paper_ref, target=target)
                    .on_conflict_do_nothing(
                        index_elements=["study_id", "paper_ref", "target"]
                    )
                )
            s.execute(stmt)

    def _adopt_corpus_edges(s: Session, study_id: str, paper_ref: str) -> int:
        corpus_edges = list(
            s.scalars(
                select(PaperEdge).where(
                    PaperEdge.study_id == CORPUS_STUDY_ID,
                    (PaperEdge.src_ref == paper_ref) | (PaperEdge.dst_ref == paper_ref),
                )
            )
        )
        n = 0
        _engine = get_engine()
        for edge in corpus_edges:
            vals = {
                "study_id": study_id,
                "src_ref": edge.src_ref,
                "dst_ref": edge.dst_ref,
                "kind": edge.kind,
                "dst_title": edge.dst_title,
                "dst_authors": edge.dst_authors,
                "dst_year": edge.dst_year,
                "dst_abstract": edge.dst_abstract,
                "dst_citation_count": edge.dst_citation_count,
            }
            if _engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as _pg_insert

                stmt = _pg_insert(PaperEdge).values([vals]).on_conflict_do_nothing()
            else:
                from sqlalchemy.dialects.sqlite import insert as _sq_insert

                stmt = (
                    _sq_insert(PaperEdge)
                    .values([vals])
                    .on_conflict_do_nothing(
                        index_elements=["study_id", "src_ref", "dst_ref", "kind"]
                    )
                )
            n += len(s.execute(stmt.returning(PaperEdge.id)).fetchall())
        return n

    def harvest_edges(s: Session, study_id: str, paper_ref: str) -> int:
        if (
            s.scalar(
                select(PaperEdge.id).where(
                    PaperEdge.study_id == study_id,
                    PaperEdge.src_ref == paper_ref,
                    PaperEdge.kind.in_(("references", "citations", "recommendations")),
                )
            )
            is not None
        ):
            return 0
        try:
            edges = semantic_scholar.fetch_edges(paper_ref, fetch=cached_fetch(s))
        except semantic_scholar.SemanticScholarError as exc:
            log.warning("edge harvest failed for %s: %s", paper_ref, exc)
            return 0
        n = 0
        _engine = get_engine()
        for kind, neighbours in edges.items():
            for nb in neighbours:
                dst = nb["paperRef"]
                if dst == paper_ref:
                    continue
                _edge_vals = {
                    "study_id": study_id,
                    "src_ref": paper_ref,
                    "dst_ref": dst,
                    "kind": kind,
                    "dst_title": nb.get("title", ""),
                    "dst_authors": nb.get("authors") or None,
                    "dst_year": nb.get("year"),
                    "dst_abstract": nb.get("abstract", ""),
                    "dst_citation_count": nb.get("citationCount"),
                }
                if _engine.dialect.name == "postgresql":
                    from sqlalchemy.dialects.postgresql import insert as _pg_insert

                    stmt = (
                        _pg_insert(PaperEdge)
                        .values([_edge_vals])
                        .on_conflict_do_nothing()
                    )
                else:
                    from sqlalchemy.dialects.sqlite import insert as _sq_insert

                    stmt = (
                        _sq_insert(PaperEdge)
                        .values([_edge_vals])
                        .on_conflict_do_nothing(
                            index_elements=["study_id", "src_ref", "dst_ref", "kind"]
                        )
                    )
                n += len(s.execute(stmt.returning(PaperEdge.id)).fetchall())
        return n

    def harvest_edges_in_background(study_id: str, paper_ref: str) -> None:
        with session_factory() as background_session:
            harvest_edges(background_session, study_id, paper_ref)
            background_session.commit()

    @app.post(
        "/studies/{study_id}/papers",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def ingest_paper(
        study_id: str,
        body: PaperIngestIn,
        background_tasks: BackgroundTasks,
        s: Session = Depends(db),
    ) -> dict:

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
        adopted = _adopt_corpus_edges(s, study_id, record["paperRef"])
        s.commit()
        background_tasks.add_task(
            harvest_edges_in_background, study_id, record["paperRef"]
        )
        return {
            "paperRef": record["paperRef"],
            "title": record["title"],
            "edges": adopted,
            "edgesPending": True,
        }

    @app.post(
        "/studies/{study_id}/papers/upload",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    async def ingest_paper_pdf(
        study_id: str, file: UploadFile, s: Session = Depends(db)
    ) -> dict:

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
            record = {
                "paperRef": f"pdf:{digest}",
                "title": title,
                "authors": [],
                "abstract": "",
            }
        record["fullText"] = extracted["text"]
        upsert_paper(s, study_id, record, source="upload")
        edges = 0
        if not record["paperRef"].startswith("pdf:"):
            edges = harvest_edges(s, study_id, record["paperRef"])
        return {
            "paperRef": record["paperRef"],
            "title": record["title"],
            "textChars": len(extracted["text"]),
            "edges": edges,
        }

    @app.delete(
        "/studies/{study_id}/papers/{paper_ref:path}",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def delete_paper(study_id: str, paper_ref: str, s: Session = Depends(db)) -> dict:

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
        has_another_copy = s.scalar(
            select(Paper.id).where(
                Paper.paper_ref == paper_ref,
                Paper.id != deleted.id,
            )
        )
        if has_another_copy is None:
            paper_index.deindex_paper(s, paper_ref)
        return {"deleted": paper_ref}

    @app.get(
        "/studies/{study_id}/papers/graph",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def papers_graph(study_id: str, s: Session = Depends(db)) -> dict:

        ingested = {
            p.paper_ref: p
            for p in s.scalars(select(Paper).where(Paper.study_id == study_id))
        }
        edges = list(s.scalars(select(PaperEdge).where(PaperEdge.study_id == study_id)))
        nodes: dict[str, dict] = {}
        for ref, p in ingested.items():
            nodes[ref] = {
                "paperRef": ref,
                "title": p.title,
                "authors": p.authors,
                "year": p.year,
                "abstract": p.abstract,
                "citationCount": p.citation_count,
                "ingested": True,
            }

        endpoint_refs = {e.src_ref for e in edges} | {e.dst_ref for e in edges}
        missing_refs = endpoint_refs - nodes.keys()
        paper_metadata: dict[str, Paper] = {}
        if missing_refs:
            for p in s.scalars(
                select(Paper).where(
                    Paper.paper_ref.in_(missing_refs),
                    Paper.study_id.in_([study_id, CORPUS_STUDY_ID]),
                )
            ):
                if p.paper_ref not in paper_metadata or p.study_id == study_id:
                    paper_metadata[p.paper_ref] = p

        for ref in missing_refs:
            p = paper_metadata.get(ref)
            edge_metadata = next(
                (
                    edge
                    for edge in reversed(edges)
                    if edge.dst_ref == ref and edge.dst_title
                ),
                None,
            )
            title = (p.title if p else "") or (
                edge_metadata.dst_title if edge_metadata else ""
            )
            authors = (
                (p.authors if p else None)
                or (edge_metadata.dst_authors if edge_metadata else None)
                or []
            )
            year = (
                p.year
                if p and p.year is not None
                else (edge_metadata.dst_year if edge_metadata else None)
            )
            abstract = (p.abstract if p else "") or (
                edge_metadata.dst_abstract if edge_metadata else ""
            )
            citation_count = (
                p.citation_count
                if p and p.citation_count is not None
                else (edge_metadata.dst_citation_count if edge_metadata else None)
            )
            nodes[ref] = {
                "paperRef": ref,
                "title": title,
                "authors": authors,
                "year": year,
                "abstract": abstract,
                "citationCount": citation_count,
                "ingested": False,
            }

        for e in edges:
            if e.dst_ref not in nodes:
                nodes[e.dst_ref] = {
                    "paperRef": e.dst_ref,
                    "title": e.dst_title,
                    "authors": e.dst_authors or [],
                    "year": e.dst_year,
                    "abstract": e.dst_abstract,
                    "citationCount": e.dst_citation_count,
                    "ingested": False,
                }
        return {
            "studyId": study_id,
            "nodes": sorted(nodes.values(), key=lambda n: not n["ingested"]),
            "edges": [
                {"src": e.src_ref, "dst": e.dst_ref, "kind": e.kind} for e in edges
            ],
        }

    @app.post(
        "/studies/{study_id}/papers/match",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def match_study_papers(
        study_id: str, body: MatchIn, s: Session = Depends(db)
    ) -> dict:
        recommendations = matching.match_papers(
            s,
            body.query,
            study_id=study_id,
            limit=body.limit,
            use_llm=False,
            expand=False,
        )
        return {"studyId": study_id, "recommendations": recommendations}

    def _adopt_corpus_paper(
        s: Session,
        study_id: str,
        ref: str,
        *,
        added_via: str,
        match_reason: str = "",
    ) -> str | None:
        corpus_row = s.execute(
            select(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref == ref
            )
        ).scalar_one_or_none()
        if corpus_row is None:
            return None
        vals = {
            "study_id": study_id,
            "paper_ref": corpus_row.paper_ref,
            "title": corpus_row.title,
            "authors": corpus_row.authors,
            "year": corpus_row.year,
            "venue": corpus_row.venue,
            "abstract": corpus_row.abstract,
            "doi": corpus_row.doi,
            "arxiv_id": corpus_row.arxiv_id,
            "url": corpus_row.url,
            "item_type": corpus_row.item_type,
            "source": added_via,
            "s2_id": corpus_row.s2_id,
            "citation_count": corpus_row.citation_count,
            "tier": corpus_row.tier,
            "added_via": added_via,
            "match_reason": match_reason,
            "added_at": now(),
        }
        update = {"added_via": added_via, "match_reason": match_reason}
        engine = get_engine()
        if engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as _pg_insert

            stmt = (
                _pg_insert(Paper)
                .values([vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=update
                )
            )
        else:
            from sqlalchemy.dialects.sqlite import insert as _sq_insert

            stmt = (
                _sq_insert(Paper)
                .values([vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=update
                )
            )
        s.execute(stmt)
        _seed_links(s, study_id, corpus_row.paper_ref)
        _adopt_corpus_edges(s, study_id, corpus_row.paper_ref)
        return corpus_row.paper_ref

    def _warmed_graph_record(s: Session, study_id: str, paper_ref: str) -> dict | None:
        edge = s.scalar(
            select(PaperEdge)
            .where(
                PaperEdge.study_id == study_id,
                PaperEdge.dst_ref == paper_ref,
                PaperEdge.dst_title != "",
            )
            .order_by(PaperEdge.id.desc())
        )
        if edge is None:
            return None
        record = {
            "paperRef": paper_ref,
            "title": edge.dst_title,
            "authors": edge.dst_authors or [],
            "year": edge.dst_year,
            "venue": "",
            "abstract": edge.dst_abstract or "",
            "doi": paper_ref.removeprefix("doi:"),
            "arxivId": paper_ref.removeprefix("arxiv:"),
            "url": "",
            "citationCount": edge.dst_citation_count,
            "itemType": "paper",
            "source": "graph",
        }
        if paper_ref.startswith("arxiv:"):
            record["url"] = f"https://arxiv.org/abs/{record['arxivId']}"
        elif paper_ref.startswith("doi:"):
            record["url"] = f"https://doi.org/{record['doi']}"
        elif paper_ref.startswith("s2:"):
            record["url"] = (
                f"https://www.semanticscholar.org/paper/{paper_ref.removeprefix('s2:')}"
            )
        return record

    @app.post(
        "/studies/{study_id}/papers/from-match",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def add_paper_from_match(
        study_id: str,
        body: FromMatchIn,
        background_tasks: BackgroundTasks,
        s: Session = Depends(db),
    ) -> dict:
        corpus_row = s.execute(
            select(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref == body.ref
            )
        ).scalar_one_or_none()
        if corpus_row is None:
            raise HTTPException(404, f"paper {body.ref!r} is not in the corpus")
        _match_vals = {
            "study_id": study_id,
            "paper_ref": corpus_row.paper_ref,
            "title": corpus_row.title,
            "authors": corpus_row.authors,
            "year": corpus_row.year,
            "venue": corpus_row.venue,
            "abstract": corpus_row.abstract,
            "doi": corpus_row.doi,
            "arxiv_id": corpus_row.arxiv_id,
            "url": corpus_row.url,
            "item_type": corpus_row.item_type,
            "source": "match",
            "s2_id": corpus_row.s2_id,
            "citation_count": corpus_row.citation_count,
            "tier": corpus_row.tier,
            "added_via": "match",
            "match_reason": body.matchReason,
            "added_at": now(),
        }
        _match_update = {"added_via": "match", "match_reason": body.matchReason}
        _engine = get_engine()
        if _engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as _pg_insert

            stmt = (
                _pg_insert(Paper)
                .values([_match_vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=_match_update
                )
            )
        else:
            from sqlalchemy.dialects.sqlite import insert as _sq_insert

            stmt = (
                _sq_insert(Paper)
                .values([_match_vals])
                .on_conflict_do_update(
                    index_elements=["study_id", "paper_ref"], set_=_match_update
                )
            )
        s.execute(stmt)
        _seed_links(s, study_id, corpus_row.paper_ref)
        adopted = _adopt_corpus_edges(s, study_id, corpus_row.paper_ref)
        s.commit()
        background_tasks.add_task(
            harvest_edges_in_background, study_id, corpus_row.paper_ref
        )
        return {
            "studyId": study_id,
            "paperRef": corpus_row.paper_ref,
            "title": corpus_row.title,
            "tier": corpus_row.tier,
            "addedVia": "match",
            "edges": adopted,
            "edgesPending": True,
        }

    @app.post(
        "/studies/{study_id}/papers/from-graph",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def add_paper_from_graph(
        study_id: str,
        body: FromGraphIn,
        background_tasks: BackgroundTasks,
        s: Session = Depends(db),
    ) -> dict:
        paper_ref = body.ref.strip()
        if not paper_ref:
            raise HTTPException(400, "paper ref is required")

        existing = s.scalar(
            select(Paper).where(
                Paper.study_id == study_id, Paper.paper_ref == paper_ref
            )
        )
        if existing is not None:
            return {
                "studyId": study_id,
                "paperRef": paper_ref,
                "title": existing.title,
                "edges": 0,
                "edgesPending": False,
            }

        adopted = _adopt_corpus_paper(
            s, study_id, paper_ref, added_via="graph", match_reason=""
        )
        if adopted is not None:
            has_edges = (
                s.scalar(
                    select(PaperEdge.id).where(
                        PaperEdge.study_id == study_id,
                        (PaperEdge.src_ref == paper_ref)
                        | (PaperEdge.dst_ref == paper_ref),
                    )
                )
                is not None
            )
            s.commit()
            if not has_edges:
                background_tasks.add_task(
                    harvest_edges_in_background, study_id, paper_ref
                )
            title = (
                s.scalar(
                    select(Paper.title).where(
                        Paper.study_id == study_id, Paper.paper_ref == paper_ref
                    )
                )
                or paper_ref
            )
            return {
                "studyId": study_id,
                "paperRef": paper_ref,
                "title": title,
                "edges": 0,
                "edgesPending": not has_edges,
            }

        record = _warmed_graph_record(s, study_id, paper_ref)
        edges_pending = record is None
        if record is None:
            try:
                record = semantic_scholar.fetch_paper(paper_ref, fetch=cached_fetch(s))
            except semantic_scholar.SemanticScholarError as exc:
                raise HTTPException(502, f"Semantic Scholar: {exc}") from exc

        upsert_paper(s, study_id, record, source="graph")
        adopted_edges = _adopt_corpus_edges(s, study_id, paper_ref)
        s.commit()
        if edges_pending:
            background_tasks.add_task(harvest_edges_in_background, study_id, paper_ref)
        return {
            "studyId": study_id,
            "paperRef": paper_ref,
            "title": record.get("title", paper_ref),
            "edges": adopted_edges,
            "edgesPending": edges_pending,
        }

    @app.get(
        "/studies/{study_id}/papers/{paper_ref:path}/links",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def get_paper_links(
        study_id: str, paper_ref: str, s: Session = Depends(db)
    ) -> dict:

        targets = sorted(
            s.scalars(
                select(PaperLink.target).where(
                    PaperLink.study_id == study_id, PaperLink.paper_ref == paper_ref
                )
            )
        )
        return {"paperRef": paper_ref, "links": targets}

    @app.put(
        "/studies/{study_id}/papers/{paper_ref:path}/links",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def set_paper_links(
        study_id: str, paper_ref: str, body: PaperLinksIn, s: Session = Depends(db)
    ) -> dict:

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

    @app.get("/schemas/event")
    def event_schema() -> dict:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://masters-project.local/schemas/event.schema.json",
            "title": "Study Event",
            "description": "Machine-readable schema for study events.",
            "type": "object",
            "required": [
                "v",
                "ts",
                "mono",
                "sessionId",
                "participantId",
                "condition",
                "seq",
                "type",
                "payload",
            ],
            "additionalProperties": False,
            "properties": {
                "v": {
                    "description": (
                        "Event schema version. Versions 2-4 cover live capture; "
                        "version 5 covers the isolated archive vocabulary."
                    ),
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 5,
                },
                "ts": {
                    "description": "ISO-8601 wall-clock timestamp with ms precision.",
                    "type": "string",
                    "format": "date-time",
                },
                "mono": {
                    "description": (
                        "Monotonic milliseconds since session start. "
                        "Immune to NTP jumps and manual clock changes."
                    ),
                    "type": "number",
                    "minimum": 0,
                },
                "sessionId": {
                    "description": "Unique session identifier.",
                    "type": "string",
                    "minLength": 1,
                },
                "participantId": {
                    "description": "Participant identifier.",
                    "type": "string",
                    "minLength": 1,
                },
                "condition": {
                    "description": "Study condition.",
                    "type": "string",
                    "enum": ["ai-assisted", "unassisted", "unspecified"],
                },
                "seq": {
                    "description": (
                        "Monotonic per-session sequence number, for ordering "
                        "and gap detection."
                    ),
                    "type": "integer",
                    "minimum": 0,
                },
                "type": {
                    "description": (
                        "Event type, e.g., 'session_start', 'fatigue_response', "
                        "'stuck_response'."
                    ),
                    "type": "string",
                    "minLength": 1,
                },
                "payload": {
                    "description": "Event-specific payload data.",
                    "type": "object",
                    "additionalProperties": True,
                },
                "source": {
                    "description": (
                        "Producer stream; falls back to DEFAULT_SOURCE "
                        "('tern') if not provided."
                    ),
                    "type": "string",
                    "default": "tern",
                },
            },
        }

    @app.get("/schemas/protocol")
    def protocol_schema() -> dict:
        protocol_schema_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "protocol"
            / "src"
            / "protocol"
            / "schema"
            / "study-protocol.schema.json"
        )
        if protocol_schema_path.exists():
            import json

            return json.loads(protocol_schema_path.read_text())
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Study Protocol",
            "description": "Machine-readable requirements specification of a study.",
            "type": "object",
            "required": [
                "protocolVersion",
                "study",
                "researchQuestions",
                "conditions",
                "participants",
                "session",
                "instruments",
                "phases",
                "analysisPlan",
            ],
            "properties": {"protocolVersion": {"type": "integer", "const": 1}},
        }

    @app.get("/schemas/template")
    def template_schema() -> dict:
        template_schema_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "templates"
            / "schemas"
            / "template.schema.json"
        )
        if template_schema_path.exists():
            import json

            return json.loads(template_schema_path.read_text())
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Study Template",
            "description": "Machine-readable template for a published study design.",
            "type": "object",
            "required": [
                "templateVersion",
                "templateId",
                "title",
                "source",
                "designType",
                "dataPath",
                "parameters",
                "measures",
                "statisticalPlan",
                "protocolSkeleton",
            ],
            "properties": {"templateVersion": {"type": "integer", "minimum": 1}},
        }

    @app.get("/templates")
    def template_index() -> dict:
        repo = Path(__file__).resolve().parent.parent.parent.parent
        templates_dir = repo / "templates" / "registry"

        templates = []
        if templates_dir.exists():
            import yaml

            for template_file in sorted(templates_dir.glob("*.yaml")):
                try:
                    with open(template_file) as f:
                        template_data = yaml.safe_load(f)
                    templates.append(
                        {
                            "id": template_data.get("templateId", ""),
                            "version": template_data.get("templateVersion", 1),
                            "title": template_data.get("title", ""),
                            "description": template_data.get("description", ""),
                            "designType": template_data.get("designType", ""),
                            "dataPath": template_data.get("dataPath", ""),
                            "source": template_data.get("source", []),
                        }
                    )
                except Exception:  # noqa: BLE001,S112 - skip unparseable template files
                    continue

        return {"templates": templates, "count": len(templates), "generatedAt": now()}

    @app.get("/conversation/profiles")
    def researcher_profiles() -> dict:
        return {
            "profiles": elicitation.profile_catalog(),
            "default": elicitation.DEFAULT_PROFILE,
        }

    @app.get("/papers/index")
    def corpus_index() -> dict:
        repo = Path(__file__).resolve().parent.parent.parent.parent
        corpus_index_path = repo / "docs" / "papers" / "corpus-index.json"

        if corpus_index_path.exists():
            import json

            return json.loads(corpus_index_path.read_text())

        return {
            "generatedAt": "",
            "pipeline": "",
            "tierA": {"count": 0, "arxivResolvable": 0, "source": ""},
            "tierB": [],
            "scoringVersion": 0,
        }

    @app.post("/projects", dependencies=[Depends(resolve_identity)])
    def create_project(
        body: dict,
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        name = str(body.get("name", "")).strip()
        if not name:
            raise HTTPException(400, "name is required")

        if name == "Personal":
            existing = s.scalar(
                select(Project)
                .join(Membership)
                .where(
                    (Project.name == "Personal")
                    & (Membership.identity_sub == identity.sub)
                    & (Membership.role == "owner")
                )
            )
            if existing:
                study_count = (
                    s.scalar(
                        select(func.count())
                        .select_from(Study)
                        .where(Study.project_id == existing.id)
                    )
                    or 0
                )
                return {
                    "id": existing.id,
                    "slug": existing.slug,
                    "name": existing.name,
                    "role": "owner",
                    "createdAt": existing.created_at,
                    "studyCount": study_count,
                }

        chosen = str(body.get("slug", "")).strip()
        slug = chosen
        if not slug:
            slug = _slug_from_text(name, 50)
        if not slug:
            slug = secrets.token_hex(4)
        if chosen:
            if s.scalar(select(Project).where(Project.slug == chosen)) is not None:
                raise HTTPException(409, f"slug {chosen!r} is taken")
        else:
            base, suffix = slug, 1
            while s.scalar(select(Project).where(Project.slug == slug)) is not None:
                suffix += 1
                slug = f"{base}-{suffix}"
        pid = secrets.token_hex(8)
        created = now()
        s.add(
            Project(
                id=pid,
                name=name,
                slug=slug,
                created_by=identity.sub,
                created_at=created,
            )
        )
        s.flush()
        s.add(
            Membership(
                project_id=pid,
                identity_sub=identity.sub,
                role="owner",
                invited_by="",
                joined_at=now(),
            )
        )
        s.flush()
        return {
            "id": pid,
            "slug": slug,
            "name": name,
            "role": "owner",
            "createdAt": created,
            "studyCount": 0,
        }

    @app.get("/projects", dependencies=[Depends(resolve_identity)])
    def list_projects(
        identity: auth.Identity = Depends(resolve_identity), s: Session = Depends(db)
    ) -> list[dict]:
        rows = s.execute(
            select(Project, Membership.role)
            .join(Membership, Membership.project_id == Project.id)
            .where(Membership.identity_sub == identity.sub)
            .order_by(Project.created_at.desc())
        ).all()
        if all(p.id != demo_mod.DEMO_PROJECT_ID for p, _ in rows):
            demo = s.get(Project, demo_mod.DEMO_PROJECT_ID)
            if demo is not None:
                rows = [*rows, (demo, authz.Role.VIEWER.value)]
        counts: dict[str, int] = {}
        if rows:
            for project_id, count in s.execute(
                select(Study.project_id, func.count())
                .where(Study.project_id.in_([proj.id for proj, _ in rows]))
                .group_by(Study.project_id)
            ):
                counts[project_id] = count
        return [
            {
                "id": p.id,
                "slug": p.slug,
                "name": p.name,
                "role": role,
                "createdAt": p.created_at,
                "studyCount": counts.get(p.id, 0),
            }
            for p, role in rows
        ]

    @app.get("/projects/{slug}", dependencies=[Depends(require_project("view"))])
    def project_home(slug: str, s: Session = Depends(db)) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        studies = [
            {"id": st.id}
            for st in s.scalars(select(Study).where(Study.project_id == proj.id))
        ]
        member_rows = list(
            s.scalars(select(Membership).where(Membership.project_id == proj.id))
        )
        members = [
            {
                "identitySub": m.identity_sub,
                "role": m.role,
            }
            for m in member_rows
        ]
        invitations = [
            {
                "id": inv.id,
                "role": inv.role,
                "createdAt": inv.created_at,
                "expiresAt": inv.expires_at,
            }
            for inv in s.scalars(
                select(Invitation).where(Invitation.project_id == proj.id)
            )
        ]
        return {
            "id": proj.id,
            "slug": proj.slug,
            "name": proj.name,
            "studies": studies,
            "members": members,
            "invitations": invitations,
        }

    @app.post(
        "/projects/{slug}/studies",
        dependencies=[Depends(require_project("contribute"))],
    )
    def create_study(slug: str, body: dict, s: Session = Depends(db)) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        name = str(body.get("name", "")).strip()
        base = _slug_from_text(name, 40) if name else ""
        if not base:
            base = "study"
        study_id = base
        suffix = 1
        while s.scalar(select(Study).where(Study.id == study_id)) is not None:
            suffix += 1
            study_id = f"{base}-{suffix}"
        seed = body.get("protocol")
        if seed is not None and (
            not isinstance(seed, dict)
            or not isinstance(seed.get("study"), dict)
            or not isinstance(seed.get("researchQuestions"), list)
        ):
            raise HTTPException(
                422,
                "protocol must be a compiled protocol: an object with "
                "study and researchQuestions",
            )
        s.add(
            Study(
                id=study_id,
                project_id=proj.id,
                protocol_version="",
                data_path="",
            )
        )
        if seed is not None:
            seed = copy.deepcopy(seed)
            seed.setdefault("study", {})["id"] = study_id
            seed["study"]["title"] = name
            s.add(
                ProtocolDraftRow(
                    study_id=study_id,
                    yaml=yaml.safe_dump(
                        seed, sort_keys=False, default_flow_style=False
                    ),
                    compilation_id="",
                    updated_at=now(),
                )
            )
        s.flush()
        return {"id": study_id}

    _STUDY_SCOPED = (
        StoredFile,
        Paper,
        PaperEdge,
        PaperLink,
        RecipeRun,
        EnrollmentToken,
        DesignMoveRow,
        ConversationTurn,
        ApprovalEvent,
        Compilation,
        ProtocolDraftRow,
        SessionOpen,
    )

    def _delete_study_scoped_rows(s: Session, study_id: str) -> None:
        for model in _STUDY_SCOPED:
            s.execute(model.__table__.delete().where(model.study_id == study_id))

    @app.delete(
        "/studies/{study_id}",
        dependencies=[Depends(require_project_for_study("delete"))],
    )
    def delete_study(study_id: str, s: Session = Depends(db)) -> dict:
        study = s.get(Study, study_id)
        if study is None:
            raise HTTPException(404, "study not found")
        _delete_study_scoped_rows(s, study_id)
        s.delete(study)
        s.flush()
        return {"deleted": study_id}

    @app.patch(
        "/projects/{slug}", dependencies=[Depends(require_project("manage_members"))]
    )
    def rename_project(slug: str, body: dict, s: Session = Depends(db)) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        name = str(body.get("name", "")).strip()
        if not name:
            raise HTTPException(400, "name is required")
        proj.name = name
        s.flush()
        return {"id": proj.id, "slug": proj.slug, "name": proj.name}

    @app.delete("/projects/{slug}", dependencies=[Depends(require_project("delete"))])
    def delete_project(slug: str, body: dict, s: Session = Depends(db)) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        confirm = str(body.get("confirm", "")).strip()
        if confirm != "DELETE":
            raise HTTPException(400, "type DELETE to confirm deletion")
        study_ids = list(s.scalars(select(Study.id).where(Study.project_id == proj.id)))
        for study_id in study_ids:
            _delete_study_scoped_rows(s, study_id)
        s.execute(Study.__table__.delete().where(Study.project_id == proj.id))
        s.execute(Membership.__table__.delete().where(Membership.project_id == proj.id))
        s.execute(Invitation.__table__.delete().where(Invitation.project_id == proj.id))
        s.delete(proj)
        s.flush()
        return {"deleted": proj.slug}

    @app.get(
        "/projects/{slug}/members", dependencies=[Depends(require_project("view"))]
    )
    def list_members(slug: str, s: Session = Depends(db)) -> list[dict]:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        return [
            {
                "identitySub": m.identity_sub,
                "role": m.role,
                "invitedBy": m.invited_by,
                "joinedAt": m.joined_at,
            }
            for m in s.scalars(
                select(Membership).where(Membership.project_id == proj.id)
            )
        ]

    @app.patch(
        "/projects/{slug}/members/{identity_sub}",
        dependencies=[Depends(require_project("manage_members"))],
    )
    def change_role(
        slug: str, identity_sub: str, body: dict, s: Session = Depends(db)
    ) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        m = s.scalar(
            select(Membership).where(
                Membership.project_id == proj.id,
                Membership.identity_sub == identity_sub,
            )
        )
        if m is None:
            raise HTTPException(404, "member not found")
        new_role = str(body.get("role", "")).strip()
        if new_role not in authz.ROLES:
            raise HTTPException(400, f"role must be one of: {list(authz.ROLES)}")
        m.role = new_role
        s.flush()
        return {"identitySub": m.identity_sub, "role": m.role}

    @app.delete(
        "/projects/{slug}/members/{identity_sub}",
        dependencies=[Depends(require_project("manage_members"))],
    )
    def remove_member(slug: str, identity_sub: str, s: Session = Depends(db)) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        m = s.scalar(
            select(Membership).where(
                Membership.project_id == proj.id,
                Membership.identity_sub == identity_sub,
            )
        )
        if m is None:
            raise HTTPException(404, "member not found")
        if m.role == "owner":
            owner_count = s.scalar(
                select(func.count())
                .select_from(Membership)
                .where(Membership.project_id == proj.id, Membership.role == "owner")
            )
            if owner_count <= 1:
                raise HTTPException(
                    409, "can't remove the last owner. Transfer ownership first"
                )
        s.delete(m)
        s.flush()
        return {"removed": identity_sub}

    @app.post(
        "/projects/{slug}/invitations",
        dependencies=[Depends(require_project("invite_member"))],
    )
    def create_invitation(
        slug: str,
        body: dict,
        s: Session = Depends(db),
        identity: auth.Identity = Depends(resolve_identity),
    ) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        role = str(body.get("role", "")).strip()
        if role not in authz.ROLES:
            raise HTTPException(400, f"role must be one of: {list(authz.ROLES)}")
        if role == authz.Role.OWNER.value:
            caller = s.scalar(
                select(Membership).where(
                    Membership.project_id == proj.id,
                    Membership.identity_sub == identity.sub,
                )
            )
            if caller is None or not authz.has_role(caller.role, "manage_members"):
                raise HTTPException(403, "only an owner can invite another owner")
        from datetime import timedelta as td

        now = clock()
        expires = now + td(days=7)
        token = secrets.token_urlsafe(32)
        inv_id = secrets.token_hex(8)
        s.add(
            Invitation(
                id=inv_id,
                project_id=proj.id,
                role=role,
                token=token,
                created_at=now.isoformat(timespec="milliseconds"),
                expires_at=expires.isoformat(timespec="milliseconds"),
            )
        )
        s.flush()
        url = f"/invitations/{token}"
        return {
            "id": inv_id,
            "token": token,
            "url": url,
            "role": role,
            "createdAt": now.isoformat(timespec="milliseconds"),
            "expiresAt": expires.isoformat(timespec="milliseconds"),
        }

    @app.delete(
        "/projects/{slug}/invitations/{inv_id}",
        dependencies=[Depends(require_project("manage_members"))],
    )
    def revoke_invitation(slug: str, inv_id: str, s: Session = Depends(db)) -> dict:
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        inv = s.scalar(
            select(Invitation).where(
                Invitation.project_id == proj.id,
                Invitation.id == inv_id,
            )
        )
        if inv is None:
            raise HTTPException(404, "invitation not found")
        s.delete(inv)
        s.flush()
        return {"revoked": inv_id}

    @app.post("/invitations/{token}/accept", dependencies=[Depends(resolve_identity)])
    def accept_invitation(
        token: str,
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        sub = identity.sub
        inv = s.scalar(select(Invitation).where(Invitation.token == token))
        if inv is None:
            raise HTTPException(
                404,
                "invitation not found. It may have expired or been revoked",
            )
        if inv.expires_at:
            try:
                exp = datetime.fromisoformat(inv.expires_at)
                if clock() > exp:
                    raise HTTPException(
                        410,
                        "this invitation has expired. Ask the project owner "
                        "to send a new one",
                    )
            except (ValueError, TypeError):
                pass
        inv.accepted_at = now()
        existing = s.scalar(
            select(Membership).where(
                Membership.project_id == inv.project_id, Membership.identity_sub == sub
            )
        )
        if existing is None:
            s.add(
                Membership(
                    project_id=inv.project_id,
                    identity_sub=sub,
                    role=inv.role,
                    invited_by=inv.id,
                    joined_at=now(),
                )
            )
        proj = s.scalar(select(Project).where(Project.id == inv.project_id))
        s.flush()
        return {
            "projectSlug": proj.slug if proj else "",
            "role": existing.role if existing else inv.role,
        }

    @app.post(
        "/studies/{study_id}/enrollment/tokens",
        dependencies=[Depends(require_project_for_study("mint_token"))],
    )
    def mint_enrollment_tokens(
        study_id: str,
        body: MintTokensIn,
        request: Request,
        s: Session = Depends(db),
    ) -> list[dict]:
        from datetime import timedelta as td

        protocol = _resolve_study_protocol(s, study_id)
        if protocol is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")
        if body.grain not in {"participant", "session"}:
            raise HTTPException(400, "grain must be 'participant' or 'session'")
        conditions = protocol["conditions"]
        existing = s.scalars(
            select(EnrollmentToken).where(EnrollmentToken.study_id == study_id)
        ).all()
        start = len(existing)
        base = str(request.base_url).rstrip("/")
        expires = (clock() + td(days=30)).isoformat(timespec="milliseconds")
        out = []
        for i in range(body.count):
            n = start + i + 1
            pid = f"P{n:02d}"
            index = n - 1
            blocks = assign(protocol, index)
            condition = blocks[0].condition if blocks else conditions[0]
            token = secrets.token_urlsafe(32)
            row = EnrollmentToken(
                id=secrets.token_hex(8),
                study_id=study_id,
                participant_id=pid,
                participant_index=index,
                condition=condition,
                grain=body.grain,
                capture_overrides=enrollment.clean_capture_overrides(body.overrides),
                token=token,
                expires_at=expires,
                created_at=now(),
            )
            s.add(row)
            out.append(
                {
                    "id": row.id,
                    "participantId": pid,
                    "condition": condition,
                    "grain": body.grain,
                    "connectionString": enrollment.connection_string(base, token),
                    "status": "unredeemed",
                }
            )
        s.commit()
        return out

    @app.get(
        "/studies/{study_id}/enrollment/tokens",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def list_enrollment_tokens(
        study_id: str,
        request: Request,
        windowSeconds: int = 300,
        s: Session = Depends(db),
    ) -> list[dict]:
        from protocol.errors import ProtocolError

        rows = s.scalars(
            select(EnrollmentToken)
            .where(
                EnrollmentToken.study_id == study_id,
                EnrollmentToken.revoked_at.is_(None),
            )
            .order_by(EnrollmentToken.participant_id)
        ).all()

        cutoff = (clock() - timedelta(seconds=windowSeconds)).astimezone(UTC)
        cutoff_s = cutoff.isoformat(timespec="milliseconds")
        streaming_participants = set(
            s.scalars(
                select(Event.participant_id)
                .where(
                    Event.received_at >= cutoff_s,
                    _session_scope(study_id)(Event.session_id),
                )
                .distinct()
            ).all()
        )

        protocol = _resolve_study_protocol(s, study_id)
        base = str(request.base_url).rstrip("/")
        out = []
        for r in rows:
            if r.redeemed_at and r.participant_id in streaming_participants:
                status = "streaming"
            elif r.redeemed_at:
                status = "paired"
            else:
                status = "unredeemed"
            capture_config = None
            if protocol is not None:
                try:
                    cfg = enrollment.build_capture_config(
                        protocol,
                        r.participant_id,
                        r.condition,
                        study_id=study_id,
                        overrides=r.capture_overrides,
                    )
                    capture_config = {
                        "captureConfigVersion": cfg["captureConfigVersion"],
                        "enabledInstruments": enrollment.enabled_instruments(
                            cfg["settings"]
                        ),
                        "producerStates": {
                            key: value.get("state")
                            for key, value in (cfg.get("sessionManifest") or {})
                            .get("producers", {})
                            .items()
                            if isinstance(value, dict)
                        },
                        "privacyPolicy": (cfg.get("sessionManifest") or {}).get(
                            "privacyPolicy", {}
                        ),
                    }
                except ProtocolError:
                    pass
            out.append(
                {
                    "id": r.id,
                    "participantId": r.participant_id,
                    "condition": r.condition,
                    "grain": r.grain,
                    "status": status,
                    "connectionString": enrollment.connection_string(base, r.token),
                    "captureConfig": capture_config,
                    "captureOverrides": r.capture_overrides,
                }
            )
        return out

    @app.delete(
        "/studies/{study_id}/enrollment/tokens/{token_id}",
        dependencies=[Depends(require_project_for_study("mint_token"))],
    )
    def revoke_enrollment_token(
        study_id: str, token_id: str, s: Session = Depends(db)
    ) -> dict:

        row = s.get(EnrollmentToken, token_id)
        if row is None or row.study_id != study_id:
            raise HTTPException(404, "enrollment token not found")
        row.revoked_at = now()
        s.commit()
        return {"revoked": token_id}

    @app.get(
        "/studies/{study_id}/enrollment/toggles/catalog",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def toggles_catalog(study_id: str, s: Session = Depends(db)) -> list[dict]:
        protocol = _resolve_study_protocol(s, study_id)
        if protocol is None:
            raise HTTPException(404, "study not found")
        return enrollment.toggle_catalog(protocol)

    @app.post(
        "/studies/{study_id}/enrollment/toggles",
        dependencies=[Depends(require_project_for_study("toggle_capture"))],
    )
    def apply_toggle(study_id: str, body: ToggleIn, s: Session = Depends(db)) -> dict:
        before = _resolve_study_protocol(s, study_id)
        if not before:
            raise HTTPException(404, "study not found")
        if not before.get("instruments"):
            raise HTTPException(400, "protocol has no instruments block")

        toggle_move = {
            "moveId": f"toggle-{secrets.token_hex(4)}",
            "kind": "reconfigure-instrument",
            "target": f"instruments.{body.instrument}",
            "patch": {
                "section": "instruments",
                "name": body.instrument,
                "op": "reconfigure",
                "path": list(body.path),
                "value": body.value,
            },
            "status": "accepted",
        }

        draft = yaml.safe_load(yaml.safe_dump(before))
        compiler._apply_instrument_moves(draft, [toggle_move])

        from protocol.loader import validate_protocol

        errors = validate_protocol(draft)
        if errors:
            raise HTTPException(
                422, f"toggle would produce an invalid protocol: {'; '.join(errors)}"
            )

        new_yaml = yaml.safe_dump(draft, default_flow_style=False)
        row = s.get(ProtocolDraftRow, study_id)
        if row is None:
            row = ProtocolDraftRow(study_id=study_id)
            s.add(row)
        row.yaml = new_yaml
        row.updated_at = now()
        s.commit()
        return {"applied": True}

    @app.post("/pair/redeem")
    def pair_redeem(body: RedeemIn, request: Request, s: Session = Depends(db)) -> dict:

        row = s.scalar(
            select(EnrollmentToken).where(EnrollmentToken.token == body.token)
        )
        if row is None or row.revoked_at:
            raise HTTPException(
                410, "this connection link is invalid or has been revoked"
            )
        try:
            if datetime.fromisoformat(row.expires_at) < clock():
                raise HTTPException(
                    410, "this connection link has expired. Ask for a new one"
                )
        except (ValueError, TypeError):
            pass
        if row.grain == "session" and row.redeemed_at:
            raise HTTPException(
                410, "this single-use connection link has already been used"
            )
        protocol = _resolve_study_protocol(s, row.study_id)
        if protocol is None:
            raise HTTPException(404, "no protocol for this study")
        task, block = _block_for_session(s, protocol, row, None)
        if not row.credential:
            row.credential = secrets.token_urlsafe(32)
        if row.grain == "session" or not row.redeemed_at:
            row.redeemed_at = now()
        s.commit()
        base = str(request.base_url).rstrip("/")
        return {
            "studyId": row.study_id,
            "participantId": row.participant_id,
            "condition": row.condition,
            "sessionCredential": row.credential,
            "ingestEndpoint": f"{base}/ingest/events",
            "captureConfig": enrollment.build_capture_config(
                protocol,
                row.participant_id,
                row.condition,
                study_id=row.study_id,
                task=task,
                block=block,
                overrides=row.capture_overrides,
                endpoints={
                    "events": f"{base}/ingest/events",
                    "metrics": f"{base}/ingest/metrics",
                },
            ),
            "consentStatement": enrollment.consent_statement(protocol, row.condition),
            "contentPolicy": enrollment.content_policy(protocol),
        }

    def resolve_credential(s: Session, authorization: str):

        if not authorization.startswith("Bearer "):
            return None
        cred = authorization.removeprefix("Bearer ").strip()
        if not cred:
            return None
        try:
            row = s.scalar(
                select(EnrollmentToken).where(EnrollmentToken.credential == cred)
            )
            if row is None or row.revoked_at:
                return None
            try:
                if datetime.fromisoformat(row.expires_at) < clock():
                    return None
            except (ValueError, TypeError):
                pass
            return row
        except Exception:  # noqa: BLE001 - never 500 an ingest batch (NFR-1)
            return None

    def _task_by_id(protocol: dict, task_id: str) -> dict | None:
        from protocol.assignment import tasks_of

        return next((t for t in tasks_of(protocol) if t.get("id") == task_id), None)

    def _block_for_session(
        s: Session, protocol: dict, row, session_id: str | None
    ) -> tuple[dict | None, dict | None]:
        from protocol.assignment import assign

        blocks = assign(protocol, row.participant_index or 0)
        if not blocks:
            return None, None

        recorded = s.get(SessionBlock, session_id) if session_id else None
        if recorded is None:
            done = (
                s.scalar(
                    select(func.count())
                    .select_from(SessionBlock)
                    .where(
                        SessionBlock.study_id == row.study_id,
                        SessionBlock.participant_id == row.participant_id,
                    )
                )
                or 0
            )
            block = blocks[min(done, len(blocks) - 1)]
            if session_id:
                s.add(
                    SessionBlock(
                        session_id=session_id,
                        study_id=row.study_id,
                        participant_id=row.participant_id,
                        block_index=block.index,
                        task_id=block.task_id,
                        condition=block.condition,
                        assigned_at=now(),
                    )
                )
                row.condition = block.condition
                s.commit()
        else:
            block = next(
                (b for b in blocks if b.index == recorded.block_index),
                blocks[0],
            )

        task = _task_by_id(protocol, block.task_id)
        return task, {
            "index": block.index,
            "of": len(blocks),
            "taskId": block.task_id,
            "condition": block.condition,
            "title": (task or {}).get("title", ""),
            "description": (task or {}).get("description", ""),
            "materials": (task or {}).get("materials", ""),
        }

    @app.get("/studies/{study_id}/capture-config")
    def get_capture_config(
        study_id: str,
        request: Request,
        sessionId: str | None = None,
        authorization: str = Header(default=""),
        s: Session = Depends(db),
    ) -> dict:
        row = resolve_credential(s, authorization)
        if row is None or row.study_id != study_id:
            raise HTTPException(401, "a valid session credential is required")
        protocol = _resolve_study_protocol(s, study_id)
        if protocol is None:
            raise HTTPException(404, "no protocol for this study")
        task, block = _block_for_session(s, protocol, row, sessionId)
        base = str(request.base_url).rstrip("/")
        return enrollment.build_capture_config(
            protocol,
            row.participant_id,
            (block or {}).get("condition") or row.condition,
            study_id=study_id,
            task=task,
            block=block,
            overrides=row.capture_overrides,
            session_id=sessionId,
            endpoints={
                "events": f"{base}/ingest/events",
                "metrics": f"{base}/ingest/metrics",
            },
        )

    @app.get(
        "/studies/{study_id}/power",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def study_power_curve(
        study_id: str,
        alpha: float = 0.05,
        maxN: int = 120,
        powerTarget: float = 0.8,
        effectSizes: str = "0.2,0.5,0.8",
        s: Session = Depends(db),
    ) -> dict:
        from analysis.power import paired_power_curve, two_sample_power_curve

        try:
            sizes = [float(x.strip()) for x in effectSizes.split(",")]
        except ValueError as exc:
            raise HTTPException(
                422, "effectSizes must be a comma-separated list of numbers"
            ) from exc
        try:
            protocol = _resolve_study_protocol(s, study_id)
            participants = (protocol or {}).get("participants", {})
            design = (
                participants.get("design", "") if isinstance(participants, dict) else ""
            )
            calculator = (
                paired_power_curve
                if str(design).lower() in {"within-subjects", "paired"}
                else two_sample_power_curve
            )
            result = calculator(
                sizes,
                alpha=alpha,
                power_target=powerTarget,
                max_total_n=maxN,
            )
            if isinstance(participants, dict):
                result["plannedParticipants"] = participants.get("planned")
                result["design"] = design or None
            if not design:
                result["note"] = (
                    "No planned comparison yet. Describe the conditions and study "
                    "design in Conversation before using recruitment planning."
                )
            return result
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def _profile_prefs(s: Session, sub: str) -> dict:
        row = s.get(UserProfile, sub)
        return dict(row.prefs) if row is not None else {}

    @app.get("/me", dependencies=[Depends(resolve_identity)])
    def get_me(identity: auth.Identity = Depends(resolve_identity)) -> dict:
        sub = identity.sub
        mode = identity.mode
        display = identity.display_name
        s = session_factory()
        try:
            rows = s.execute(
                select(Project, Membership.role)
                .join(Membership, Membership.project_id == Project.id)
                .where(Membership.identity_sub == sub)
            ).all()
            return {
                "sub": sub,
                "displayName": display,
                "mode": mode,
                "memberships": [
                    {"projectSlug": p.slug, "projectName": p.name, "role": r}
                    for p, r in rows
                ],
                "preferences": _profile_prefs(s, sub),
            }
        finally:
            s.close()

    KNOWN_PREF_KEYS = frozenset({"theme", "savedViews"})

    @app.put(
        "/me/preferences",
        dependencies=[Depends(resolve_identity)],
    )
    def put_preferences(
        body: dict,
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        sub = identity.sub
        incoming = body.get("preferences", body)
        if not isinstance(incoming, dict):
            raise HTTPException(400, "preferences must be an object")
        clean = {k: v for k, v in incoming.items() if k in KNOWN_PREF_KEYS}
        row = s.get(UserProfile, sub)
        if row is None:
            row = UserProfile(
                identity_sub=sub,
                prefs=clean,
                updated_at=now(),
            )
            s.add(row)
        else:
            merged = dict(row.prefs)
            merged.update(clean)
            row.prefs = merged
            row.updated_at = now()
        s.flush()
        return {"sub": sub, "preferences": dict(row.prefs)}

    @app.post("/templates/{template_id}/instantiate")
    def instantiate_template(template_id: str, body: TemplateInstantiateIn) -> dict:
        params = dict(body.parameters)
        if body.studyId:
            params.setdefault("studyId", body.studyId)
        if body.title:
            params.setdefault("title", body.title)
        try:
            out = template_registry.instantiate_template(template_id, params)
        except template_registry.TemplateError as exc:
            raise HTTPException(422, str(exc)) from exc
        out["yaml"] = yaml.safe_dump(
            out["protocol"], sort_keys=False, default_flow_style=False
        )
        return out

    @app.get("/templates/{template_id}/plan")
    def template_plan(template_id: str) -> dict:
        try:
            tpl = template_registry.load_template(template_id)
        except template_registry.TemplateError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {
            "templateId": template_id,
            "explanation": template_registry.explain_plan(tpl),
        }

    @app.get("/templates/repertoire")
    def template_repertoire_route(
        limitRefs: int = 6,
        s: Session = Depends(db),
    ) -> dict:
        corpus = corpus_importer.corpus_status_for_session(s)
        entries = (
            template_repertoire.rank_repertoire(
                s, limit_refs=max(1, min(limitRefs, 20))
            )
            if corpus["state"] == "ready"
            else []
        )
        return {
            "repertoire": entries,
            "count": len(entries),
            "minReferenceConfidence": template_repertoire.MIN_REFERENCE_CONFIDENCE,
            "corpus": corpus,
            "generatedAt": now(),
        }

    @app.post("/templates/merge")
    def merge_templates_route(body: dict) -> dict:
        ids = body.get("templateIds") or []
        params = body.get("parameters") or {}
        if not isinstance(ids, list) or len(ids) < 2:
            raise HTTPException(400, "templateIds must be a list of at least two ids")
        try:
            return template_registry.merge_templates(ids, params)
        except template_registry.TemplateError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/corpus/search")
    def corpus_search(q: str = "", limit: int = 8, s: Session = Depends(db)) -> dict:
        query = q.strip()
        if not query:
            return {"results": []}
        results = matching.match_papers(
            s,
            query,
            study_id=None,
            limit=max(1, min(limit, 25)),
            use_llm=False,
            expand=False,
        )
        return {"results": results}

    @app.get("/corpus/status")
    def corpus_status(s: Session = Depends(db)) -> dict:
        return {
            **corpus_importer.corpus_status_for_session(s),
            **corpus_enrich.enrichment_status_for_session(s),
        }

    @app.post("/templates/from-paper")
    def template_from_paper(body: dict, s: Session = Depends(db)) -> dict:
        ref = str(body.get("paperRef", "")).strip()
        base = str(body.get("baseTemplateId", "")).strip()
        if not ref or not base:
            raise HTTPException(400, "paperRef and baseTemplateId are required")
        meta = matching.get_paper_metadata(s, ref)
        if meta is None:
            raise HTTPException(404, f"paper {ref!r} is not in the corpus")
        try:
            template = template_registry.derive_template_from_paper(
                ref, base, title=meta.get("title", ""), year=meta.get("year")
            )
        except template_registry.TemplateError as exc:
            raise HTTPException(400, str(exc)) from exc
        try:
            filled = template_registry.instantiate_doc(template, {})
        except template_registry.TemplateError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {
            "template": template,
            "paper": meta,
            "protocol": filled["protocol"],
        }

    @app.get("/analysis/prescriptions")
    def analysis_prescriptions(
        study_id: str | None = None, s: Session = Depends(db)
    ) -> dict:
        from analysis.prescribe import design_shapes, shapes_from_recipe_ids

        if study_id is None:
            rows = [
                design_assistant.recommend_prescription(shape)
                for shape in design_shapes()
            ]
            return {"prescriptions": [r for r in rows if r is not None]}

        protocol = _resolve_study_protocol(s, study_id)
        recipe_ids: set[str] = set()
        for entry in (protocol or {}).get("analysisPlan") or []:
            recipe_ids.update(entry.get("recipes") or [])
        matched_shapes = shapes_from_recipe_ids(recipe_ids)
        participants = (protocol or {}).get("participants", {})
        participant_design = (
            participants.get("design", "") if isinstance(participants, dict) else ""
        )
        if str(participant_design).lower() in {"within-subjects", "paired"}:
            matched_shapes.add("paired")
        rows = [
            design_assistant.recommend_prescription(shape)
            for shape in design_shapes()
            if shape in matched_shapes
        ]
        return {"prescriptions": [r for r in rows if r is not None]}

    def _conversation_seq(s: Session, study_id: str) -> int:
        last = s.scalar(
            select(func.max(ConversationTurn.seq)).where(
                ConversationTurn.study_id == study_id
            )
        )
        return (last or 0) + 1

    def _validate_decision_followup(
        s: Session, study_id: str, decision: DecisionTriggerIn | None
    ) -> None:
        if decision is None:
            return
        move = s.get(DesignMoveRow, decision.moveId)
        expected = "rejected" if decision.action == "rejected" else "accepted"
        if move is None or move.study_id != study_id or move.status != expected:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This card decision is no longer current. "
                    "Refresh the conversation and try again."
                ),
            )
        if decision.action == "noted" and move.kind != "caution":
            raise HTTPException(
                status_code=409,
                detail="Only a caution card can be noted.",
            )

    def _turn_for_request(
        s: Session, study_id: str, request_id: str | None
    ) -> ConversationTurn | None:
        if not request_id:
            return None
        return s.scalar(
            select(ConversationTurn).where(
                ConversationTurn.study_id == study_id,
                ConversationTurn.request_id == request_id,
            )
        )

    def _stored_turn_payload(
        s: Session, study_id: str, researcher: ConversationTurn
    ) -> dict | None:
        platform = s.scalar(
            select(ConversationTurn).where(
                ConversationTurn.study_id == study_id,
                ConversationTurn.role == "platform",
                ConversationTurn.seq == researcher.seq + 1,
            )
        )
        if platform is None:
            return None
        moves = []
        for move in s.scalars(
            select(DesignMoveRow)
            .where(DesignMoveRow.turn_id == platform.id)
            .order_by(DesignMoveRow.seq)
        ):
            item = {
                "moveId": move.id,
                "kind": move.kind,
                "target": move.target,
                "proposal": move.proposal,
                "patch": move.patch,
                "grounding": move.grounding,
                "status": move.status,
            }
            if move.kind == "merge-templates" and move.patch:
                item["mergeData"] = {
                    "templateIds": list(move.patch.get("templateIds") or []),
                    "reason": str(move.patch.get("reason") or ""),
                }
            moves.append(item)
        return {
            "researcherTurnId": researcher.id,
            "platformTurnId": platform.id,
            "text": platform.text,
            "moves": moves,
            "recommendations": platform.recommendations or [],
            "source": platform.source,
            "understanding": None,
            "turnIntent": "",
        }

    @app.post(
        "/studies/{study_id}/conversation/turns",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def append_turn(
        study_id: str,
        body: ConversationTurnIn,
        s: Session = Depends(db),
        identity: auth.Identity = Depends(resolve_identity),
    ) -> dict:
        _validate_decision_followup(s, study_id, body.decision)
        existing = _turn_for_request(s, study_id, body.requestId)
        if existing is not None:
            replay = _stored_turn_payload(s, study_id, existing)
            if replay is not None:
                return replay
        researcher = _append_researcher_turn(s, study_id, body)
        try:
            reply = design_assistant.respond(
                s,
                body.text,
                seq=researcher.seq + 1,
                study_id=study_id,
                client=_design_turn_client(),
                steer=body.steer,
                decision=body.decision.model_dump() if body.decision else None,
            )
        except design_assistant.ModelUnavailable as exc:
            log.info("design turn unanswered: %s", exc)
            return _persist_platform_turn(
                s, study_id, researcher, design_assistant.holding_turn(str(exc))
            )
        return _persist_platform_turn(s, study_id, researcher, reply)

    def _append_researcher_turn(
        s: Session, study_id: str, body: ConversationTurnIn
    ) -> ConversationTurn:
        researcher = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=_conversation_seq(s, study_id),
            role="researcher",
            author=body.author,
            text=body.text,
            retrieved_refs=[],
            created_at=now(),
            request_id=body.requestId or None,
        )
        s.add(researcher)
        s.flush()
        return researcher

    def _design_turn_client():
        return assistant.make_design_client()

    def _persist_platform_turn(
        s: Session, study_id: str, researcher: ConversationTurn, reply: dict
    ) -> dict:
        retrieved = set(reply["retrievedRefs"])
        for m in reply["moves"]:
            cited = {g["ref"] for g in m["grounding"]}
            assert cited <= retrieved, (  # noqa: S101 - FR-ETH-4 boundary
                f"move {m['moveId']} cites outside retrieved set: "
                f"{sorted(cited - retrieved)}"
            )
        platform = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=researcher.seq + 1,
            role="platform",
            author="Platform",
            text=reply["text"],
            retrieved_refs=sorted(retrieved),
            recommendations=reply["recommendations"],
            created_at=now(),
            source=reply["source"],
        )
        s.add(platform)
        for i, m in enumerate(reply["moves"]):
            s.add(
                DesignMoveRow(
                    id=f"{platform.id}:{m['moveId']}",
                    study_id=study_id,
                    turn_id=platform.id,
                    seq=i + 1,
                    kind=m["kind"],
                    target=m["target"],
                    proposal=m["proposal"],
                    patch=m["patch"],
                    grounding=m["grounding"],
                    status="proposed",
                )
            )
        s.commit()
        return {
            "researcherTurnId": researcher.id,
            "platformTurnId": platform.id,
            "text": reply["text"],
            "moves": [
                {
                    "moveId": f"{platform.id}:{m['moveId']}",
                    "kind": m["kind"],
                    "target": m["target"],
                    "proposal": m["proposal"],
                    "patch": m["patch"],
                    "grounding": m["grounding"],
                    "status": "proposed",
                    **(
                        {"mergeData": m["mergeData"]}
                        if m["kind"] == "merge-templates" and m.get("mergeData")
                        else {}
                    ),
                }
                for m in reply["moves"]
            ],
            "recommendations": reply["recommendations"],
            "source": reply["source"],
            "understanding": reply["understanding"],
            "turnIntent": reply["turnIntent"],
        }

    @app.post(
        "/studies/{study_id}/conversation/turns/stream",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def append_turn_streaming(
        study_id: str,
        body: ConversationTurnIn,
        s: Session = Depends(db),
        identity: auth.Identity = Depends(resolve_identity),
    ) -> StreamingResponse:

        def frames():
            try:
                _validate_decision_followup(s, study_id, body.decision)
                existing = _turn_for_request(s, study_id, body.requestId)
                if existing is not None:
                    replay = _stored_turn_payload(s, study_id, existing)
                    if replay is not None:
                        yield _sse("done", replay)
                        return
                researcher = _append_researcher_turn(s, study_id, body)
                stream = design_assistant.respond_streaming(
                    s,
                    body.text,
                    seq=researcher.seq + 1,
                    study_id=study_id,
                    client=_design_turn_client(),
                    steer=body.steer,
                    decision=body.decision.model_dump() if body.decision else None,
                )
                reply = None
                while True:
                    try:
                        prose = next(stream)
                    except StopIteration as done:
                        reply = done.value
                        break
                    yield _sse("token", {"text": prose})
                payload = _persist_platform_turn(s, study_id, researcher, reply)
                yield _sse("done", payload)
            except design_assistant.ModelUnavailable as exc:
                log.info("conversation turn unanswered: %s", exc)
                payload = _persist_platform_turn(
                    s, study_id, researcher, design_assistant.holding_turn(str(exc))
                )
                yield _sse("done", payload)
            except Exception as exc:
                log.exception("streaming conversation turn failed")
                s.rollback()
                yield _sse("error", {"detail": str(exc)})

        return StreamingResponse(
            frames(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get(
        "/studies/{study_id}/conversation",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def get_conversation(study_id: str, s: Session = Depends(db)) -> dict:
        turns = s.scalars(
            select(ConversationTurn)
            .where(ConversationTurn.study_id == study_id)
            .order_by(ConversationTurn.seq)
        ).all()
        moves_by_turn: dict[str, list] = defaultdict(list)
        for mv in s.scalars(
            select(DesignMoveRow)
            .where(DesignMoveRow.study_id == study_id)
            .order_by(DesignMoveRow.seq)
        ):
            wire = {
                "moveId": mv.id,
                "kind": mv.kind,
                "target": mv.target,
                "proposal": mv.proposal,
                "patch": mv.patch,
                "grounding": mv.grounding,
                "status": mv.status,
            }
            if mv.kind == "merge-templates" and isinstance(mv.patch, dict):
                wire["mergeData"] = {
                    "templateIds": list(mv.patch.get("templateIds") or []),
                    "reason": str(mv.patch.get("reason") or ""),
                }
            moves_by_turn[mv.turn_id].append(wire)

        study_refs = set(
            s.scalars(select(Paper.paper_ref).where(Paper.study_id == study_id))
        )

        def current_recommendations(recommendations: list | None) -> list:
            return [
                {
                    **recommendation,
                    "inStudy": recommendation.get("ref") in study_refs,
                }
                for recommendation in (recommendations or [])
            ]

        return {
            "studyId": study_id,
            "turns": [
                {
                    "turnId": t.id,
                    "seq": t.seq,
                    "role": t.role,
                    "author": t.author,
                    "text": "" if t.redacted else t.text,
                    "redacted": bool(t.redacted),
                    "moves": moves_by_turn.get(t.id, []),
                    "recommendations": current_recommendations(t.recommendations),
                    "source": t.source,
                }
                for t in turns
            ],
            "understanding": elicitation.understanding_summary(
                elicitation.assess_understanding(
                    design_assistant.researcher_texts(s, study_id)
                )
            ),
        }

    @app.post(
        "/studies/{study_id}/conversation/moves/{move_id}/decision",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def decide_move(
        study_id: str, move_id: str, body: MoveDecisionIn, s: Session = Depends(db)
    ) -> dict:
        if body.status not in ("accepted", "rejected", "proposed"):
            raise HTTPException(
                400, "status must be 'accepted', 'rejected', or 'proposed'"
            )
        mv = s.get(DesignMoveRow, move_id)
        if mv is None or mv.study_id != study_id:
            raise HTTPException(404, "design move not found")
        mv.status = body.status
        if body.status == "proposed":
            mv.decided_by = ""
            mv.decided_at = ""
        else:
            mv.decided_by = body.decidedBy
            mv.decided_at = now()

        adopted: list[str] = []
        if body.status == "accepted":
            for g in mv.grounding or []:
                ref = g.get("ref") if isinstance(g, dict) else None
                if not ref:
                    continue
                got = _adopt_corpus_paper(
                    s,
                    study_id,
                    str(ref),
                    added_via="grounding",
                    match_reason=str(g.get("why") or g.get("matchReason") or ""),
                )
                if got is not None:
                    adopted.append(got)
        s.commit()
        return {"moveId": move_id, "status": mv.status, "papersAdded": adopted}

    @app.post(
        "/studies/{study_id}/quick-protocol",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def create_quick_protocol(
        study_id: str, body: QuickProtocolIn, s: Session = Depends(db)
    ) -> dict:
        if any(
            not value.strip()
            for value in (
                body.title,
                body.researchQuestion,
                body.participantDescription,
                body.taskDescription,
            )
        ):
            raise HTTPException(422, "the study brief fields cannot be blank")
        conditions = [condition.strip() for condition in body.conditions]
        if any(not condition or len(condition) > 80 for condition in conditions):
            raise HTTPException(
                422, "each condition needs a short, non-empty name (80 characters max)"
            )
        if len({condition.casefold() for condition in conditions}) != 2:
            raise HTTPException(422, "the two conditions must be different")
        if body.design == "within-subjects" and not body.counterbalanced:
            raise HTTPException(
                422,
                "within-subjects studies in this quick path must counterbalance "
                "condition order",
            )
        if body.design == "between-subjects" and body.plannedParticipants < 6:
            raise HTTPException(
                422,
                "between-subjects studies need at least 6 planned participants",
            )

        scope = elicitation.classify_scope(
            [body.researchQuestion, body.taskDescription, body.participantDescription]
        )
        if scope != "supported":
            raise HTTPException(
                422,
                "Quick protocol is limited to task-based human–AI software-development "
                "studies that run in VS Code. Use the chat for a supported idea that "
                "needs shaping, or choose a different tool for exams, classroom, "
                "clinical, marketing, or general survey studies.",
            )

        measures = [measure.strip() for measure in body.measures]
        from middleware.measurements import MEASURES

        if set(measures) - MEASURES.keys():
            raise HTTPException(
                422, "Supported checklist outcomes: " + ", ".join(MEASURES)
            )
        if any(not measure or len(measure) > 100 for measure in measures):
            raise HTTPException(
                422,
                "each outcome needs a short, non-empty description "
                "(100 characters max)",
            )
        if len({measure.casefold() for measure in measures}) != len(measures):
            raise HTTPException(422, "selected outcomes must be different")

        template_id = (
            "within-subjects-crossover-v1"
            if body.design == "within-subjects"
            else "two-group-rct-v1"
        )
        parameters = {
            "studyId": study_id,
            "title": body.title.strip(),
            "researchQuestion": body.researchQuestion.strip(),
            "conditions": conditions,
            "participantPlan": body.plannedParticipants,
            "sessionMinutes": body.sessionMinutes,
            "taskDescription": body.taskDescription.strip(),
        }
        move_specs = [
            {
                "kind": "choose-template",
                "target": "design",
                "proposal": (
                    "Use a counterbalanced within-subjects comparison."
                    if body.design == "within-subjects"
                    else "Use a two-group between-subjects comparison."
                ),
                "patch": {
                    "templateId": template_id,
                    "parameters": parameters,
                    "selectedMeasures": measures,
                },
            },
            {
                "kind": "set-field",
                "target": "participants.description",
                "proposal": f"Recruit {body.participantDescription.strip()}.",
                "patch": {
                    "op": "set-field",
                    "path": ["participants", "description"],
                    "value": body.participantDescription.strip(),
                },
            },
            {
                "kind": "add-measure",
                "target": "measures[]",
                "proposal": "Measure " + ", ".join(measures) + ".",
                "patch": {"section": "measures", "op": "append", "value": measures},
            },
            {
                "kind": "declare-task",
                "target": "tasks[]",
                "proposal": f"Declare the task: {body.taskDescription.strip()}.",
                "patch": {
                    "id": "primary-task",
                    "title": body.taskDescription.strip()[:80],
                    "description": body.taskDescription.strip(),
                    "minutes": body.sessionMinutes,
                    "conditions": conditions,
                },
            },
        ]

        researcher = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=_conversation_seq(s, study_id),
            role="researcher",
            author="Researcher",
            text=(
                f"Quick protocol checklist submitted: {body.researchQuestion.strip()}"
            ),
            retrieved_refs=[],
            created_at=now(),
        )
        s.add(researcher)
        s.flush()
        platform = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=researcher.seq + 1,
            role="platform",
            author="Platform",
            text=(
                "The checklist is complete. I instantiated the matching study "
                "template and ran the protocol compiler. Review the verified draft "
                "before applying it."
            ),
            retrieved_refs=[],
            recommendations=[],
            created_at=now(),
            source="scripted",
        )
        s.add(platform)
        s.flush()
        moves = []
        for index, spec in enumerate(move_specs, start=1):
            move_id = f"{platform.id}:quick-{index}"
            move = {
                "moveId": move_id,
                **spec,
                "grounding": [],
                "status": "accepted",
            }
            moves.append(move)
            s.add(
                DesignMoveRow(
                    id=move_id,
                    study_id=study_id,
                    turn_id=platform.id,
                    seq=index,
                    kind=spec["kind"],
                    target=spec["target"],
                    proposal=spec["proposal"],
                    patch=spec["patch"],
                    grounding=[],
                    status="accepted",
                    decided_by="Researcher",
                    decided_at=now(),
                )
            )

        existing = s.get(ProtocolDraftRow, study_id)
        base_yaml = existing.yaml if existing else ""
        result = compiler.compile_moves(moves, base_yaml=base_yaml)
        comp = Compilation(
            id=secrets.token_hex(8),
            study_id=study_id,
            base_sha256=sha256(base_yaml.encode()).hexdigest(),
            draft_yaml=result.yaml,
            diff=result.diff,
            move_ids=[move["moveId"] for move in moves],
            errors=result.errors,
            unresolved=result.unresolved,
            valid=int(result.valid),
            created_at=now(),
        )
        s.add(comp)
        platform.text = (
            "The checklist is complete and the compiler "
            + ("verified the draft." if result.valid else "found issues to resolve.")
            + " Review the result before applying it."
        )
        s.commit()
        return {
            "compilationId": comp.id,
            "valid": result.valid,
            "errors": result.errors,
            "unresolved": result.unresolved,
            "warnings": result.warnings,
            "diff": result.diff,
            "yaml": result.yaml,
            "protocol": result.draft,
            "templateId": result.template_id,
            "selectedMeasures": measures,
            "participantDescription": body.participantDescription.strip(),
        }

    @app.post(
        "/studies/{study_id}/conversation/compile",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def compile_conversation(
        study_id: str, body: CompileIn, s: Session = Depends(db)
    ) -> dict:
        moves = [
            {
                "moveId": mv.id,
                "kind": mv.kind,
                "target": mv.target,
                "proposal": mv.proposal,
                "patch": mv.patch,
                "grounding": mv.grounding,
                "status": mv.status,
            }
            for mv in s.scalars(
                select(DesignMoveRow)
                .join(ConversationTurn, DesignMoveRow.turn_id == ConversationTurn.id)
                .where(DesignMoveRow.study_id == study_id)
                .order_by(ConversationTurn.seq, DesignMoveRow.seq)
            )
        ]
        base_yaml = body.baseYaml
        if base_yaml is None:
            existing = s.get(ProtocolDraftRow, study_id)
            base_yaml = existing.yaml if existing else ""
        result = compiler.compile_moves(moves, base_yaml=base_yaml)
        comp = Compilation(
            id=secrets.token_hex(8),
            study_id=study_id,
            base_sha256=sha256(base_yaml.encode()).hexdigest(),
            draft_yaml=result.yaml,
            diff=result.diff,
            move_ids=[m["moveId"] for m in moves if m["status"] == "accepted"],
            errors=result.errors,
            unresolved=result.unresolved,
            valid=int(result.valid),
            created_at=now(),
        )
        s.add(comp)
        s.commit()
        return {
            "compilationId": comp.id,
            "valid": result.valid,
            "errors": result.errors,
            "unresolved": result.unresolved,
            "warnings": result.warnings,
            "diff": result.diff,
            "yaml": result.yaml,
            "protocol": result.draft,
            "templateId": result.template_id,
        }

    @app.post(
        "/studies/{study_id}/conversation/approve",
        dependencies=[Depends(require_project_for_study("apply_draft"))],
    )
    def approve_compilation(
        study_id: str,
        body: ApproveIn,
        membership: Membership = Depends(require_project_for_study("apply_draft")),
        s: Session = Depends(db),
    ) -> dict:
        comp = s.get(Compilation, body.compilationId)
        if comp is None or comp.study_id != study_id:
            raise HTTPException(404, "compilation not found")
        if not comp.valid:
            raise HTTPException(
                409,
                "this draft did not pass validation and cannot be applied. "
                f"Resolve: {comp.errors or comp.unresolved}",
            )

        s.add(
            ApprovalEvent(
                study_id=study_id,
                compilation_id=comp.id,
                approved_by=body.approvedBy,
                role=str(membership.role),
                at=now(),
            )
        )
        comp.applied_at = now()
        draft = s.get(ProtocolDraftRow, study_id)
        if draft is None:
            draft = ProtocolDraftRow(study_id=study_id)
            s.add(draft)
        draft.yaml = comp.draft_yaml
        draft.compilation_id = comp.id
        draft.updated_at = now()
        s.commit()
        return {"applied": True, "compilationId": comp.id}

    @app.get(
        "/studies/{study_id}/conversation/export",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def export_elicitation(study_id: str, s: Session = Depends(db)) -> dict:
        conv = get_conversation(study_id, s)
        compilations = [
            {
                "compilationId": c.id,
                "valid": bool(c.valid),
                "moveIds": c.move_ids,
                "errors": c.errors,
                "appliedAt": c.applied_at or None,
            }
            for c in s.scalars(
                select(Compilation)
                .where(Compilation.study_id == study_id)
                .order_by(Compilation.created_at)
            )
        ]
        approvals = [
            {
                "compilationId": a.compilation_id,
                "approvedBy": a.approved_by,
                "role": a.role,
                "at": a.at,
            }
            for a in s.scalars(
                select(ApprovalEvent).where(ApprovalEvent.study_id == study_id)
            )
        ]
        draft = s.get(ProtocolDraftRow, study_id)
        return {
            "studyId": study_id,
            "turns": conv["turns"],
            "compilations": compilations,
            "approvals": approvals,
            "currentDraft": draft.yaml if draft else "",
        }

    @app.post(
        "/studies/{study_id}/simulate",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def simulate_study(
        study_id: str,
        body: SimulateIn,
        request: Request,
        s: Session = Depends(db),
    ) -> dict:
        from middleware.simulation import PROFILES, run_plan_summary, simulate_into

        proto = _resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(
                409,
                f"study {study_id!r} has no compiled protocol yet. "
                "Approve a draft in the design conversation first",
            )
        if body.count < 1 or body.count > 100:
            raise HTTPException(400, "count must be between 1 and 100")
        if body.profile not in PROFILES and body.profile != "mixed":
            raise HTTPException(
                400, f"profile must be one of mixed|{'|'.join(PROFILES)}"
            )
        base = str(request.base_url).rstrip("/")
        outcome = simulate_into(
            s,
            proto,
            study_id,
            body.count,
            profile=body.profile,
            seed=body.seed,
            base_url=base,
            now=now,
            start=clock(),
        )
        outcome["studyId"] = study_id
        s.flush()
        session_ids = set(outcome["sessionIds"])
        rows = [
            row
            for row in _joined_rows(s, study_id, True)
            if row["sessionId"] in session_ids
        ]
        outcome["plan"] = run_plan_summary(proto, rows, study_id)
        return outcome

    @app.post(
        "/studies/{study_id}/sessions/start",
        dependencies=[Depends(require_project_for_study("run_recipe"))],
    )
    def start_session(
        study_id: str, body: SessionStartIn, s: Session = Depends(db)
    ) -> dict:
        existing = s.get(SessionOpen, body.sessionId)
        if existing is not None:
            return {
                "sessionId": existing.session_id,
                "protocolVersion": existing.protocol_version,
                "resumed": True,
            }
        s.add(
            SessionOpen(
                session_id=body.sessionId,
                study_id=study_id,
                protocol_version=1,
                opened_at=now(),
            )
        )
        s.commit()
        return {
            "sessionId": body.sessionId,
            "protocolVersion": 1,
            "resumed": False,
        }

    @app.get("/health")
    def health() -> dict:
        try:
            with session_factory() as s:
                s.execute(sqltext("SELECT 1"))
            db_ok = True
        except Exception:  # noqa: BLE001 - /health reports degraded, never raises
            db_ok = False
        payload = {
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "unreachable",
            "studyId": check.study_id,
            "protocolLoaded": protocol_doc is not None,
            "knownEventSchemaVersions": sorted(KNOWN_EVENT_SCHEMA_VERSIONS),
        }
        if not db_ok:
            raise HTTPException(status_code=503, detail=payload)
        return payload

    @app.get("/auth/config")
    def auth_config() -> dict:
        return auth.public_config(settings)

    dist = settings.spa_dist
    index_html = dist / "index.html"
    if index_html.is_file():
        _no_store = {"Cache-Control": "no-cache"}

        def _shell() -> FileResponse:
            return FileResponse(index_html, headers=_no_store)

        @app.get("/", include_in_schema=False)
        def spa_index() -> FileResponse:
            return _shell()

        @app.get("/home", include_in_schema=False)
        @app.get("/signin", include_in_schema=False)
        def spa_home_route() -> FileResponse:
            return _shell()

        @app.get("/p/{rest:path}", include_in_schema=False)
        def spa_project_route(rest: str) -> FileResponse:
            return _shell()

        @app.get("/invitations/{rest:path}", include_in_schema=False)
        def spa_invite_route(rest: str) -> FileResponse:
            return _shell()

        @app.get("/repertoire", include_in_schema=False)
        def spa_repertoire_route() -> FileResponse:
            return _shell()

        @app.get("/start", include_in_schema=False)
        def spa_start_route() -> FileResponse:
            return _shell()

        @app.get("/settings", include_in_schema=False)
        def spa_settings_route() -> FileResponse:
            return _shell()

        class PlatformFiles(StaticFiles):
            async def get_response(self, path, scope):
                try:
                    return await super().get_response(path, scope)
                except StarletteHTTPException as exc:
                    if (
                        exc.status_code == 404
                        and scope["method"] in {"GET", "HEAD"}
                        and "text/html" in Request(scope).headers.get("accept", "")
                        and not Path(path).suffix
                    ):
                        return FileResponse(
                            index_html, status_code=404, headers=_no_store
                        )
                    raise

        app.mount("/", PlatformFiles(directory=dist), name="platform")

    return app


def _ensure_study_row(s: Session, study_id: str, protocol_doc: dict) -> None:

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


def _event_json(e: Event) -> dict:
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
        "payload": e.payload,
        "flags": e.flags,
    }
