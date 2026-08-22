"""FastAPI ingestion service (FR-ING-1..6)."""

import csv
import io
import itertools
import json
import logging
import os
import re
import secrets
import tempfile
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
    PlainTextResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from protocol.assignment import assign, tasks_of
from protocol.errors import ProtocolError
from protocol.export import build_kit
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, union
from sqlalchemy import text as sqltext
from sqlalchemy.orm import Session

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
from middleware.settings import Settings

# Event schema versions this service is written against; other versions are stored and
# flagged, never rejected (FR-PROT-2 discipline).
KNOWN_EVENT_SCHEMA_VERSIONS = {2, 3, 4, 5}

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


class StudyEventIn(BaseModel):
    """Extension StudyEvent (schema v2)."""

    sessionId: str
    seq: int
    v: int = -1
    ts: str = ""
    mono: float = -1
    participantId: str = ""
    condition: str = ""
    type: str = ""
    payload: dict = Field(default_factory=dict)
    source: str = ""


class EventBatch(BaseModel):
    """The HttpSink wire format; a bare event array is also accepted."""

    source: str = ""
    events: list[StudyEventIn]



class RecipeRunIn(BaseModel):
    """One recipe run recorded by the analysis runner."""

    recipeId: str
    status: str = "ok"
    answers: list[str] = Field(default_factory=list)
    note: str = ""


class PaperIngestIn(BaseModel):
    """Ingest one paper by identifier (FR-LIT-1 id path)."""

    arxivId: str = ""
    doi: str = ""


class PaperLinksIn(BaseModel):
    """Replace a paper's protocol-element links (FR-LIT-3)."""

    targets: list[str] = Field(default_factory=list)



class MatchIn(BaseModel):
    """One idea → papers match request (FR-LIT-9)."""

    query: str
    limit: int = 5


class FromMatchIn(BaseModel):
    """Accept a recommendation card into the study's paper set (FR-LIT-9.3)."""

    ref: str
    matchReason: str = ""


class ConversationTurnIn(BaseModel):
    """One researcher turn (FR-CONV-1)."""

    text: str
    author: str = "Researcher"
    steer: str | None = None


class MoveDecisionIn(BaseModel):
    """Accept, reject, or reopen ("proposed") one design move (FR-CONV-1.2)."""

    status: str
    decidedBy: str = "Researcher"


class CompileIn(BaseModel):
    """Compile the study's accepted moves into a draft diff (FR-CONV-3)."""

    baseYaml: str | None = None


class ApproveIn(BaseModel):
    """Apply one compiled diff (FR-CONV-3.4) - the audited step."""

    compilationId: str
    approvedBy: str = "Researcher"
    rationale: str = ""


class SessionStartIn(BaseModel):
    """
    Open a data-collection session under the study's current protocol revision
    (FR-CONV-4, F4.2/F4.3).
    """

    sessionId: str


class TemplateInstantiateIn(BaseModel):
    """Instantiate a template with parameter values (FR-TPL-1.4)."""

    parameters: dict = Field(default_factory=dict)
    studyId: str = ""
    title: str = ""



class MintTokensIn(BaseModel):
    """Mint a batch of enrollment (pairing) tokens for a study (FR-INST-20)."""

    count: int = 1
    grain: str = "participant"
    # Per-mint capture-config overrides, layered on the protocol-derived defaults for
    # every token in the batch. ``{"toggles": [{"instrument", "path", "value"}, ...]}``.
    overrides: dict | None = None


class RedeemIn(BaseModel):
    """
    The raw token half of a connection string, POSTed by the extension to pair a
    live-capture session (FR-INST-20/21).
    """

    token: str


