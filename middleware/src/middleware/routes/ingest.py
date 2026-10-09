"""Ingest API routes."""

import logging
from collections import defaultdict
from hashlib import sha256

from fastapi import (
    Depends,
    FastAPI,
    Form,
    Header,
    HTTPException,
    UploadFile,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from middleware.db import (
    Event,
    MetricRow,
    SessionBlock,
    SessionOpen,
    StoredFile,
)
from middleware.route_helpers import (
    DEFAULT_SOURCE,
    _event_json,
    _gap_summary,
    canonical_source,
)
from middleware.routes.deps import ApiDeps
from middleware.schemas import (
    EventBatch,
    SessionStartIn,
    StudyEventIn,
)

log = logging.getLogger("middleware.app")


def register(app: FastAPI, deps: ApiDeps):
    @app.post("/ingest/events")
    def ingest_events(
        batch: EventBatch | list[StudyEventIn],
        authorization: str = Header(default=""),
        s: Session = Depends(deps.db),
    ) -> dict:
        events = batch if isinstance(batch, list) else batch.events
        batch_source = "" if isinstance(batch, list) else batch.source
        received = deps.now()
        cred_row = deps.resolve_credential(s, authorization)
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
                if s.get(SessionOpen, e.sessionId) is None:
                    s.add(
                        SessionOpen(
                            session_id=e.sessionId,
                            study_id=cred_row.study_id,
                            protocol_version=1,
                            opened_at=received,
                        )
                    )
                expected = block.condition if block else cred_row.condition
                if (e.participantId and e.participantId != cred_row.participant_id) or (
                    e.condition and e.condition != expected
                ):
                    extra_flags.append("credential-mismatch")
                pid, cond = cred_row.participant_id, expected
            elif bearer_present:
                extra_flags.append("unauthenticated")
            flags = deps.check.flags_for(pid, cond, e.v) + extra_flags
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
                    # Server-stamped from the session's block, never taken from the
                    # client: what the participant was asked to do is the study's fact,
                    # not the editor's claim.
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
    def ingest_metrics(rows: list[dict], s: Session = Depends(deps.db)) -> dict:
        from middleware.ingest_core import store_metric_rows

        received = deps.now()
        flagged = 0
        flags_by_row: list[list[str]] = []
        for row in rows:
            participant_id = str(row.get("participantId", ""))
            condition = str(row.get("condition", ""))
            session_id = str(row.get("sessionId", ""))
            task_id = str(row.get("taskId", ""))
            flags = deps.check.flags_for(participant_id, condition, None)
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
        s: Session = Depends(deps.db),
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
        deps.settings.files_dir.mkdir(parents=True, exist_ok=True)
        stored = deps.settings.files_dir / f"{digest[:16]}-{file.filename}"
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
            uploaded_at=deps.now(),
        )
        s.add(record)
        s.flush()
        return {"id": record.id, "sha256": digest, "duplicate": False}

    @app.get(
        "/studies/{study_id}/sessions",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def list_sessions(
        study_id: str, includeSynthetic: bool = False, s: Session = Depends(deps.db)
    ) -> list[dict]:
        in_this_study = deps.session_scope(study_id, includeSynthetic)

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
        dependencies=[Depends(deps.authz["require_project_for_session"]("view"))],
    )
    def session_events(
        session_id: str,
        type: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 10_000,
        s: Session = Depends(deps.db),
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
        dependencies=[Depends(deps.authz["require_project_for_session"]("view"))],
    )
    def session_gaps(session_id: str, s: Session = Depends(deps.db)) -> dict:
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

    @app.get("/files", dependencies=[Depends(deps.view_auth)])
    def list_files(s: Session = Depends(deps.db)) -> list[dict]:
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

    @app.post(
        "/studies/{study_id}/sessions/start",
        dependencies=[Depends(deps.authz["require_project_for_study"]("run_recipe"))],
    )
    def start_session(
        study_id: str, body: SessionStartIn, s: Session = Depends(deps.db)
    ) -> dict:
        """Open a data-collection session under the study's protocol (FR-CONV-4)."""
        existing = s.get(SessionOpen, body.sessionId)
        if existing is not None and existing.study_id != study_id:
            raise HTTPException(409, "Session id already belongs to another study")
        if existing is not None:
            return {
                "sessionId": existing.session_id,
                "protocolVersion": existing.protocol_version,
                "resumed": True,
            }
        proto = deps.resolve_study_protocol(s, study_id)
        protocol_version = (proto or {}).get("protocolVersion", 1)
        s.add(
            SessionOpen(
                session_id=body.sessionId,
                study_id=study_id,
                protocol_version=protocol_version,
                opened_at=deps.now(),
            )
        )
        s.commit()
        return {
            "sessionId": body.sessionId,
            "protocolVersion": protocol_version,
            "resumed": False,
        }