class SimulateIn(BaseModel):
    """Synthetic dry-run settings (POST /studies/{study_id}/simulate)."""

    count: int = 5
    profile: str = "mixed"
    seed: int | None = None


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
        """
        Resolve a study's protocol: the compiled draft, then the boot protocol (the
        single-facilitator fallback for a study never taken through the design
        conversation).
        """
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

    # The repository ships the full corpus, so a fresh local database should not
    # silently degrade every grounded template into "seen in 0 papers". Import it in
    # a daemon thread so the health endpoint and the shell become usable immediately.
    # Test databases stay hermetic; operators can force either behavior explicitly.
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
    def ingest_metrics(rows: list[dict], s: Session = Depends(db)) -> dict:
        from middleware.ingest_core import store_metric_rows

        received = now()
        flagged = 0
        flags_by_row: list[list[str]] = []
        for row in rows:
            flags = check.flags_for(
                str(row.get("participantId", "")), str(row.get("condition", "")), None
            )
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


    def _session_scope(study_id: str):
        """
        A predicate for "this session_id belongs to this study".

        Sessions are attributed through ``SessionOpen``/``SessionBlock``; events
        and metric rows carry only a ``session_id``, so any query that reads
        them per-study MUST go through this. `/studies/{id}/status` did not, and
        returned every session in the database for whichever study was asked  -
        one project's Data tab listing another's participants. Shared by both
        readers so they cannot drift apart again.
        """
        scoped = union(
            select(SessionOpen.session_id).where(SessionOpen.study_id == study_id),
            select(SessionBlock.session_id).where(SessionBlock.study_id == study_id),
        )
        # Multi-tenant (clerk) never adopts them: an unattributable session there could
        # have come from anyone, which is precisely the leak this scoping closes.
        adopt_unattributed = settings.auth != "clerk" and check.study_id == study_id
        mapped = union(select(SessionOpen.session_id), select(SessionBlock.session_id))

        def in_this_study(column):
            here = column.in_(scoped)
            return or_(here, column.notin_(mapped)) if adopt_unattributed else here

        return in_this_study

    @app.get(
        "/studies/{study_id}/sessions",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def list_sessions(study_id: str, s: Session = Depends(db)) -> list[dict]:
        in_this_study = _session_scope(study_id)

        out = {}
        event_rows = s.execute(
            select(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                func.count(),
                func.min(Event.ts),
                func.max(Event.ts),
            )
            .where(in_this_study(Event.session_id))
            .group_by(Event.session_id, Event.participant_id, Event.condition)
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
            )
            .where(in_this_study(MetricRow.session_id))
            .group_by(
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

    def _joined_rows(s: Session) -> list[dict]:
        """
        The joined one-timeline rows (FR-ING-4), in-process.

        Shared by the dataset export and the dry run's plan validation, so the
        statistics a dry run reports are computed over exactly the rows a
        researcher would download  -  not a second, drifting join.
        """
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
        return rows

    @app.get(
        "/studies/{study_id}/dataset",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def dataset(study_id: str, format: str = "json", s: Session = Depends(db)):
        """The joined one-timeline export all legs share (FR-ING-4)."""
        rows = _joined_rows(s)
        if format == "json":
            return {"studyId": study_id, "rows": rows}
        if format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            header = [
                "source",
                "ts",
                "sessionId",
                "participantId",
                "condition",
                "type",
                "seq",
                "flags",
                "payload",
            ]
            writer.writerow(header)
            for r in rows:
                writer.writerow(
                    [
                        r[k] if k not in ("flags", "payload") else json.dumps(r[k])
                        for k in header
                    ]
                )
            return PlainTextResponse(buf.getvalue(), media_type="text/csv")
        raise HTTPException(400, "format must be 'json' or 'csv'")


    @app.get(
        "/studies/{study_id}/protocol",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def study_protocol(study_id: str, s: Session = Depends(db)) -> dict:
        """
        Protocol summary for the overview card (FR-DASH-1) and the traceability chips
        (FR-DASH-6): RQ -> planned recipes comes verbatim from the protocol's analysis
        plan.
        """

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
            # The resolved protocol as-is, for surfaces that render the whole
            # document rather than this card's summary of it. The conversation's
            # draft rail is the reason: it could only obtain a protocol from
            # `/conversation/compile`, which needs a contribute capability, so
            # every viewer  -  and every visitor to the read-only demo  -  saw an
            # empty "no design shape yet" rail over a fully compiled protocol.
            # Additive: the summary fields above are unchanged.
            "document": proto,
        }

    @app.get(
        "/studies/{study_id}/status",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def study_status(study_id: str, s: Session = Depends(db)) -> dict:
        """One factual status document (FR-DASH-7)."""

        proto = _resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")

        # Every read below is scoped to this study's sessions; without it the
        # status document described the whole database (see `_session_scope`).
        in_this_study = _session_scope(study_id)

        seqs_by_session: dict[str, dict[str, list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for sid, src, seq in s.execute(
            select(Event.session_id, Event.source, Event.seq).where(
                in_this_study(Event.session_id)
            )
        ):
            seqs_by_session[sid][src].append(seq)

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
        for sid, pid, cond, n, last_recv in s.execute(
            select(
                Event.session_id,
                Event.participant_id,
                Event.condition,
                func.count(),
                func.max(Event.received_at),
            )
            .where(in_this_study(Event.session_id))
            .group_by(Event.session_id, Event.participant_id, Event.condition)
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
            )
            .where(in_this_study(MetricRow.session_id))
            .group_by(
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
        """
        Sessions with ingests inside the window (FR-DASH-3), with per- bucket receive
        counts for the event-rate sparkline.
        """

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
                # Un-clamped, a negative age floor-divides to a negative bucket offset
                # and indexes past the end of `rate`, which crashed this route outright
                # the moment a study had ever run a dry run - the offending IndexError
                # never depended on anything about the study, so it was invisible until
                # real data (simulated or otherwise) actually triggered it.
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
        """Record one analysis-recipe run."""

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
        """The study's paper set."""

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
        """
        A Semantic Scholar GET wrapped in the DB cache (D8, NFR-7): the graph renders
        offline after the first fetch.
        """

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
        """
        Seed a newly-ingested paper's protocol links from the protocol's ``literature:``
        list (FR-LIT-3), idempotently.
        """
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
        """Copy the corpus's own edges touching ``paper_ref`` into this study."""
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
        """Fetch and store the paper's graph neighbourhood (FR-LIT-2)."""
        # Adding the same paper again should be a local idempotent read, not another
        # three remote calls. The persistent response cache handles individual URLs;
        # this guard handles the more common whole-paper repeat.
        if s.scalar(
            select(PaperEdge.id).where(
                PaperEdge.study_id == study_id,
                PaperEdge.src_ref == paper_ref,
                PaperEdge.kind.in_(
                    ("references", "citations", "recommendations")
                ),
            )
        ) is not None:
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
        """Enrich after the paper has already become visible to the researcher."""
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
        """
        Ingest one paper by arXiv id / DOI (FR-LIT-1 id path): fetch S2 metadata, index
        it, and harvest its graph neighbourhood (FR-LIT-2).
        """

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
        # Release the request transaction before the background session opens its
        # enrichment transaction. This matters for SQLite, where a response that is
        # already ready can still hold the writer lock until dependency cleanup.
        s.commit()
        # Metadata is the blocking part of the add action. The neighbourhood is useful
        # but not required to confirm the paper, so let the graph catch up in a fresh
        # session after this response is sent.
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
        """
        Ingest a paper from a PDF (FR-LIT-1 PDF path): extract text + a title guess
        locally (D21), then enrich by DOI/title via S2 when possible.
        """

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
        paper_index.deindex_paper(s, paper_ref)
        return {"deleted": paper_ref}

    @app.get(
        "/studies/{study_id}/papers/graph",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def papers_graph(study_id: str, s: Session = Depends(db)) -> dict:
        """
        The related-papers graph (FR-LIT-2): ingested nodes (solid) plus suggested stub
        nodes (hollow, un-ingested), and the typed edges between them - the
        ResearchRabbit-style view's data.
        """

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
                "citationCount": p.citation_count,
                "ingested": True,
            }

        # A harvested edge may point back to a corpus paper that has not been
        # ingested into this study. The old response only materialised the
        # destination stub, leaving that edge's source without a node. The
        # client quite correctly refused to paint a path between a node and
        # nothing, which made references, citations, and recommendations all
        # appear to have vanished. Materialise both endpoints, preferring
        # study metadata and then the shared corpus metadata when available.
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
            nodes[ref] = {
                "paperRef": ref,
                "title": p.title if p else "",
                "authors": (p.authors if p else None) or [],
                "year": p.year if p else None,
                "citationCount": p.citation_count if p else None,
                "ingested": False,
            }

        for e in edges:
            if e.dst_ref not in nodes:
                nodes[e.dst_ref] = {
                    "paperRef": e.dst_ref,
                    "title": e.dst_title,
                    "authors": e.dst_authors or [],
                    "year": e.dst_year,
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
        """Idea → paper recommendations via the match ladder (FR-LIT-9)."""
        recommendations = matching.match_papers(
            s,
            body.query,
            study_id=study_id,
            limit=body.limit,
            use_llm=assistant.configured(),
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
        """
        Copy one corpus paper into a study's own paper set, or return None if the corpus
        does not hold it.
        """
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
        """
        One-click ingest of a recommendation card (FR-LIT-9.3): the corpus row joins the
        study's paper set with ``addedVia=match`` and the match reason kept - it is
        elicitation evidence.
        """
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
        # A corpus recommendation may carry provenance edges but not the full
        # Semantic Scholar neighbourhood. Start the same enrichment used by
        # direct ingest so accepting a recommendation grows the graph too.
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
        """Replace a paper's protocol-element links (FR-LIT-3)."""

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
        """Event schema for agent consumption (FR-AGF-1)."""
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
                        "Event schema version. Current: 3 (behavioral telemetry leg, "
                        "). v4 reserved for agent-interaction leg."
                    ),
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 4,
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
        """Protocol schema for agent consumption (FR-AGF-1)."""
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
        """Template schema for agent consumption (FR-AGF-1)."""
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
        """Template registry index for agent consumption (FR-AGF-1)."""
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
                    # Skip files that can't be parsed.
                    continue

        return {"templates": templates, "count": len(templates), "generatedAt": now()}

    @app.get("/conversation/profiles")
    def researcher_profiles() -> dict:
        """The researcher profiles the design conversation adapts to (FR-CONV-9)."""
        return {
            "profiles": elicitation.profile_catalog(),
            "default": elicitation.DEFAULT_PROFILE,
        }


    @app.get("/papers/index")
    def corpus_index() -> dict:
        """Corpus index for agent consumption (FR-AGF-1)."""
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
        """Create a new project (FR-PLAT-1), or return existing implicit project."""
        name = str(body.get("name", "")).strip()
        if not name:
            raise HTTPException(400, "name is required")

        # Phase 6: Implicit personal projects. If the caller creates a project named
        # "Personal", check if they already have one  -  if so, return it (reusable).
        if name == "Personal":
            existing = s.scalar(
                select(Project).join(Membership).where(
                    (Project.name == "Personal")
                    & (Membership.identity_sub == identity.sub)
                    & (Membership.role == "owner")
                )
            )
            if existing:
                study_count = s.scalar(
                    select(func.count())
                    .select_from(Study)
                    .where(Study.project_id == existing.id)
                ) or 0
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
        # Returning a partial row here is what made the list and the create response two
        # different types wearing one name.
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
        """
        My project memberships (FR-PLAT-2), each carrying the shape of what is inside it
        (FR-PLAT-1): how many studies it holds.
        """
        rows = s.execute(
            select(Project, Membership.role)
            .join(Membership, Membership.project_id == Project.id)
            .where(Membership.identity_sub == identity.sub)
            .order_by(Project.created_at.desc())
        ).all()
        # The demo carries no membership rows by design (middleware.demo), so a join on
        # memberships can never find it.
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
        """Project home payload: project info, studies, members preview."""
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
        """
        Start a new study in this project (FR-PLAT-1 continued): the design conversation
        needs a study row to attach its moves/drafts to before it can run
        -  this is that row, empty and pre-design, ready for the researcher to talk it
        into existence.
        """
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

    # The corpus study is never a target (it isn't a project study).
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
        """
        Delete a study and everything scoped to it (FR-PLAT-1): its conversation, design
        moves, drafts, papers, enrollment, and mining records.
        """
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
        # A member can invite peers (D40), but only an owner can mint an owner invite  -
        # otherwise invite_member would be a backdoor to ownership.
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
        """Accept an invitation (FR-PLAT-3). A share link stays valid for
        everyone who clicks it until it expires or is revoked."""
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
            # It used to be a bare round-robin over conditions, which is a
            # between-subjects assignment applied regardless of what the protocol
            # declared  -  a within-subjects participant got one condition and never met
            # the other, so nobody was ever their own comparison.
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
        """List a study's active enrollment tokens (FR-INST-20)."""
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
                .where(Event.received_at >= cutoff_s)
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
                        overrides=r.capture_overrides,
                    )
                    capture_config = {
                        "captureConfigVersion": cfg["captureConfigVersion"],
                        "enabledInstruments": enrollment.enabled_instruments(
                            cfg["settings"]
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
        """Revoke a pairing token (researcher+, study-scoped)."""

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
        """List togglable capture metrics for a study's protocol shape (FR-DASH-11)."""
        protocol = _resolve_study_protocol(s, study_id)
        if protocol is None:
            raise HTTPException(404, "study not found")
        return enrollment.toggle_catalog(protocol)

    class ToggleIn(BaseModel):
        instrument: str
        path: list[str]
        value: object
        rationale: str = ""

    @app.post(
        "/studies/{study_id}/enrollment/toggles",
        dependencies=[Depends(require_project_for_study("toggle_capture"))],
    )
    def apply_toggle(study_id: str, body: ToggleIn, s: Session = Depends(db)) -> dict:
        """Apply one metric toggle to the protocol's instruments block (FR-DASH-11)."""
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
        """
        Redeem a connection-string token into a live-capture session (FR-INST-20/21).
        """

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
                overrides=row.capture_overrides,
            ),
            "consentStatement": enrollment.consent_statement(protocol, row.condition),
            "contentPolicy": enrollment.content_policy(protocol),
        }

    def resolve_credential(s: Session, authorization: str):
        """
        Return the ``EnrollmentToken`` for a valid Bearer session credential, else
        ``None``.
        """

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
            # A DB/infra error here (SQLite lock, I/O error, any SQLAlchemy error) must
            # never surface as a 500 that drops the whole ingest batch - degrade to the
            # already-correct "bearer present but unresolved" path (Task A7, NFR-1/
            # FR-ING-6).
            return None

    def _task_by_id(protocol: dict, task_id: str) -> dict | None:
        from protocol.assignment import tasks_of

        return next((t for t in tasks_of(protocol) if t.get("id") == task_id), None)

    def _block_for_session(
        s: Session, protocol: dict, row, session_id: str | None
    ) -> tuple[dict | None, dict | None]:
        """Which task and condition this session runs, as ``(task, block)``."""
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
        sessionId: str | None = None,
        authorization: str = Header(default=""),
        s: Session = Depends(db),
    ) -> dict:
        """
        Session-boundary re-pull of the capture config (FR-INST-21): the extension
        re-fetches this at the start of each session so a protocol change lands
        without re-pairing.
        """
        row = resolve_credential(s, authorization)
        if row is None or row.study_id != study_id:
            raise HTTPException(401, "a valid session credential is required")
        protocol = _resolve_study_protocol(s, study_id)
        if protocol is None:
            raise HTTPException(404, "no protocol for this study")
        task, block = _block_for_session(s, protocol, row, sessionId)
        return enrollment.build_capture_config(
            protocol,
            row.participant_id,
            (block or {}).get("condition") or row.condition,
            task=task,
            block=block,
            overrides=row.capture_overrides,
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
        """
        The power/sensitivity curve for the study's planned comparison (P2-2): exact
        two-sample t-test power (non-central t, equal per-group n, two-sided) across
        per-group n, plus the first n reaching the target power, per effect size.
        """
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
                participants.get("design", "")
                if isinstance(participants, dict)
                else ""
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
            if not design:
                result["note"] = (
                    "No planned comparison yet. Describe the conditions and study "
                    "design in Conversation before using recruitment planning."
                )
            return result
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    def _profile_prefs(s: Session, sub: str) -> dict:
        """The persisted prefs for ``sub`` (FR-OPS-7)."""
        row = s.get(UserProfile, sub)
        return dict(row.prefs) if row is not None else {}

    @app.get("/me", dependencies=[Depends(resolve_identity)])
    def get_me(identity: auth.Identity = Depends(resolve_identity)) -> dict:
        """Identity + memberships + preferences (FR-OPS-7)."""
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

    KNOWN_PREF_KEYS = frozenset(
        {"theme", "savedViews"}
    )

    @app.put(
        "/me/preferences",
        dependencies=[Depends(resolve_identity)],
    )
    def put_preferences(
        body: dict,
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        """Persist this identity's profile preferences (FR-OPS-7)."""
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
        """Template + parameters → a validated protocol draft (FR-TPL-1.4)."""
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
        """
        The statistical-plan explainer (FR-TPL-2.3): each choice in plain language with
        its why  -  never a bare test name.
        """
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
        """
        The protocol repertoire (FR-TPL): design shapes ranked common → rare by how many
        corpus papers use them, each carrying its ranked references.
        """
        corpus = corpus_importer.corpus_status_for_session(s)
        # Do not repeatedly scan a partially imported corpus. The client keeps the
        # small readiness poll cheap and only asks for the full ranking once every
        # manifest row is present, so partial matches can never look authoritative.
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
        """
        Compose several templates into one novel, grounded protocol at runtime (FR-TPL):
        borrow a measure from one published design and an analysis from another.
        """
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
        """
        Search the corpus for papers (FR-LIT-9), not study-scoped  -  powers the "turn
        this paper into a template" picker.
        """
        query = q.strip()
        if not query:
            return {"results": []}
        results = matching.match_papers(
            s, query, study_id=None, limit=max(1, min(limit, 25))
        )
        return {"results": results}

    @app.get("/corpus/status")
    def corpus_status(s: Session = Depends(db)) -> dict:
        """
        How much of the corpus carries a real abstract, not just a title (FR-LIT-8
        quality).
        """
        return {
            **corpus_importer.corpus_status_for_session(s),
            **corpus_enrich.enrichment_status_for_session(s),
        }

    @app.post("/templates/from-paper")
    def template_from_paper(body: dict, s: Session = Depends(db)) -> dict:
        """
        Turn a corpus paper into an executable template by binding it to a base
        archetype (FR-TPL-4): the paper becomes the design's primary source, so any of
        the corpus's thousands of papers is a starting point without hand-authoring a
        template each.
        """
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
        """
        The deterministic, LLM-free prescription table (FR-TPL-6): design shape →
        the exact test, effect size, correction, and sample-size guidance, each with its
        rationale.

        Without ``study_id`` this is the full reference table  -  every shape PHOENIX
        knows how to prescribe, the browsable catalogue. With ``study_id``, it's
        filtered to the shape(s) that study's *own compiled protocol* actually calls
        for (read off ``analysisPlan[].recipes[]`` and mapped back through the same
        shape→recipe table the compiler used to pick them)  -  "what analysis your
        design calls for" was previously showing the full catalogue unconditionally
        on every study's Data tab, identical regardless of that study's actual
        design, which the researcher reads as bespoke guidance it isn't.
        """
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
            participants.get("design", "")
            if isinstance(participants, dict)
            else ""
        )
        # Domain-specific recipes answer the study's operational questions, while
        # the prescription catalogue is keyed by statistical design shape. The
        # protocol's participant design is the authoritative bridge when a
        # recipe has no generic shape mapping.
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
        """
        Append a researcher turn and generate the platform's grounded reply (FR-CONV-1).
        """
        researcher = _append_researcher_turn(s, study_id, body)
        try:
            reply = design_assistant.respond(
                s,
                body.text,
                seq=researcher.seq + 1,
                study_id=study_id,
                client=_design_turn_client(),
                steer=body.steer,
            )
        except design_assistant.ModelUnavailable as exc:
            log.info("design turn unanswered: %s", exc)
            # Persisted like any other reply, not held in memory only. The
            # unpersisted version was the researcher's own question surviving
            # a reload while the platform's explanation of why it went
            # unanswered did not  -  so the exact moment a plain answer mattered
            # most was the one moment it was allowed to vanish. `source:
            # "unavailable"` still marks it as neither grounded nor scripted;
            # the client already renders that source as "Not answered"
            # (StreamingTurn.tsx) rather than as a real reply.
            return _persist_platform_turn(
                s, study_id, researcher, design_assistant.holding_turn(str(exc))
            )
        return _persist_platform_turn(s, study_id, researcher, reply)

    def _append_researcher_turn(
        s: Session, study_id: str, body: ConversationTurnIn
    ) -> ConversationTurn:
        """Land the researcher's own turn; its seq settles the reply's."""
        researcher = ConversationTurn(
            id=secrets.token_hex(8),
            study_id=study_id,
            seq=_conversation_seq(s, study_id),
            role="researcher",
            author=body.author,
            text=body.text,
            retrieved_refs=[],
            created_at=now(),
        )
        s.add(researcher)
        s.flush()
        return researcher


    def _design_turn_client():
        """
        Use the platform's sole Mistral Large model for the design conversation. These
        turns shape the researcher's protocol, so the model boundary stays explicit.
        """
        return assistant.make_client()

    def _persist_platform_turn(
        s: Session, study_id: str, researcher: ConversationTurn, reply: dict
    ) -> dict:
        """Persist the platform reply + its moves and return the wire shape."""
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
                        if m["kind"] == "merge-templates"
                        and m.get("mergeData")
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
        """The same turn as ``POST .../turns``, streamed (NFR-12)."""

        def frames():
            try:
                researcher = _append_researcher_turn(s, study_id, body)
                stream = design_assistant.respond_streaming(
                    s,
                    body.text,
                    seq=researcher.seq + 1,
                    study_id=study_id,
                    client=_design_turn_client(),
                    steer=body.steer,
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
                # Keep the researcher's own turn so they never have to retype it, and
                # close the stream with a normal `done` frame carrying the holding turn
                # - an `error` frame would leave the thread looking broken rather than
                # waiting.
                #
                # Persisted, same as the blocking endpoint's branch just above
                # and for the same reason: unpersisted, a reload kept the
                # researcher's question on screen and silently dropped the one
                # sentence explaining why nothing answered it.
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
            # Recomputed the same way a fresh turn computes it
            # (`design_assistant.turn_stance`)  -  otherwise a reload blanks the line
            # the UI keeps this for, until the next turn is sent.
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
        """
        Accept, reject, or reopen ("proposed") a design move (FR-CONV-1.2)  -  undo is
        just deciding "proposed" again.
        """
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

        # It did not, and the omission hid behind three surfaces that each looked right
        # on their own: the move card showed its citations, the compiled provenance
        # recorded them, and the library assistant answered questions about them (it
        # searches a cross-study index), while the library's own list and citation graph
        # - both scoped to `study_id` - had never been told the papers existed.
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
        "/studies/{study_id}/conversation/compile",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def compile_conversation(
        study_id: str, body: CompileIn, s: Session = Depends(db)
    ) -> dict:
        """Compile the study's accepted moves into a protocol draft diff (FR-CONV-3)."""
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
        """Apply a compiled diff  -  the audited step (FR-CONV-3.3/F3.3)."""
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
        """
        The elicitation record (FR-CONV-6): the full chain from idea to specification  -
        turns, moves + grounding, compilations, approvals, and the current draft  -
        captured by construction, not reconstructed.
        """
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

    @app.get(
        "/studies/{study_id}/replication-kit",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def export_replication_kit(study_id: str, s: Session = Depends(db)):
        """The study's replication kit as a download (FR-PROT-7)."""
        proto = _resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(
                409,
                f"study {study_id!r} has no compiled protocol yet. "
                "Approve a draft in the design conversation first",
            )
        payload = dataset(study_id, "json", s)
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        with tempfile.TemporaryDirectory() as td:
            staging = Path(td)
            protocol_path = staging / "protocol.yaml"
            protocol_path.write_text(
                yaml.safe_dump(proto, sort_keys=False, default_flow_style=False)
            )
            out = staging / f"{study_id}-replication-kit.tar.gz"
            try:
                build_kit(protocol_path, payload, out, repo_root=repo_root)
            except ProtocolError as exc:
                raise HTTPException(422, str(exc)) from exc
            archive = out.read_bytes()
        return Response(
            content=archive,
            media_type="application/gzip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{study_id}-replication-kit.tar.gz"'
                ),
                "Cache-Control": "no-store",
            },
        )

    @app.get(
        "/studies/{study_id}/notebook",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def download_notebook(study_id: str, s: Session = Depends(db)):
        """The starter notebook (.ipynb) + its data dictionary as a zip."""
        import zipfile

        from analysis.dataset import Dataset
        from analysis.notebook import build_notebook, data_dictionary_markdown

        proto = _resolve_study_protocol(s, study_id)
        if proto is None:
            raise HTTPException(
                409,
                f"study {study_id!r} has no compiled protocol yet. "
                "Approve a draft in the design conversation first",
            )
        payload = dataset(study_id, "json", s)
        ds = Dataset(rows=payload["rows"], study_id=study_id)
        notebook_json = json.dumps(build_notebook(proto, ds, study_id), indent=1)
        dictionary_md = f"# {study_id}: data dictionary\n\n" + data_dictionary_markdown(
            ds
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("notebook.ipynb", notebook_json)
            zf.writestr("data-dictionary.md", dictionary_md)
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{study_id}-notebook.zip"'
                ),
                "Cache-Control": "no-store",
            },
        )


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
        """Synthetic dry run: N synthetic participants through the real ingest path."""
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
        # The half that answers the researcher's real question. `simulate_into`
        # committed through the `db` dependency, so the rows are already there
        # to analyse  -  and they are the same joined rows the dataset export
        # hands back, not a parallel construction.
        s.flush()
        outcome["plan"] = run_plan_summary(proto, _joined_rows(s), study_id)
        return outcome


    @app.post(
        "/studies/{study_id}/sessions/start",
        dependencies=[Depends(require_project_for_study("run_recipe"))],
    )
    def start_session(
        study_id: str, body: SessionStartIn, s: Session = Depends(db)
    ) -> dict:
        """Open a data-collection session under the study's protocol (FR-CONV-4)."""
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
        """Which sign-in surface the platform should render (FR-OPS-5)."""
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

        app.mount("/", StaticFiles(directory=dist), name="platform")

    return app


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
