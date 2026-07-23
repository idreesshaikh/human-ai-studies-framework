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
import secrets
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote as _urlquote

import yaml
from fastapi import Depends, FastAPI, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from protocol.lifecycle import PHASE_ORDER, current_phase, gates_by_phase
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy import text as sqltext
from sqlalchemy.orm import Session

from middleware import (
    assistant,
    auth,
    authz,
    compiler,
    design_assistant,
    enrollment,
    evolution,
    mailer,
    manifest,
    matching,
    mining,
    paper_index,
    pdf,
    semantic_scholar,
    template_registry,
)
from middleware.db import (
    CORPUS_STUDY_ID,
    IMPLICIT_PROJECT_ID,
    AggregateShape,
    Amendment,
    ApprovalEvent,
    Compilation,
    ConversationTurn,
    CuratedDataset,
    DesignMoveRow,
    EnrollmentToken,
    Event,
    Finding,
    Invitation,
    Membership,
    MetricRow,
    MiningJob,
    Paper,
    PaperEdge,
    PaperLink,
    Project,
    ProtocolDraftRow,
    RecipeRun,
    S2Cache,
    SessionOpen,
    StoredFile,
    Study,
    StudyEvolution,
    TaskCard,
    TemplateSubmission,
    UserProfile,
    get_engine,
    make_session_factory,
)
from middleware.redocs import parse_glossary, parse_srs
from middleware.settings import Settings

#: Event schema versions this service is written against; other versions are
#: stored and flagged, never rejected (FR-PROT-2 discipline). v2 = cognitive
#: leg; v3 = + behavioral telemetry leg; v4 = + agent-interaction
#: leg, snapshots, task harness; v5 = + curated-mining vocabulary
#:.
KNOWN_EVENT_SCHEMA_VERSIONS = {2, 3, 4, 5}

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
    """One recipe run recorded by the analysis runner."""

    recipeId: str
    status: str = "ok"
    answers: list[str] = Field(default_factory=list)
    note: str = ""


class TaskPatch(BaseModel):
    status: str  # open | done


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


class MatchIn(BaseModel):
    """One idea → papers match request (FR-LIT-9)."""

    query: str
    limit: int = 5


class FromMatchIn(BaseModel):
    """Accept a recommendation card into the study's paper set
    (FR-LIT-9.3). The match reason is kept - elicitation evidence."""

    ref: str
    matchReason: str = ""


class GateAttestIn(BaseModel):
    """Attest that a lifecycle gate's requirement is met (FR-DASH-2): the
    researcher confirms ethics approval / consent template / etc. is in hand,
    which writes the gate artifact and lets the study advance a phase."""

    note: str = ""
    attestedBy: str = "Researcher"
    confirmed: bool = False


class ConversationTurnIn(BaseModel):
    """One researcher turn (FR-CONV-1). The researcher supplies text only;
    the *platform* reply — its prose, design moves, and grounding — is
    generated server-side by the design assistant, so a move can only ever
    cite what the server's own tools retrieved (FR-CONV-2.2 true by
    construction, not by trusting the client)."""

    text: str
    author: str = "Researcher"


class MoveDecisionIn(BaseModel):
    """Accept/reject one design move (FR-CONV-1.2)."""

    status: str  # accepted | rejected
    decidedBy: str = "Researcher"


class CompileIn(BaseModel):
    """Compile the study's accepted moves into a draft diff (FR-CONV-3)."""

    baseYaml: str | None = None  # None = the study's current approved draft


class ApproveIn(BaseModel):
    """Apply one compiled diff (FR-CONV-3.4) - the audited step.

    Post-ethics this application is an *amendment* (FR-CONV-4.2): ``rationale``
    is the "why" the amendment record and the ethics-board delta carry."""

    compilationId: str
    approvedBy: str = "Researcher"
    rationale: str = ""


class ReapprovalIn(BaseModel):
    """Record the updated ethics artifact that lifts a consent-relevant
    amendment's session pause (FR-CONV-4.2, F4.1)."""

    artifact: str = ""


class SessionStartIn(BaseModel):
    """Open a data-collection session under the study's current protocol
    revision (FR-CONV-4, F4.2/F4.3). The gate refuses *new* sessions while a
    consent-relevant amendment awaits re-approval; an already-open session
    resumes untouched (NFR-1)."""

    sessionId: str


class FeedbackIn(BaseModel):
    """Mark a conversation turn as platform feedback (FR-CONV-5.1). ``note`` is
    the researcher's optional words; ``kind`` buckets the feedback (a UX
    defect, a template gap, ...) — detection may *offer* it, marking confirms."""

    note: str = ""
    kind: str = "unclassified"


class TemplateInstantiateIn(BaseModel):
    """Instantiate a template with parameter values (FR-TPL-1.4)."""

    parameters: dict = Field(default_factory=dict)
    studyId: str = ""
    title: str = ""


class TemplateSubmitIn(BaseModel):
    """Submit a third-party template for registry review (FR-TPL-5)."""

    name: str = Field(min_length=1, max_length=200)
    templateYaml: str = Field(min_length=1)


class TemplateDecisionIn(BaseModel):
    """Owner decision on a template submission (FR-TPL-5)."""

    status: str = Field(pattern=r"^(approved|rejected)$")
    reviewComment: str = ""


class MintTokensIn(BaseModel):
    """Mint a batch of enrollment (pairing) tokens for a study (FR-INST-20)."""

    count: int = 1
    grain: str = "participant"  # 'participant' | 'session'


class RedeemIn(BaseModel):
    """The raw token half of a connection string, POSTed by the extension
    to pair a live-capture session (FR-INST-20/21)."""

    token: str


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
    session_factory = make_session_factory(settings.db_url)

    protocol_doc = None
    if settings.protocol_path is not None:
        from protocol.loader import load_protocol

        protocol_doc = load_protocol(settings.protocol_path)
    check = _ProtocolCheck(protocol_doc)

    def _resolve_study_protocol(s: Session, study_id: str) -> dict | None:
        """Resolve a study's protocol: the approved YAML snapshot wins
        (post-ethics, FR-CONV-4); the boot protocol is the single-facilitator
        fallback for a study never taken through the design conversation.

        Named with a leading underscore (unlike the brief's ``study_protocol``)
        because ``create_app`` already binds that name to the
        ``GET /studies/{study_id}/protocol`` route handler (~line 774) — reusing
        it would have the later ``def`` silently shadow this helper for every
        caller below it, including this task's own routes. Discovered via the
        TDD RED step (a same-named-argument ``TypeError`` at the mint route)."""
        import yaml

        from middleware.db import StudyEvolution

        evo = s.get(StudyEvolution, study_id)
        if evo is not None and evo.approved_yaml:
            return yaml.safe_load(evo.approved_yaml)
        if protocol_doc is not None and protocol_doc["study"]["id"] == study_id:
            return protocol_doc
        if settings.dev_mode:
            # Developer mode: a compiled draft that hasn't been ethics-frozen is
            # still enough to exercise the flow (e.g. minting). Production never
            # takes this branch, so the approved snapshot stays the source of
            # record there.
            from middleware.db import ProtocolDraftRow

            draft = s.get(ProtocolDraftRow, study_id)
            if draft is not None and draft.yaml:
                return yaml.safe_load(draft.yaml)
        return None

    def _resolve_study_protocol_for_lifecycle(s: Session, study_id: str) -> dict | None:
        """Resolve a study's protocol for the lifecycle board and its
        siblings (status, findings scan): unlike ``_resolve_study_protocol``
        - which gates the pre-ethics draft behind ``dev_mode`` for the
        enrollment route's hard science invariant (no minting before ethics
        approval) - the lifecycle must show a study's compiled-and-approved
        draft even before ethics approval, since attesting the ``design``
        phase's gate is how a study *reaches* the ``ethics`` phase, not
        something that follows it.
        """
        proto = _resolve_study_protocol(s, study_id)
        if proto is not None:
            return proto
        import yaml

        from middleware.db import ProtocolDraftRow

        draft = s.get(ProtocolDraftRow, study_id)
        if draft is not None and draft.yaml:
            return yaml.safe_load(draft.yaml)
        return None

    # Reify the loaded protocol's study into the studies table: the
    # project choke point resolves study_id -> studies.project_id -> membership,
    # so the protocol's study needs a row. Owned by the implicit project
    # (auto-created by _migrate_projects at boot). Idempotent: a re-run only
    # backfills project_id on a pre--style row. No protocol loaded = no
    # study row; the v1 /studies/{id} routes still 404 as before on unknown ids.
    if check.study_id is not None:
        with session_factory() as s:
            _ensure_study_row(s, check.study_id, protocol_doc)
            s.commit()

    app = FastAPI(title="Study ingestion middleware", version="0.1.0")

    # Platform manifest for agent-friendliness (FR-AGF-1). The resolved auth
    # mode is passed so the manifest reports what this deployment enforces.
    manifest.setup_manifest_route(app, auth_mode=auth.resolve_mode(settings))

    # Cross-origin access is opt-in per origin (FR-OPS-6): unset = the
    # same-origin-only default; set = a platform hosted on a separate
    # origin calling this middleware.
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
                404,
                f"unknown study {study_id!r}; this deployment serves "
                f"{check.study_id!r}",
            )

    # Sign-in gate on the platform-facing endpoints (FR-OPS-5): pluggable
    # provider (none/token/clerk), built once at startup so misconfiguration
    # fails loudly here, not on first request. Ingest stays open: sensors
    # are fire-and-forget (NFR-1) on a local-first deployment (NFR-5).
    verify_view_auth = auth.verifier_from_settings(settings)

    def view_auth(authorization: str = Header(default="")) -> None:
        verify_view_auth(authorization)

    # The project-scoping choke point (FR-PLAT-1/2, Slice A): one
    # seam, built once. ``require_project`` / ``require_project_for_study``
    # are dependency *factories* - a route names its capability and the
    # factory returns a dependency that resolves membership or 403/404. The
    # matrix lives in ``authz.CAPABILITIES`` (data), not in prose. Routes
    # read these as ``Depends(authz_dep("require_project")("view"))``.
    authz_dep = authz.build_authz(
        session_factory, verify_view_auth, loaded_study_id=lambda: check.study_id
    )
    require_project = authz_dep["require_project"]
    require_project_for_study = authz_dep["require_project_for_study"]
    resolve_identity = authz_dep["resolve_identity"]

    def require_protocol() -> dict:
        if protocol_doc is None:
            raise HTTPException(404, "no protocol loaded; set MIDDLEWARE_PROTOCOL")
        return protocol_doc

    # ---------------------------------------------------------------- ingest

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
        for e in events:
            pid, cond = e.participantId, e.condition
            extra_flags: list[str] = []
            if cred_row is not None:
                if (e.participantId and e.participantId != cred_row.participant_id) or (
                    e.condition and e.condition != cred_row.condition
                ):
                    extra_flags.append("credential-mismatch")
                pid, cond = cred_row.participant_id, cred_row.condition  # server-stamp
            elif bearer_present:
                extra_flags.append("unauthenticated")  # bearer sent, none valid
            flags = check.flags_for(pid, cond, e.v) + extra_flags
            flagged += bool(flags)
            rows.append(
                dict(
                    session_id=e.sessionId,
                    source=e.source or batch_source or DEFAULT_SOURCE,
                    seq=e.seq,
                    participant_id=pid,
                    condition=cond,
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
            engine = get_engine()
            if engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as _pg_insert
                stmt = _pg_insert(Event).values(rows).on_conflict_do_nothing()
            else:
                from sqlalchemy.dialects.sqlite import insert as _sq_insert
                stmt = _sq_insert(Event).values(rows).on_conflict_do_nothing(
                    index_elements=["session_id", "source", "seq"]
                )
            inserted = len(s.execute(stmt.returning(Event.id)).fetchall())
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
            _row_vals = dict(
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
            _engine = get_engine()
            if _engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as _pg_insert
                stmt = (
                    _pg_insert(MetricRow)
                    .values([_row_vals])
                    .on_conflict_do_nothing()
                )
            else:
                from sqlalchemy.dialects.sqlite import insert as _sq_insert
                stmt = _sq_insert(MetricRow).values([_row_vals]).on_conflict_do_nothing(
                    index_elements=["row_hash"]
                )
            inserted += len(s.execute(stmt.returning(MetricRow.id)).fetchall())
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

    # ----------------------------------------------------------------- query

    @app.get(
        "/studies/{study_id}/sessions",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def list_sessions(study_id: str, s: Session = Depends(db)) -> list[dict]:
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
        # every stream out.
        summaries = {src: _gap_summary(sorted(seqs)) for src, seqs in by_source.items()}
        primary = DEFAULT_SOURCE if DEFAULT_SOURCE in summaries else min(summaries)
        return {
            "sessionId": session_id,
            **summaries[primary],
            "sources": [{"source": src, **summaries[src]} for src in sorted(summaries)],
        }

    @app.get(
        "/studies/{study_id}/dataset",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def dataset(study_id: str, format: str = "json", s: Session = Depends(db)):
        """The joined one-timeline export all legs share (FR-ING-4).

        Every row: source, ts, sessionId, participantId, condition, type,
        payload - sorted by (ts, source, seq). JSON by default, ``?format=csv``
        for the flat file (payload JSON-encoded in one column).
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

    # ------------------------------------- platform support

    def _stored_files(s: Session, study_id: str) -> dict[str, StoredFile]:
        """Uploaded artifacts by filename, scoped to one study - the
        lifecycle's evidence set.

        Later uploads win on filename collision (re-upload supersedes).
        """
        files = s.scalars(
            select(StoredFile)
            .where(StoredFile.study_id == study_id)
            .order_by(StoredFile.id)
        )
        return {f.filename: f for f in files}

    def _lifecycle_doc(s: Session, study_id: str) -> dict:
        """The computed lifecycle (FR-DASH-2): the current phase is derived
        from uploaded gate artifacts via the lifecycle engine, never hand-set.
        """
        proto = _resolve_study_protocol_for_lifecycle(s, study_id)
        if proto is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")
        files = _stored_files(s, study_id)
        # The engine's gate view, not the raw declarations: a gateless phase
        # carries its implicit completion attestation (FR-PROT-10), so the
        # board shows the manual advance instead of silently ticking past.
        guarded = gates_by_phase(proto)
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
                for g in guarded.get(name, [])
            ]
            phases.append(
                {
                    "name": name,
                    "status": (
                        "complete"
                        if i < cur_i
                        else "current"
                        if i == cur_i
                        else "upcoming"
                    ),
                    "gates": gates,
                }
            )
        return {"currentPhase": current, "phases": phases}

    @app.get(
        "/studies/{study_id}/protocol",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def study_protocol(study_id: str, s: Session = Depends(db)) -> dict:
        """Protocol summary for the overview card (FR-DASH-1) and the
        traceability chips (FR-DASH-6): RQ -> planned recipes comes verbatim
        from the protocol's analysis plan."""

        proto = _resolve_study_protocol_for_lifecycle(s, study_id)
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
        }

    @app.get(
        "/studies/{study_id}/lifecycle",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def study_lifecycle(study_id: str, s: Session = Depends(db)) -> dict:

        return _lifecycle_doc(s, study_id)

    @app.post(
        "/studies/{study_id}/lifecycle/gates/{artifact}/attest",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def attest_gate(
        study_id: str, artifact: str, body: GateAttestIn, s: Session = Depends(db)
    ) -> dict:
        """Satisfy a lifecycle gate by attestation (FR-DASH-2): the researcher
        confirms a requirement is met - ethics approval obtained, consent
        template finalized - which writes the gate artifact so the study can
        advance. Only a gate the protocol declares for the *current* phase can
        be attested, so progression stays one gated step at a time and never
        skips ahead. Attestation requires explicit confirmation (the 'agree'
        step), and the note + who attested are kept as evidence."""
        if not body.confirmed:
            raise HTTPException(400, "attestation needs explicit confirmation")
        proto = _resolve_study_protocol_for_lifecycle(s, study_id)
        if proto is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")
        current = current_phase(proto, set(_stored_files(s, study_id)))
        # The engine's gate view includes the implicit completion attestation
        # of a gateless phase (FR-PROT-10) — the manual advance is attested
        # through the same one-gated-step-at-a-time door as declared gates.
        current_gates = gates_by_phase(proto).get(current, [])
        if artifact not in current_gates:
            raise HTTPException(
                409,
                f"{artifact!r} is not an open gate of the current phase {current!r}",
            )
        _write_gate_artifact(
            s,
            artifact,
            {
                "attestation": f"{artifact} satisfied by researcher attestation",
                "attestedBy": body.attestedBy,
                "note": body.note,
                "at": now(),
            },
            study_id,
        )
        s.commit()
        return _lifecycle_doc(s, study_id)

    @app.get(
        "/studies/{study_id}/status",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def study_status(study_id: str, s: Session = Depends(db)) -> dict:
        """One factual status document (FR-DASH-7).

        The task board is a *projection* of this document: the platform
        derives cards from it and they clear themselves when the fact that
        spawned them disappears. Facts only - no card state lives here.
        """

        proto = _resolve_study_protocol_for_lifecycle(s, study_id)
        if proto is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")

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
            "lifecycle": _lifecycle_doc(s, study_id),
            "conditions": conditions,
            "plannedParticipants": int(participants.get("planned", 0)),
            "plannedSessionsPerParticipant": len(conditions) if within else 1,
            "sessions": sorted(sessions.values(), key=lambda e: e["sessionId"]),
            "researchQuestions": [
                {
                    "id": rq["id"],
                    "recipes": recipes_by_rq.get(rq["id"], []),
                    # Recorded by `analysis run`; planned recipes
                    # without a recorded ok run read as un-run.
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
        """Sessions with ingests inside the window (FR-DASH-3), with per-
        bucket receive counts for the event-rate sparkline. Keyed on
        ``received_at`` (when the middleware saw the row), not event ``ts``:
        liveness is about ingestion, and replayed sessions show up too."""

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
                "participantId": f.participant_id,
                "uploadedAt": f.uploaded_at,
            }
            for f in s.scalars(select(StoredFile).order_by(StoredFile.id))
        ]

    # ---------------------------------------------------------------- papers

    @app.get(
        "/studies/{study_id}/papers",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def list_papers(study_id: str, s: Session = Depends(db)) -> list[dict]:
        """The study's paper set. ``inProtocolLiterature`` marks papers the
        protocol's ``literature:`` list already cites - links join on the
        canonical paperRef (FR-LIT-3 builds on this in)."""

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

    # --------------------------------------- paper ingest + graph

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
        _paper_vals = dict(
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
        """Seed a newly-ingested paper's protocol links from the protocol's
        ``literature:`` list (FR-LIT-3), idempotently."""
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

    def harvest_edges(s: Session, study_id: str, paper_ref: str) -> int:
        """Fetch and store the paper's graph neighbourhood (FR-LIT-2). Best
        effort - S2 failure leaves any existing edges intact."""
        try:
            edges = semantic_scholar.fetch_edges(paper_ref, fetch=cached_fetch(s))
        except semantic_scholar.SemanticScholarError as exc:
            log_finding(
                s,
                "papers/graph",
                "FR-LIT-2",
                f"edge harvest failed for {paper_ref}: {exc}",
                {},
            )
            return 0
        n = 0
        _engine = get_engine()
        for kind, neighbours in edges.items():
            for nb in neighbours:
                dst = nb["paperRef"]
                if dst == paper_ref:
                    continue
                _edge_vals = dict(
                    study_id=study_id,
                    src_ref=paper_ref,
                    dst_ref=dst,
                    kind=kind,
                    dst_title=nb.get("title", ""),
                    dst_year=nb.get("year"),
                    dst_citation_count=nb.get("citationCount"),
                )
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

    @app.post(
        "/studies/{study_id}/papers",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def ingest_paper(
        study_id: str, body: PaperIngestIn, s: Session = Depends(db)
    ) -> dict:
        """Ingest one paper by arXiv id / DOI (FR-LIT-1 id path): fetch S2
        metadata, index it, and harvest its graph neighbourhood (FR-LIT-2).
        PDF upload is the sibling ``/papers/upload`` route."""

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
        return {
            "paperRef": record["paperRef"],
            "title": record["title"],
            "edges": edges,
        }

    @app.post(
        "/studies/{study_id}/papers/upload",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    async def ingest_paper_pdf(
        study_id: str, file: UploadFile, s: Session = Depends(db)
    ) -> dict:
        """Ingest a paper from a PDF (FR-LIT-1 PDF path): extract text + a
        title guess locally (D21), then enrich by DOI/title via S2 when
        possible. Falls back to metadata-from-PDF if S2 can't resolve it."""

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
        "/studies/{study_id}/papers/{paper_ref:path}", dependencies=[Depends(view_auth)]
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
        """The related-papers graph (FR-LIT-2): ingested nodes (solid) plus
        suggested stub nodes (hollow, un-ingested), and the typed edges
        between them - the ResearchRabbit-style view's data."""

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
        for e in edges:
            if e.dst_ref not in nodes:
                nodes[e.dst_ref] = {
                    "paperRef": e.dst_ref,
                    "title": e.dst_title,
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

    # ------------------------------------------------ FR-LIT-9 matching

    @app.post(
        "/studies/{study_id}/papers/match",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def match_study_papers(
        study_id: str, body: MatchIn, s: Session = Depends(db)
    ) -> dict:
        """Idea → paper recommendations via the match ladder (FR-LIT-9).
        The LLM rerank rung runs only when a key is configured; without one
        the same request answers from FTS + the seed graph (F9.2)."""
        recommendations = matching.match_papers(
            s,
            body.query,
            study_id=study_id,
            limit=body.limit,
            use_llm=assistant.configured(),
        )
        return {"studyId": study_id, "recommendations": recommendations}

    @app.post(
        "/studies/{study_id}/papers/from-match",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def add_paper_from_match(
        study_id: str, body: FromMatchIn, s: Session = Depends(db)
    ) -> dict:
        """One-click ingest of a recommendation card (FR-LIT-9.3): the
        corpus row joins the study's paper set with ``addedVia=match`` and
        the match reason kept - it is elicitation evidence. The paper is
        immediately retrievable in the next assistant exchange (F9.3): its
        FTS entries already exist at the shared index."""
        corpus_row = s.execute(
            select(Paper).where(
                Paper.study_id == CORPUS_STUDY_ID, Paper.paper_ref == body.ref
            )
        ).scalar_one_or_none()
        if corpus_row is None:
            raise HTTPException(404, f"paper {body.ref!r} is not in the corpus")
        _match_vals = dict(
            study_id=study_id,
            paper_ref=corpus_row.paper_ref,
            title=corpus_row.title,
            authors=corpus_row.authors,
            year=corpus_row.year,
            venue=corpus_row.venue,
            abstract=corpus_row.abstract,
            doi=corpus_row.doi,
            arxiv_id=corpus_row.arxiv_id,
            url=corpus_row.url,
            item_type=corpus_row.item_type,
            source="match",
            s2_id=corpus_row.s2_id,
            citation_count=corpus_row.citation_count,
            tier=corpus_row.tier,
            added_via="match",
            match_reason=body.matchReason,
            added_at=now(),
        )
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
        return {
            "studyId": study_id,
            "paperRef": corpus_row.paper_ref,
            "title": corpus_row.title,
            "tier": corpus_row.tier,
            "addedVia": "match",
        }

    @app.get(
        "/studies/{study_id}/papers/{paper_ref:path}/links",
        dependencies=[Depends(view_auth)],
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
        dependencies=[Depends(view_auth)],
    )
    def set_paper_links(
        study_id: str, paper_ref: str, body: PaperLinksIn, s: Session = Depends(db)
    ) -> dict:
        """Replace a paper's protocol-element links (FR-LIT-3). Targets use
        the protocol's justification vocabulary (``RQ-P2``,
        ``metric:parameter_count``, ...)."""

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
        "/studies/{study_id}/assistant/config",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def assistant_config(study_id: str) -> dict:
        """Whether the assistant is configured and which Mistral model tiers
        the platform may pick (D32 rev 2). Never exposes the key itself."""

        ready = assistant.configured()
        return {
            "configured": ready,
            "models": list(assistant.MISTRAL_MODELS) if ready else [],
            "defaultModel": assistant.MISTRAL_MODEL,
        }

    @app.get("/assistant/models")
    def assistant_models() -> dict:
        """The catalog of assistant model tiers the platform may pick
        (D32 rev 2). Unauthenticated — it names tiers, never the key. Used by
        the profile preference "default assistant model" (FR-OPS-7)."""

        return {
            "configured": assistant.configured(),
            "models": list(assistant.MISTRAL_MODELS),
            "defaultModel": assistant.MISTRAL_MODEL,
        }

    @app.post(
        "/studies/{study_id}/assistant",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def knowledge_assistant(
        study_id: str, body: AssistantIn, s: Session = Depends(db)
    ) -> dict:
        """Grounded Q&A over papers + protocol + dataset *aggregates*
        (FR-LIT-4). FR-ETH-4 is enforced in ``assistant.build_tools`` - no
        tool can return a row-level participant event. Absent an API key the
        endpoint degrades gracefully (503); everything else stays offline."""

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
                at=now(),
                source=finding.source,
                kind=finding.kind,
                requirement_id=finding.requirementId,
                message=finding.message,
                context=finding.context,
                status=finding.status,
            )
        )
        return {"ok": True}

    @app.get("/findings", dependencies=[Depends(view_auth)])
    def list_findings(s: Session = Depends(db)) -> list[dict]:
        rows = s.scalars(select(Finding).order_by(Finding.id))
        return [_finding_json(f) for f in rows]

    @app.post(
        "/studies/{study_id}/findings/scan",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def scan_findings(study_id: str, s: Session = Depends(db)) -> dict:
        """Auto-write the read-detectable operational findings (FR-META-1):
        per-producer seq gaps (FR-ING-3) and unsatisfied current-phase gate
        blocks (FR-PROT-3). Idempotent - each defect is logged once (keyed on
        ``(kind, context)``), so re-scanning reflects the current state
        without duplicating rows."""

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
            log_finding(
                s,
                source="findings/scan",
                requirement_id=req,
                message=message,
                context=context,
                kind=kind,
            )
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
                    "seq-gap",
                    "FR-ING-3",
                    f"{sid} ({src}): {len(summary['gaps'])} seq gap(s), "
                    f"{missing} event(s) missing",
                    {"session": sid, "source": src},
                )

        # Gate blocks: the current phase's unsatisfied gates (including a
        # gateless phase's implicit completion attestation, FR-PROT-10).
        proto = _resolve_study_protocol_for_lifecycle(s, study_id)
        if proto is not None:
            files = _stored_files(s, study_id)
            current = current_phase(proto, set(files))
            for gate in gates_by_phase(proto).get(current, []):
                if gate not in files:
                    emit(
                        "gate-block",
                        "FR-PROT-3",
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
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "note": t.note,
                "createdAt": t.created_at,
            }
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
        """The SRS, parsed live from ``srs.md`` - platform tooltip text
        comes from the document of record and cannot drift."""
        return parse_srs(settings.requirements_dir / "srs.md")

    @app.get("/glossary", dependencies=[Depends(view_auth)])
    def list_glossary() -> list[dict]:
        """The project glossary, parsed live from ``glossary.md``."""
        return parse_glossary(settings.requirements_dir / "glossary.md")

    # ------------------------- vocabulary endpoints for agents (FR-AGF-1)
    # Unauthenticated endpoints for agent consumption - same data as above
    # but without auth requirements so agents can discover the platform.

    @app.get("/vocabulary/glossary")
    def agent_glossary() -> list[dict]:
        """The project glossary for agent consumption (FR-AGF-1).

        Unauthenticated. Same data as /glossary but without auth.
        """
        return parse_glossary(settings.requirements_dir / "glossary.md")

    @app.get("/vocabulary/requirements")
    def agent_requirements() -> list[dict]:
        """The SRS for agent consumption (FR-AGF-1).

        Unauthenticated. Same data as /requirements but without auth.
        """
        return parse_srs(settings.requirements_dir / "srs.md")

    # ------------------------- schema endpoints for agents (FR-AGF-1)
    # Unauthenticated endpoints serving JSON schemas for agent discovery.

    @app.get("/schemas/event")
    def event_schema() -> dict:
        """Event schema for agent consumption (FR-AGF-1).

        Unauthenticated. Returns the current event schema that the
        middleware accepts ( StudyEvent from extension/types.ts ).
        """
        # Serve a generated schema that represents the StudyEvent interface
        # from extension/src/core/types.ts
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
                        "('cognitive-overlay') if not provided."
                    ),
                    "type": "string",
                    "default": "cognitive-overlay",
                },
            },
        }

    @app.get("/schemas/protocol")
    def protocol_schema() -> dict:
        """Protocol schema for agent consumption (FR-AGF-1).

        Unauthenticated. Serves the study protocol schema from the protocol package.
        """
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
        # Fallback to minimal schema if file not found
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
        """Template schema for agent consumption (FR-AGF-1).

        Unauthenticated. Serves the template schema from the templates package.
        """
        template_schema_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "templates"
            / "schemas"
            / "template.schema.json"
        )
        if template_schema_path.exists():
            import json

            return json.loads(template_schema_path.read_text())
        # Fallback to minimal schema if file not found
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

    # ------------------------- templates endpoint for agents (FR-AGF-1)

    @app.get("/templates")
    def template_index() -> dict:
        """Template registry index for agent consumption (FR-AGF-1).

        Unauthenticated. Returns metadata about available templates.
        """
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
                except Exception:
                    # Skip files that can't be parsed
                    continue

        return {"templates": templates, "count": len(templates), "generatedAt": now()}

    # ------------------------- corpus endpoint for agents (FR-AGF-1)

    @app.get("/papers/index")
    def corpus_index() -> dict:
        """Corpus index for agent consumption (FR-AGF-1).

        Unauthenticated. Returns metadata about the paper corpus.
        """
        repo = Path(__file__).resolve().parent.parent.parent.parent
        corpus_index_path = repo / "docs" / "papers" / "corpus-index.json"

        if corpus_index_path.exists():
            import json

            return json.loads(corpus_index_path.read_text())

        # Fallback if corpus-index.json doesn't exist
        return {
            "generatedAt": "",
            "pipeline": "",
            "tierA": {"count": 0, "arxivResolvable": 0, "source": ""},
            "tierB": [],
            "scoringVersion": 0,
        }

    # -------------------------------------------------- project routes
    # The platform API surface (FR-PLAT-1..5). Every project-scoped route
    # depends on the ``require_project(capability)`` choke point; the matrix
    # lives in ``authz.CAPABILITIES`` (data), tests iterate it (F2.1/F2.2).

    @app.post("/projects", dependencies=[Depends(resolve_identity)])
    def create_project(
        body: dict,
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        """Create a new project (FR-PLAT-1). Any signed-in identity may
        create a project; the creator becomes owner."""
        name = str(body.get("name", "")).strip()
        if not name:
            raise HTTPException(400, "name is required")
        slug = str(body.get("slug", "")).strip()
        if not slug:
            # Auto-slug from name: lowercase, hyphens, max 50 chars.
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50]
        if not slug:
            slug = secrets.token_hex(4)
        existing = s.scalar(select(Project).where(Project.slug == slug))
        if existing is not None:
            raise HTTPException(409, f"slug {slug!r} is taken")
        pid = secrets.token_hex(8)
        s.add(
            Project(
                id=pid, name=name, slug=slug, created_by=identity.sub, created_at=now()
            )
        )
        # Flush the project before adding its membership row: Project and
        # Membership have no ORM relationship() between them (only a raw FK
        # column), and SQLAlchemy's flush-time insert ordering leans on that
        # relationship to sequence cross-table inserts correctly - without
        # it, the two pending inserts can be emitted in whatever order the
        # unit-of-work happens to iterate them, and Membership going first
        # trips its own foreign-key constraint. Flushing the parent alone
        # first makes the dependency real regardless of iteration order.
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
        return {"id": pid, "slug": slug, "name": name}

    @app.get("/projects", dependencies=[Depends(resolve_identity)])
    def list_projects(
        identity: auth.Identity = Depends(resolve_identity), s: Session = Depends(db)
    ) -> list[dict]:
        """My project memberships (FR-PLAT-2). Returns projects where the
        caller has any membership, with their role on each."""
        rows = s.execute(
            select(Project, Membership.role)
            .join(Membership, Membership.project_id == Project.id)
            .where(Membership.identity_sub == identity.sub)
            .order_by(Project.created_at.desc())
        ).all()
        return [
            {
                "id": p.id,
                "slug": p.slug,
                "name": p.name,
                "role": role,
                "createdAt": p.created_at,
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
            {"id": st.id, "phase": st.phase}
            for st in s.scalars(select(Study).where(Study.project_id == proj.id))
        ]
        member_rows = list(
            s.scalars(select(Membership).where(Membership.project_id == proj.id))
        )
        # Membership only ever stores the bare identity_sub (a Clerk user id
        # for hosted deployments) - resolve a human label from the
        # invitation that brought each member in, where one exists, so the
        # UI never has to show a raw "user_..." string as someone's name.
        invited_by_ids = [m.invited_by for m in member_rows if m.invited_by]
        invite_emails = {
            inv.id: inv.email
            for inv in (
                s.scalars(select(Invitation).where(Invitation.id.in_(invited_by_ids)))
                if invited_by_ids
                else []
            )
        }
        members = [
            {
                "identitySub": m.identity_sub,
                "role": m.role,
                "email": invite_emails.get(m.invited_by) if m.invited_by else None,
            }
            for m in member_rows
        ]
        invitations = [
            {
                "id": inv.id,
                "email": inv.email,
                "role": inv.role,
                "expiresAt": inv.expires_at,
                "acceptedAt": inv.accepted_at,
            }
            for inv in s.scalars(
                select(Invitation).where(
                    Invitation.project_id == proj.id, Invitation.accepted_at.is_(None)
                )
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
        """Start a new study in this project (FR-PLAT-1 continued): the
        design conversation needs a study row to attach its moves/drafts to
        before it can run — this is that row, empty and pre-design, ready
        for the researcher to talk it into existence. Any project member
        with at least the researcher role may start one."""
        proj = s.scalar(select(Project).where(Project.slug == slug))
        if proj is None:
            raise HTTPException(404, "project not found")
        name = str(body.get("name", "")).strip()
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] if name else ""
        if not base:
            base = "study"
        study_id = base
        suffix = 1
        while s.scalar(select(Study).where(Study.id == study_id)) is not None:
            suffix += 1
            study_id = f"{base}-{suffix}"
        s.add(
            Study(
                id=study_id,
                project_id=proj.id,
                protocol_version="",
                phase="design",
                data_path="",
            )
        )
        s.flush()
        return {"id": study_id, "phase": "design"}

    #: Every table that scopes rows by ``study_id`` — deleting a study removes
    #: its row plus all of these, so nothing is orphaned. The corpus study is
    #: never a target (it isn't a project study).
    _STUDY_SCOPED = (
        StoredFile,
        Paper,
        PaperEdge,
        PaperLink,
        RecipeRun,
        EnrollmentToken,
        MiningJob,
        CuratedDataset,
        ConversationTurn,
        DesignMoveRow,
        Compilation,
        ApprovalEvent,
        ProtocolDraftRow,
        StudyEvolution,
        Amendment,
        SessionOpen,
    )

    @app.delete(
        "/studies/{study_id}",
        dependencies=[Depends(require_project_for_study("delete"))],
    )
    def delete_study(study_id: str, s: Session = Depends(db)) -> dict:
        """Delete a study and everything scoped to it (FR-PLAT-1): its
        conversation, design moves, drafts, papers, enrollment, mining, and
        evolution records. Owner-only. Idempotent-ish: a missing study 404s."""
        study = s.get(Study, study_id)
        if study is None:
            raise HTTPException(404, "study not found")
        for model in _STUDY_SCOPED:
            s.execute(model.__table__.delete().where(model.study_id == study_id))
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
        if confirm != proj.slug:
            raise HTTPException(
                400, f"type the project slug ({proj.slug!r}) to confirm deletion"
            )
        # Delete memberships + invitations cascade via FK (ondelete);
        # studies, papers etc. are scoped via the choke point, not cascaded.
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
        # Last owner refuses (fr-plat.md §2).
        if m.role == "owner":
            owner_count = s.scalar(
                select(func.count())
                .select_from(Membership)
                .where(Membership.project_id == proj.id, Membership.role == "owner")
            )
            if owner_count <= 1:
                raise HTTPException(
                    409, "can't remove the last owner — transfer ownership first"
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
        email = str(body.get("email", "")).strip()
        role = str(body.get("role", "")).strip()
        if not email:
            raise HTTPException(400, "email is required")
        if role not in authz.ROLES:
            raise HTTPException(400, f"role must be one of: {list(authz.ROLES)}")
        # A member can invite peers (D40), but only an owner can mint an owner
        # invite — otherwise invite_member would be a backdoor to ownership.
        if role == authz.Role.OWNER.value:
            caller = s.scalar(
                select(Membership).where(
                    Membership.project_id == proj.id,
                    Membership.identity_sub == identity.sub,
                )
            )
            if caller is None or not authz.has_role(caller.role, "manage_members"):
                raise HTTPException(403, "only an owner can invite another owner")
        # Expiry: 7 days from now (roadmap says expiring; duration is mine).
        from datetime import timedelta as td

        expires = clock() + td(days=7)
        token = secrets.token_urlsafe(32)
        inv_id = secrets.token_hex(8)
        s.add(
            Invitation(
                id=inv_id,
                project_id=proj.id,
                email=email,
                role=role,
                token=token,
                expires_at=expires.isoformat(timespec="milliseconds"),
            )
        )
        s.flush()
        # Build the accept URL (the frontend base path is implicit).
        url = f"/invitations/{token}"
        # Best-effort email delivery (D40); the copy-link is always returned so
        # the invite works whether or not a mail key is configured.
        base = settings.public_base_url or (
            settings.cors_origins[0] if settings.cors_origins else None
        )
        emailed, email_reason = mailer.send_invitation(
            api_key=settings.resend_api_key,
            from_email=settings.invite_from_email,
            to_email=email,
            project_name=proj.name,
            role=role,
            token=token,
            base_url=base,
            inviter=identity.display_name,
        )
        return {
            "id": inv_id,
            "token": token,
            "url": url,
            "email": email,
            "role": role,
            "emailed": emailed,
            "emailReason": email_reason,
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
                Invitation.accepted_at.is_(None),
            )
        )
        if inv is None:
            raise HTTPException(404, "invitation not found or already accepted")
        s.delete(inv)
        s.flush()
        return {"revoked": inv_id}

    @app.post("/invitations/{token}/accept", dependencies=[Depends(resolve_identity)])
    def accept_invitation(
        token: str,
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        """Accept an invitation (FR-PLAT-3). Signed-in; single-use;
        expiring. The invitation token links to a project + role; accepting
        creates a membership."""
        sub = identity.sub
        inv = s.scalar(
            select(Invitation).where(
                Invitation.token == token, Invitation.accepted_at.is_(None)
            )
        )
        if inv is None:
            raise HTTPException(
                404,
                "invitation not found — it may have expired, been revoked, "
                "or already accepted",
            )
        # Check expiry.
        if inv.expires_at:
            try:
                exp = datetime.fromisoformat(inv.expires_at)
                if clock() > exp:
                    raise HTTPException(
                        410,
                        "this invitation has expired — ask the project owner "
                        "to send a new one",
                    )
            except (ValueError, TypeError):
                pass  # malformed expiry — don't block on it
        # Single-use: mark accepted.
        inv.accepted_at = now()
        # Create membership (upsert — re-accepting is idempotent).
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
        else:
            existing.role = inv.role
        # Resolve the project slug for the redirect.
        proj = s.scalar(select(Project).where(Project.id == inv.project_id))
        s.flush()
        return {
            "projectSlug": proj.slug if proj else "",
            "role": inv.role,
        }

    # -------------------------------------------------- enrollment tokens

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

        from middleware.db import StudyEvolution

        evo = s.get(StudyEvolution, study_id)
        # The ethics gate is a science invariant: no enrollment before approval.
        # MIDDLEWARE_DEV_MODE relaxes it so the whole enrollment flow is testable
        # on a fresh study; it stays enforced on any real (production) instance.
        if not settings.dev_mode and (evo is None or not evo.ethics_approved_at):
            raise HTTPException(
                409,
                "Mint enrollment tokens only after the study clears its ethics "
                "gate — you cannot collect data before approval.",
            )
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
            condition = conditions[(n - 1) % len(conditions)]
            token = secrets.token_urlsafe(32)
            row = EnrollmentToken(
                id=secrets.token_hex(8),
                study_id=study_id,
                participant_id=pid,
                condition=condition,
                grain=body.grain,
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
        """List a study's active enrollment tokens (FR-INST-20). A revoked
        token drops off this list — DELETE is not a soft-hide-with-a-badge, it
        removes the token from what a researcher can hand out or pair
        against; the row itself is kept (``revoked_at`` set) for audit, just
        not surfaced here. ``unredeemed``/``paired``/``streaming`` derive
        from redemption state joined against the live session-status feed
        (FR-DASH-3): a paired participant with an event inside the window
        reads as ``streaming``. Each row also carries the capture config the
        IDE will run under (FR-DASH-10 pre-flight visibility) — the same
        ``derive_overlay_settings`` output the extension applies, so a
        researcher catches a forgotten toggle before "begin"."""
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
                        protocol, r.participant_id, r.condition
                    )
                    capture_config = {
                        "captureConfigVersion": cfg["captureConfigVersion"],
                        "enabledInstruments": enrollment.enabled_instruments(
                            cfg["settings"]
                        ),
                    }
                except ProtocolError:
                    pass  # agent-participant study, no overlay to show
            out.append(
                {
                    "id": r.id,
                    "participantId": r.participant_id,
                    "condition": r.condition,
                    "grain": r.grain,
                    "status": status,
                    "connectionString": enrollment.connection_string(base, r.token),
                    "captureConfig": capture_config,
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
        """Revoke a pairing token (researcher+, study-scoped). Keyed by study so
        the project choke point authorizes it exactly like mint/list; a token
        that isn't in this study 404s (never leak another study's tokens, and
        never let a member of one study revoke another's — the IDOR guard)."""

        row = s.get(EnrollmentToken, token_id)
        if row is None or row.study_id != study_id:
            raise HTTPException(404, "enrollment token not found")
        row.revoked_at = now()
        s.commit()
        return {"revoked": token_id}

    # ------------------------------------------------ capture-metric toggles

    @app.get(
        "/studies/{study_id}/enrollment/toggles/catalog",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def toggles_catalog(
        study_id: str, s: Session = Depends(db)
    ) -> list[dict]:
        """List togglable capture metrics for a study's protocol shape
        (FR-DASH-11). Each entry carries the current protocol-derived value,
        a label, and grounding (cited or unsourced)."""
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
    def apply_toggle(
        study_id: str, body: ToggleIn, s: Session = Depends(db)
    ) -> dict:
        """Apply one metric toggle as a protocol amendment (FR-DASH-11).

        Builds a deterministic ``reconfigure`` move, compiles it against the
        study's current approved YAML, then runs ``consent_relevance``. If
        relevant: records an ``Amendment`` row and pauses new sessions pending
        re-approval (FR-CONV-4.1). If not relevant: commits the new snapshot
        directly (F4.2). Always applies through ``compile_moves`` — never a
        side-channel mutation of ``EnrollmentToken`` or any other table.
        """
        from middleware.db import Amendment, StudyEvolution

        evo = s.get(StudyEvolution, study_id)
        if evo is None:
            raise HTTPException(404, "study not found")
        if not evo.ethics_approved_at:
            raise HTTPException(
                409,
                "Cannot toggle metrics before ethics approval — "
                "the protocol is still in design phase.",
            )

        before = yaml.safe_load(evo.approved_yaml) or {}
        if not before.get("instruments"):
            raise HTTPException(400, "protocol has no instruments block")

        # Build the deterministic reconfigure move.
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

        # Compile the move against the approved snapshot.
        draft = yaml.safe_load(yaml.safe_dump(before))
        compiler._apply_instrument_moves(draft, [toggle_move])

        # Validate the resulting draft.
        from protocol.loader import validate_protocol

        errors = validate_protocol(draft)
        if errors:
            raise HTTPException(
                422, f"toggle would produce an invalid protocol: {'; '.join(errors)}"
            )

        # Check consent relevance.
        relevant, reasons = evolution.consent_relevance(before, draft)
        changes = evolution.change_summary(before, draft)
        new_yaml = yaml.safe_dump(draft, default_flow_style=False)

        if relevant:
            # Record as a formal amendment (consent-relevant).
            from_v = evo.current_version
            to_v = from_v + 1
            amend = Amendment(
                id=secrets.token_hex(8),
                study_id=study_id,
                compilation_id="",
                from_version=from_v,
                to_version=to_v,
                summary=changes[0] if changes else "metric toggle",
                changes=changes,
                rationale=body.rationale,
                grounding=[],
                consent_relevant=1,
                consent_reasons=reasons,
                approved_by="",
                role="",
                created_at=now(),
            )
            s.add(amend)
            evo.current_version = to_v
            evo.approved_yaml = new_yaml
            evo.pending_reapproval = amend.id
            evo.updated_at = now()
            s.commit()
            return {
                "applied": True,
                "requiresReapproval": True,
                "amendmentId": amend.id,
                "fromVersion": from_v,
                "toVersion": to_v,
                "consentReasons": reasons,
            }
        else:
            # Non-relevant: commit directly (F4.2).
            evo.approved_yaml = new_yaml
            evo.updated_at = now()
            s.commit()
            return {
                "applied": True,
                "requiresReapproval": False,
            }

    @app.post("/pair/redeem")
    def pair_redeem(body: RedeemIn, request: Request, s: Session = Depends(db)) -> dict:
        """Redeem a connection-string token into a live-capture session
        (FR-INST-20/21). Public — no project dependency, since the token
        itself is the credential the extension holds; a study's members
        never need to be a project member to pair from the field."""
        from middleware.db import StudyEvolution

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
                    410, "this connection link has expired — ask for a new one"
                )
        except (ValueError, TypeError):
            pass
        if row.grain == "session" and row.redeemed_at:
            raise HTTPException(
                410, "this single-use connection link has already been used"
            )
        evo = s.get(StudyEvolution, row.study_id)
        if evo is None or not evo.ethics_approved_at:
            raise HTTPException(409, "this study has not cleared its ethics gate")
        protocol = _resolve_study_protocol(s, row.study_id)
        if protocol is None:
            raise HTTPException(404, "no protocol for this study")
        if not row.credential:
            row.credential = secrets.token_urlsafe(32)
        if row.grain == "session":
            row.redeemed_at = now()
        elif not row.redeemed_at:
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
                protocol, row.participant_id, row.condition
            ),
            "consentStatement": enrollment.consent_statement(protocol, row.condition),
            "contentPolicy": enrollment.content_policy(protocol),
        }

    def resolve_credential(s: Session, authorization: str):
        """Return the ``EnrollmentToken`` for a valid Bearer session
        credential, else ``None``. Never raises — callers decide whether
        absence is fatal (reused by the ingest route, Task A7)."""

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
        except Exception:
            # A DB/infra error here (SQLite lock, I/O error, any
            # SQLAlchemy error) must never surface as a 500 that drops
            # the whole ingest batch - degrade to the already-correct
            # "bearer present but unresolved" path (Task A7, NFR-1/
            # FR-ING-6). The caller flags the row `unauthenticated` and
            # stores it anyway.
            return None

    @app.get("/studies/{study_id}/capture-config")
    def get_capture_config(
        study_id: str,
        authorization: str = Header(default=""),
        s: Session = Depends(db),
    ) -> dict:
        """Session-boundary re-pull of the capture config (FR-INST-21): the
        extension re-fetches this at the start of each session so a protocol
        amendment lands without re-pairing. Gated on the session credential
        minted by ``/pair/redeem`` — never the study's project membership,
        since the extension holds no project identity."""
        row = resolve_credential(s, authorization)
        if row is None or row.study_id != study_id:
            raise HTTPException(401, "a valid session credential is required")
        protocol = _resolve_study_protocol(s, study_id)
        if protocol is None:
            raise HTTPException(404, "no protocol for this study")
        return enrollment.build_capture_config(
            protocol, row.participant_id, row.condition
        )

    def _profile_prefs(s: Session, sub: str) -> dict:
        """The persisted prefs for ``sub`` (FR-OPS-7). Empty dict when no
        profile row exists yet."""
        row = s.get(UserProfile, sub)
        return dict(row.prefs) if row is not None else {}

    @app.get("/me", dependencies=[Depends(resolve_identity)])
    def get_me(identity: auth.Identity = Depends(resolve_identity)) -> dict:
        """Identity + memberships + preferences (FR-OPS-7). The single
        surface both SPAs share; a hosted Clerk identity carries its own
        persisted profile (theme, default assistant model, saved views)."""
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

    #: The preference keys the server will persist. The blob is schema-less
    #: beyond this allow-list so the UI owns per-key semantics; unknown keys
    #: are dropped rather than stored (defense against a stray client).
    KNOWN_PREF_KEYS = frozenset(
        {"theme", "defaultAssistantModel", "savedViews"}
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
        """Persist this identity's profile preferences (FR-OPS-7). Only
        :data:`KNOWN_PREF_KEYS` are stored; everything else is ignored. The
        new prefs (merged over the previous blob) are returned so the client
        can reconcile without a second round-trip."""
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

    # ------------------------------------------- curated mining
    #
    # A curated study answers "the dataset already exists" by declaring a
    # sampling frame in the protocol's ``curated:`` section, running a mining
    # job, and landing rows in the same one-timeline shape a live study
    # produces - so every recipe/report/paper mechanism works unchanged.

    #: The gate artifact whose presence opens the ``analysis`` phase for a
    #: curated study. Completing the validity-threats record writes a file
    #: with this name, so the existing lifecycle gate mechanism enforces
    #: "no record → no analysis" (FR-CUR-3 F3.2) with no lifecycle changes.
    CURATED_GATE_ARTIFACT = "validity-threats.yaml"

    def _build_fetcher():
        """The offline cassette when one is configured (demo/CI, Slice
        D); otherwise a live GitHub fetcher (token-scoped, NFR-4). The live
        path is only reachable with a token and is not exercised offline."""
        if settings.mining_cassette:
            from curated.cassette import Cassette

            return Cassette.load(settings.mining_cassette)
        from middleware.github_fetch import LiveGitHubFetcher

        return LiveGitHubFetcher(settings.github_token)

    def _mining_frame():
        """The sampling frame from the loaded protocol's ``curated:`` section,
        or an HTTPException(422) refusing to mine without one (F2.2)."""
        from curated.frame import FrameError, frame_from_protocol

        proto = require_protocol()
        try:
            return frame_from_protocol(proto)
        except FrameError as exc:
            raise HTTPException(422, str(exc)) from exc

    def _job_doc(job: MiningJob) -> dict:
        return {
            "id": job.id,
            "studyId": job.study_id,
            "source": job.source,
            "state": job.state,
            "cursor": job.cursor,
            "coverage": job.coverage,
            "firedHeuristics": job.fired_heuristics,
            "statusMessage": job.status_message,
            "createdAt": job.created_at,
            "updatedAt": job.updated_at,
        }

    def _run_and_persist(job_id: str, resume: bool) -> None:
        """Run (or resume) a job to a gate, ingesting events and persisting
        each checkpoint. Synchronous against the configured fetcher - instant
        on a cassette; a live mine would wrap this in a background task."""
        from curated.registry import get_adapter

        frame = _mining_frame()
        sess = session_factory()
        try:
            job = sess.get(MiningJob, job_id)
            adapter = get_adapter(job.source, _build_fetcher(), job.salt)
            state = mining.JobState(
                state=job.state,
                cursor=job.cursor if resume else None,
                fired_heuristics=list(job.fired_heuristics or []),
            )

            def ingest(rows: list[dict]) -> None:
                if not rows:
                    return
                received = now()
                values = [
                    dict(
                        session_id=r["sessionId"],
                        source=r["source"],
                        seq=r["seq"],
                        participant_id=r["participantId"],
                        condition=r["condition"],
                        v=r["v"],
                        ts=r["ts"],
                        mono=r["mono"],
                        type=r["type"],
                        payload=r["payload"],
                        flags=[],
                        received_at=received,
                    )
                    for r in rows
                ]
                _mine_engine = get_engine()
                if _mine_engine.dialect.name == "postgresql":
                    from sqlalchemy.dialects.postgresql import insert as _pg_insert
                    stmt = _pg_insert(Event).values(values).on_conflict_do_nothing()
                else:
                    from sqlalchemy.dialects.sqlite import insert as _sq_insert
                    stmt = (
                        _sq_insert(Event)
                        .values(values)
                        .on_conflict_do_nothing(
                            index_elements=["session_id", "source", "seq"]
                        )
                    )
                sess.execute(stmt)
                sess.commit()

            def on_update(st: mining.JobState) -> None:
                job.state = st.state
                job.cursor = st.cursor
                job.coverage = {
                    "requested": st.requested,
                    "retrieved": st.retrieved,
                    "dropped": dict(st.dropped or {}),
                }
                job.fired_heuristics = list(st.fired_heuristics or [])
                job.status_message = st.status_message
                job.updated_at = now()
                sess.commit()

            # No real waiting offline: the cassette's rate-limit pauses are
            # recorded as state transitions but sleep is a no-op.
            mining.run_job(
                adapter, frame, state, ingest, on_update, sleep=lambda _s: None
            )
        finally:
            sess.close()

    @app.post(
        "/studies/{study_id}/mining-jobs",
        dependencies=[Depends(require_project_for_study("run_recipe"))],
    )
    def start_mining_job(study_id: str, s: Session = Depends(db)) -> dict:
        """Start a mining job (FR-CUR-2). Refuses without a protocol-declared
        sampling frame (F2.2). Runs against the configured source and returns
        the job at its gate; the validity-threats record is completed next."""
        _mining_frame()  # refuse early if no frame (422)
        import secrets as _secrets

        from curated.pseudonymize import new_salt

        job = MiningJob(
            id=_secrets.token_hex(8),
            study_id=study_id,
            source="github",
            state=mining.DECLARED,
            salt=new_salt(),
            coverage={},
            fired_heuristics=[],
            created_at=now(),
            updated_at=now(),
        )
        s.add(job)
        s.flush()
        job_id = job.id
        s.commit()
        _run_and_persist(job_id, resume=False)
        # The runner committed via its own session; expire ours so the
        # re-read reflects the persisted state rather than the cached row.
        s.expire_all()
        refreshed = s.get(MiningJob, job_id)
        return _job_doc(refreshed)

    @app.get(
        "/studies/{study_id}/mining-jobs/{job_id}",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def get_mining_job(study_id: str, job_id: str, s: Session = Depends(db)) -> dict:
        job = s.get(MiningJob, job_id)
        if job is None or job.study_id != study_id:
            raise HTTPException(404, "mining job not found")
        return _job_doc(job)

    @app.post(
        "/studies/{study_id}/mining-jobs/{job_id}/resume",
        dependencies=[Depends(require_project_for_study("run_recipe"))],
    )
    def resume_mining_job(study_id: str, job_id: str, s: Session = Depends(db)) -> dict:
        """Resume an interrupted job from its persisted cursor (F2.1). Never
        auto-restarts - resume is an explicit act."""
        job = s.get(MiningJob, job_id)
        if job is None or job.study_id != study_id:
            raise HTTPException(404, "mining job not found")
        if job.state in (mining.COMPLETE, mining.GATED):
            return _job_doc(job)
        _run_and_persist(job_id, resume=True)
        s.expire_all()
        return _job_doc(s.get(MiningJob, job_id))

    @app.post(
        "/studies/{study_id}/mining-jobs/{job_id}/stop",
        dependencies=[Depends(require_project_for_study("run_recipe"))],
    )
    def stop_mining_job(study_id: str, job_id: str, s: Session = Depends(db)) -> dict:
        job = s.get(MiningJob, job_id)
        if job is None or job.study_id != study_id:
            raise HTTPException(404, "mining job not found")
        if job.state not in (mining.COMPLETE, mining.GATED):
            job.state = mining.INTERRUPTED
            job.status_message = "stopped by request; resume to continue."
            job.updated_at = now()
            s.commit()
        return _job_doc(job)

    @app.get(
        "/studies/{study_id}/curated-datasets/{job_id}",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def get_curated_dataset(
        study_id: str, job_id: str, s: Session = Depends(db)
    ) -> dict:
        """The dataset + its validity-threats record. When the record is not
        yet finalized, the *generated* draft (coverage + heuristics + starter
        biases) is returned so the researcher can complete the biases."""
        job = s.get(MiningJob, job_id)
        if job is None or job.study_id != study_id:
            raise HTTPException(404, "mining job not found")
        ds = s.scalar(select(CuratedDataset).where(CuratedDataset.job_id == job_id))
        record = ds.threats_record if ds else None
        if record is None:
            frame = _mining_frame()
            state = mining.JobState(
                requested=(job.coverage or {}).get("requested", 0),
                retrieved=(job.coverage or {}).get("retrieved", 0),
                dropped=(job.coverage or {}).get("dropped", {}),
                fired_heuristics=list(job.fired_heuristics or []),
            )
            record = mining.default_threats_doc(frame, state)
        counts = dict(
            s.execute(
                select(Event.type, func.count())
                .where(Event.source == "github")
                .group_by(Event.type)
            ).all()
        )
        return {
            "jobId": job_id,
            "studyId": study_id,
            "state": job.state,
            "threatsRecord": record,
            "eventCounts": counts,
            "finalized": bool(ds and ds.threats_record),
        }

    @app.put(
        "/studies/{study_id}/curated-datasets/{job_id}/threats",
        dependencies=[Depends(require_project_for_study("run_recipe"))],
    )
    def finalize_threats_record(
        study_id: str, job_id: str, body: dict, s: Session = Depends(db)
    ) -> dict:
        """Write the validity-threats record. A valid record opens the
        analysis gate (F3.2) by writing the gate artifact; an invalid one is
        refused with the specific problems named (never silently accepted)."""
        from curated.threats import validate_record_doc

        job = s.get(MiningJob, job_id)
        if job is None or job.study_id != study_id:
            raise HTTPException(404, "mining job not found")
        record = body.get("threatsRecord", body)
        problems = validate_record_doc(record)
        if problems:
            raise HTTPException(
                422, "the validity-threats record is incomplete: " + "; ".join(problems)
            )
        ds = s.scalar(select(CuratedDataset).where(CuratedDataset.job_id == job_id))
        if ds is None:
            import secrets as _secrets

            ds = CuratedDataset(
                id=_secrets.token_hex(8),
                study_id=study_id,
                job_id=job_id,
                created_at=now(),
            )
            s.add(ds)
        ds.threats_record = record
        # Open the analysis gate by writing the gate artifact as a stored
        # file (the lifecycle engine keys on filenames - FR-CUR-3 F3.2).
        _write_gate_artifact(s, CURATED_GATE_ARTIFACT, record, study_id)
        job.state = mining.COMPLETE
        job.status_message = "complete — validity-threats record accepted."
        job.updated_at = now()
        s.commit()
        return {"finalized": True, "state": job.state, "gate": CURATED_GATE_ARTIFACT}

    def _write_gate_artifact(
        s: Session, filename: str, record: dict, study_id: str
    ) -> None:
        """Persist the threats record as a stored-file gate artifact so the
        existing lifecycle gate opens (no lifecycle-engine change)."""
        import yaml as _yaml

        content = _yaml.safe_dump(record, sort_keys=False).encode("utf-8")
        digest = sha256(content).hexdigest()
        settings.files_dir.mkdir(parents=True, exist_ok=True)
        path = settings.files_dir / f"{digest}.yaml"
        path.write_bytes(content)
        existing = s.scalar(
            select(StoredFile).where(
                StoredFile.filename == filename,
                StoredFile.sha256 == digest,
                StoredFile.study_id == study_id,
            )
        )
        if existing is None:
            s.add(
                StoredFile(
                    filename=filename,
                    stored_path=str(path),
                    content_type="application/x-yaml",
                    size=len(content),
                    sha256=digest,
                    study_id=study_id,
                    uploaded_at=now(),
                )
            )

    # ------------------------------- templates
    #
    # The registry serves published designs; instantiation is a pure function
    # of (template, parameters) that produces a protocol passing validation
    # with zero hand edits (F1.1). ``/templates`` (FR-AGF index) already
    # exists above; these add the FR-TPL instantiation + plan-explainer.

    @app.post("/templates/{template_id}/instantiate")
    def instantiate_template(template_id: str, body: TemplateInstantiateIn) -> dict:
        """Template + parameters → a validated protocol draft (FR-TPL-1.4).
        A template cannot silently produce an invalid protocol — a bad
        parameter or a skeleton defect surfaces as a 422 naming it."""
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
        """The statistical-plan explainer (FR-TPL-2.3): each choice in plain
        language with its why — never a bare test name."""
        try:
            tpl = template_registry.load_template(template_id)
        except template_registry.TemplateError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {
            "templateId": template_id,
            "explanation": template_registry.explain_plan(tpl),
        }

    @app.post("/templates/merge")
    def merge_templates_route(body: dict) -> dict:
        """Compose several templates into one novel, grounded protocol at
        runtime (FR-TPL): borrow a measure from one published design and an
        analysis from another. Every contributing template and its cited
        papers are returned as provenance."""
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
        """Search the corpus for papers (FR-LIT-9), not study-scoped — powers
        the "turn this paper into a template" picker. Returns the same
        confidence-ranked shape as a study's recommendations."""
        query = q.strip()
        if not query:
            return {"results": []}
        results = matching.match_papers(
            s, query, study_id=None, limit=max(1, min(limit, 25))
        )
        return {"results": results}

    @app.post("/templates/from-paper")
    def template_from_paper(body: dict, s: Session = Depends(db)) -> dict:
        """Turn a corpus paper into an executable template by binding it to a
        base archetype (FR-TPL-4): the paper becomes the design's primary
        source, so any of the corpus's thousands of papers is a starting
        point without hand-authoring a template each."""
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
        return {"template": template, "paper": meta}

    @app.get("/analysis/prescriptions")
    def analysis_prescriptions() -> dict:
        """The deterministic, LLM-free prescription table (FR-TPL-6): every
        design shape → the exact test, effect size, correction, and
        sample-size guidance, each with its rationale. Surfaced so the Data
        surface can show researchers what analysis their design calls for —
        the statistical formulation they most fear getting wrong (NFR-8)."""
        from analysis.prescribe import design_shapes

        rows = [
            design_assistant.recommend_prescription(shape) for shape in design_shapes()
        ]
        return {"prescriptions": [r for r in rows if r is not None]}

    # ------------------------- template submissions (FR-TPL-5)

    def _owner_membership(
        identity: auth.Identity, s: Session
    ) -> Membership | None:
        """Check if the caller is an owner on the implicit project."""
        from middleware.authz import has_role

        m = s.scalar(
            select(Membership).where(
                Membership.project_id == IMPLICIT_PROJECT_ID,
                Membership.identity_sub == identity.sub,
            )
        )
        if m is not None and has_role(m.role, "manage_members"):
            return m
        return None

    @app.post(
        "/templates/submissions",
        dependencies=[Depends(resolve_identity)],
    )
    def submit_template(
        body: TemplateSubmitIn,
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        """Submit a third-party template YAML for registry review (FR-TPL-5).

        The YAML is validated against the template schema before storage;
        a 422 is returned on schema violation so the submitter can fix it.
        """

        try:
            loaded = yaml.safe_load(body.templateYaml)
            if not isinstance(loaded, dict):
                raise ValueError("template YAML must be a mapping")
            problems = template_registry.validate_template(loaded)
        except yaml.YAMLError as exc:
            raise HTTPException(422, f"invalid YAML: {exc}") from exc
        except Exception as exc:
            raise HTTPException(422, str(exc)) from exc
        if problems:
            raise HTTPException(
                422, f"template validation failed: {'; '.join(problems)}"
            )

        row = TemplateSubmission(
            submitter_sub=identity.sub,
            name=body.name,
            template_yaml=body.templateYaml,
            status="pending",
            created_at=now(),
        )
        s.add(row)
        s.commit()
        return {
            "id": row.id,
            "name": row.name,
            "status": row.status,
            "createdAt": row.created_at,
        }

    @app.get("/templates/submissions")
    def list_template_submissions(
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        """List template submissions (FR-TPL-5).

        A caller sees their own submissions; owners of the implicit project
        see all pending submissions (review dashboard).
        """
        owner = _owner_membership(identity, s)
        if owner is not None:
            rows = s.scalars(
                select(TemplateSubmission).order_by(
                    TemplateSubmission.created_at.desc()
                )
            )
        else:
            rows = s.scalars(
                select(TemplateSubmission)
                .where(TemplateSubmission.submitter_sub == identity.sub)
                .order_by(TemplateSubmission.created_at.desc())
            )
        items = []
        for r in rows:
            items.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "submitterSub": r.submitter_sub,
                    "status": r.status,
                    "reviewerSub": r.reviewer_sub or None,
                    "reviewComment": r.review_comment or None,
                    "createdAt": r.created_at,
                    "reviewedAt": r.reviewed_at or None,
                }
            )
        return {"submissions": items, "count": len(items)}

    @app.get(
        "/templates/submissions/{sub_id}",
        dependencies=[Depends(resolve_identity)],
    )
    def get_template_submission(
        sub_id: int,
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        """View a single template submission and its full YAML."""
        row = s.scalar(
            select(TemplateSubmission).where(TemplateSubmission.id == sub_id)
        )
        if row is None:
            raise HTTPException(404, "submission not found")
        owner = _owner_membership(identity, s)
        if row.submitter_sub != identity.sub and owner is None:
            raise HTTPException(403, "not your submission")
        return {
            "id": row.id,
            "name": row.name,
            "submitterSub": row.submitter_sub,
            "status": row.status,
            "templateYaml": row.template_yaml,
            "reviewerSub": row.reviewer_sub or None,
            "reviewComment": row.review_comment or None,
            "createdAt": row.created_at,
            "reviewedAt": row.reviewed_at or None,
        }

    @app.post(
        "/templates/submissions/{sub_id}/decision",
        dependencies=[Depends(resolve_identity)],
    )
    def decide_template_submission(
        sub_id: int,
        body: TemplateDecisionIn,
        identity: auth.Identity = Depends(resolve_identity),
        s: Session = Depends(db),
    ) -> dict:
        """Approve or reject a template submission (FR-TPL-5, owner only).

        On **approval** the template YAML is validated and written to the
        registry directory as a new file (``templates/registry/<id>-<name>.yaml``).
        On **rejection** the submission is marked rejected with an optional
        review comment.
        """
        owner = _owner_membership(identity, s)
        if owner is None:
            raise HTTPException(403, "only project owners may review submissions")

        row = s.scalar(
            select(TemplateSubmission).where(TemplateSubmission.id == sub_id)
        )
        if row is None:
            raise HTTPException(404, "submission not found")
        if row.status != "pending":
            raise HTTPException(409, f"submission already {row.status}")

        row.status = body.status
        row.reviewer_sub = identity.sub
        row.review_comment = body.reviewComment
        row.reviewed_at = now()

        if body.status == "approved":
            try:
                loaded = yaml.safe_load(row.template_yaml)
                if not isinstance(loaded, dict):
                    raise ValueError("template YAML must be a mapping")
                problems = template_registry.validate_template(loaded)
                if problems:
                    raise ValueError(
                        f"validation failed: {'; '.join(problems)}"
                    )
                repo = Path(__file__).resolve().parent.parent.parent.parent
                reg_dir = repo / "templates" / "registry"
                reg_dir.mkdir(parents=True, exist_ok=True)
                slug = row.name.lower().replace(" ", "-").replace("/", "-")
                dest = reg_dir / f"submission-{row.id}-{slug}.yaml"
                if dest.exists():
                    raise ValueError(
                        f"file {dest.name} already exists in registry"
                    )
                dest.write_text(
                    yaml.safe_dump(
                        loaded, sort_keys=False, default_flow_style=False
                    )
                )
            except Exception as exc:
                s.rollback()
                raise HTTPException(422, str(exc)) from exc

        s.commit()
        return {
            "id": row.id,
            "name": row.name,
            "status": row.status,
            "reviewerSub": row.reviewer_sub,
            "reviewComment": row.review_comment or None,
            "reviewedAt": row.reviewed_at,
        }

    # ------------------------- design conversation
    #
    # The conversation stored as the elicitation record (FR-CONV-6): turns +
    # moves + compilations + approvals, append-only. Compilation is
    # deterministic and LLM-free (FR-CONV-3); a diff applies only through a
    # recorded approval (F3.3).

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
        study_id: str, body: ConversationTurnIn, s: Session = Depends(db)
    ) -> dict:
        """Append a researcher turn and generate the platform's grounded
        reply (FR-CONV-1). The reply's moves are built server-side from
        corpus rows the assistant's own tools returned this exchange, so no
        move can cite an unretrieved source (FR-CONV-2.2 / F2.1 — enforced
        by construction, then asserted). With no LLM key the deterministic
        design assistant answers (NFR-4); the LLM seam swaps in behind the
        same shape."""
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
        s.flush()  # researcher.seq is now settled; the reply is the next seq

        reply = design_assistant.respond(
            s,
            body.text,
            seq=researcher.seq + 1,
            study_id=study_id,
            # The medium tier, not `mistral-large-latest`: the design turn is a
            # single JSON completion (no tool loop), so the large model's
            # latency was the whole cost of a slow reply. Medium is markedly
            # faster and strong enough for this structured task (FR-CONV-1.4).
            client=assistant.make_client(assistant.MISTRAL_MODEL),
        )
        retrieved = set(reply["retrievedRefs"])
        # Belt-and-suspenders: grounding is built only from retrieved rows, so
        # this can only fire on a coding error — but the boundary is too
        # important to leave unasserted (mirrors the FR-ETH-4 grep test).
        for m in reply["moves"]:
            cited = {g["ref"] for g in m["grounding"]}
            assert cited <= retrieved, (
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
            created_at=now(),
            source=reply["source"],
        )
        s.add(platform)
        for m in reply["moves"]:
            s.add(
                DesignMoveRow(
                    id=f"{platform.id}:{m['moveId']}",
                    study_id=study_id,
                    turn_id=platform.id,
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
                }
                for m in reply["moves"]
            ],
            "recommendations": reply["recommendations"],
            "source": reply["source"],
        }

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
            select(DesignMoveRow).where(DesignMoveRow.study_id == study_id)
        ):
            moves_by_turn[mv.turn_id].append(
                {
                    "moveId": mv.id,
                    "kind": mv.kind,
                    "proposal": mv.proposal,
                    "patch": mv.patch,
                    "grounding": mv.grounding,
                    "status": mv.status,
                }
            )
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
                    "source": t.source,
                }
                for t in turns
            ],
        }

    @app.post(
        "/studies/{study_id}/conversation/moves/{move_id}/decision",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def decide_move(
        study_id: str, move_id: str, body: MoveDecisionIn, s: Session = Depends(db)
    ) -> dict:
        """Accept or reject a design move (FR-CONV-1.2). The decision is part
        of the elicitation record — the row is updated, never deleted."""
        if body.status not in ("accepted", "rejected"):
            raise HTTPException(400, "status must be 'accepted' or 'rejected'")
        mv = s.get(DesignMoveRow, move_id)
        if mv is None or mv.study_id != study_id:
            raise HTTPException(404, "design move not found")
        mv.status = body.status
        mv.decided_by = body.decidedBy
        mv.decided_at = now()
        s.commit()
        return {"moveId": move_id, "status": mv.status}

    @app.post(
        "/studies/{study_id}/conversation/compile",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def compile_conversation(
        study_id: str, body: CompileIn, s: Session = Depends(db)
    ) -> dict:
        """Compile the study's accepted moves into a protocol draft diff
        (FR-CONV-3). Deterministic + LLM-free; runs ``protocol validate`` so
        a schema-breaking move bounces back with errors (F3.2). Stored
        unapplied — only an approval advances the draft (F3.3)."""
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
                .where(DesignMoveRow.study_id == study_id)
                .order_by(DesignMoveRow.id)
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
        """Apply a compiled diff — the audited step (FR-CONV-3.3/F3.3). No
        other code path writes the draft. A draft that failed validation
        cannot be applied (a conversation never produces an invalid draft
        silently).

        Post-ethics (an ``ethics-approval`` recorded), an application is an
        **amendment** (FR-CONV-4.2): it needs the ``owner`` role, bumps the
        study revision, and writes an ``Amendment`` record. The deterministic
        consent-relevance rule (``evolution.consent_relevance``) decides
        whether it pauses new data-collection sessions until re-approval — never
        an LLM judgment, always version-visible, never sneaky."""
        comp = s.get(Compilation, body.compilationId)
        if comp is None or comp.study_id != study_id:
            raise HTTPException(404, "compilation not found")
        if not comp.valid:
            raise HTTPException(
                409,
                "this draft did not pass validation and cannot be applied — "
                f"resolve: {comp.errors or comp.unresolved}",
            )

        evo = s.get(StudyEvolution, study_id)
        is_amendment = evo is not None and bool(evo.ethics_approved_at)
        amendment_out: dict | None = None
        if is_amendment:
            # Post-ethics: amendment approval is owner-only (FR-PLAT-2, S3).
            if str(membership.role) != authz.Role.OWNER.value:
                raise HTTPException(
                    403,
                    "This study has ethics approval, so changing its protocol "
                    "is an amendment that only an owner may approve. Ask an "
                    "owner to approve it.",
                )
            amendment_out = _record_amendment(s, evo, comp, body)

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
        out: dict = {"applied": True, "compilationId": comp.id}
        if amendment_out is not None:
            out["amendment"] = amendment_out
        return out

    def _record_amendment(
        s: Session, evo: StudyEvolution, comp: Compilation, body: ApproveIn
    ) -> dict:
        """Write the Amendment record for a post-ethics application and advance
        the study's approved snapshot + revision. The consent verdict is the
        deterministic rule's, computed from the approved snapshot vs. the new
        draft; a relevant amendment sets the session-pause flag (F4.1)."""
        before = yaml.safe_load(evo.approved_yaml) or {}
        after = yaml.safe_load(comp.draft_yaml) or {}
        relevant, reasons = evolution.consent_relevance(before, after)
        changes = evolution.change_summary(before, after)
        grounding = sorted(
            {
                ref
                for mv in s.scalars(
                    select(DesignMoveRow).where(DesignMoveRow.id.in_(comp.move_ids))
                )
                for g in (mv.grounding or [])
                if (ref := g.get("ref")) and ref != "none"
            }
        )
        from_v = evo.current_version
        to_v = from_v + 1
        amend = Amendment(
            id=secrets.token_hex(8),
            study_id=evo.study_id,
            compilation_id=comp.id,
            from_version=from_v,
            to_version=to_v,
            summary=changes[0] if changes else "protocol amendment",
            changes=changes,
            rationale=body.rationale,
            grounding=grounding,
            consent_relevant=int(relevant),
            consent_reasons=reasons,
            approved_by=body.approvedBy,
            role=authz.Role.OWNER.value,
            created_at=now(),
        )
        s.add(amend)
        evo.current_version = to_v
        evo.approved_yaml = comp.draft_yaml
        if relevant:
            evo.pending_reapproval = amend.id
        evo.updated_at = now()
        return {
            "amendmentId": amend.id,
            "fromVersion": from_v,
            "toVersion": to_v,
            "consentRelevant": relevant,
            "consentReasons": reasons,
            "requiresReapproval": relevant,
        }

    def _run_aggregation(s: Session) -> dict:
        """Recompute cross-project usage shapes (FR-CONV-5.3). A full-snapshot
        recompute (clear + rewrite) so the table is a deterministic function of
        the conversation corpus, independent of cadence (a degree of freedom).
        Every value written is a vocabulary token — never text or an id."""
        templates_chosen: list[str] = []
        studies_with_template: set[str] = set()
        for mv in s.scalars(
            select(DesignMoveRow).where(
                DesignMoveRow.kind == "choose-template",
                DesignMoveRow.status == "accepted",
            )
        ):
            tid = (mv.patch or {}).get("templateId")
            if tid:
                templates_chosen.append(tid)
                studies_with_template.add(mv.study_id)
        rejected_move_kinds = [
            mv.kind
            for mv in s.scalars(
                select(DesignMoveRow).where(DesignMoveRow.status == "rejected")
            )
        ]
        unresolved_slots: list[str] = []
        stalls: list[str] = []
        for c in s.scalars(select(Compilation)):
            unresolved_slots.extend(c.unresolved or [])
            stalls.append(
                evolution.stall_category(
                    valid=bool(c.valid),
                    errors=c.errors or [],
                    unresolved=c.unresolved or [],
                    has_template=c.study_id in studies_with_template,
                )
            )
        shapes = evolution.accumulate_shapes(
            templates_chosen=templates_chosen,
            unresolved_slots=unresolved_slots,
            stalls=stalls,
            rejected_move_kinds=rejected_move_kinds,
        )
        ts = now()
        s.execute(delete(AggregateShape))
        for metric, key, count in shapes:
            s.add(AggregateShape(metric=metric, key=key, count=count, computed_at=ts))
        s.commit()
        return {"computed": len(shapes), "computedAt": ts}

    @app.get(
        "/studies/{study_id}/conversation/export",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def export_elicitation(study_id: str, s: Session = Depends(db)) -> dict:
        """The elicitation record (FR-CONV-6): the full chain from idea to
        specification — turns, moves + grounding, compilations, approvals,
        and the current draft — captured by construction, not reconstructed."""
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
        amendments = [
            _amendment_json(a)
            for a in s.scalars(
                select(Amendment)
                .where(Amendment.study_id == study_id)
                .order_by(Amendment.from_version)
            )
        ]
        draft = s.get(ProtocolDraftRow, study_id)
        return {
            "studyId": study_id,
            "turns": conv["turns"],
            "compilations": compilations,
            "approvals": approvals,
            # The elicitation record now carries design, amendment, and feedback
            # (FR-CONV-6 extended by amendment hunks); redaction never unmakes
            # a decision, so amendments survive a redacted turn intact.
            "amendments": amendments,
            "currentDraft": draft.yaml if draft else "",
        }

    # -------------------------------------------------- evolution (A/B/C)

    @app.post(
        "/studies/{study_id}/ethics-approval",
        dependencies=[Depends(require_project_for_study("freeze"))],
    )
    def approve_ethics(study_id: str, s: Session = Depends(db)) -> dict:
        """Record that the study's current draft has ethics approval (owner,
        FR-PLAT-2). This snapshots the *approved protocol* — the executed
        protocol S3 cares about — so every later compile-approve becomes a
        version-visible amendment diffed against it (FR-CONV-4.2). Pre-ethics,
        amendments are ordinary compilations (FR-CONV-4.1); this is the line
        that turns ceremony on."""
        draft = s.get(ProtocolDraftRow, study_id)
        if draft is None or not draft.yaml:
            raise HTTPException(
                409,
                "approve a compiled protocol draft before recording ethics "
                "approval — there is nothing to freeze yet.",
            )
        evo = s.get(StudyEvolution, study_id)
        if evo is None:
            evo = StudyEvolution(study_id=study_id, current_version=1)
            s.add(evo)
        evo.ethics_approved_at = now()
        evo.approved_yaml = draft.yaml
        evo.current_version = evo.current_version or 1
        evo.pending_reapproval = ""
        evo.updated_at = now()
        s.commit()
        return {
            "ethicsApprovedAt": evo.ethics_approved_at,
            "version": evo.current_version,
        }

    @app.post(
        "/studies/{study_id}/sessions/start",
        dependencies=[Depends(require_project_for_study("run_recipe"))],
    )
    def start_session(
        study_id: str, body: SessionStartIn, s: Session = Depends(db)
    ) -> dict:
        """Open a data-collection session under the study's current revision
        (FR-CONV-4). The gate refuses *new* sessions while a consent-relevant
        amendment awaits re-approval (F4.1); a session already open resumes with
        the revision it began under — running sessions are never touched by an
        evolving study (NFR-1, the F4.2 in-flight guarantee)."""
        existing = s.get(SessionOpen, body.sessionId)
        if existing is not None:
            return {
                "sessionId": existing.session_id,
                "protocolVersion": existing.protocol_version,
                "resumed": True,
            }
        evo = s.get(StudyEvolution, study_id)
        if evo is not None and evo.pending_reapproval:
            raise HTTPException(
                409,
                "New sessions are paused: a consent-relevant amendment is "
                "awaiting ethics re-approval. Upload the re-approval to resume "
                "— already-collected data and any open sessions are unaffected.",
            )
        version = evo.current_version if evo is not None else 1
        s.add(
            SessionOpen(
                session_id=body.sessionId,
                study_id=study_id,
                protocol_version=version,
                opened_at=now(),
            )
        )
        s.commit()
        return {
            "sessionId": body.sessionId,
            "protocolVersion": version,
            "resumed": False,
        }

    @app.post(
        "/studies/{study_id}/reapproval",
        dependencies=[Depends(require_project_for_study("freeze"))],
    )
    def record_reapproval(
        study_id: str, body: ReapprovalIn, s: Session = Depends(db)
    ) -> dict:
        """Record the updated ethics artifact that lifts a consent-relevant
        amendment's session pause (owner, F4.1). This is the existing gate-
        artifact mechanism with one more artifact type — the re-approval."""
        evo = s.get(StudyEvolution, study_id)
        if evo is None or not evo.pending_reapproval:
            raise HTTPException(
                409, "no amendment on this study is awaiting re-approval."
            )
        amend = s.get(Amendment, evo.pending_reapproval)
        if amend is not None:
            amend.reapproval_artifact = body.artifact or "ethics-reapproval"
            amend.reapproved_at = now()
        evo.pending_reapproval = ""
        evo.updated_at = now()
        s.commit()
        return {"reapproved": True, "amendmentId": amend.id if amend else ""}

    @app.get(
        "/studies/{study_id}/amendments",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def list_amendments(study_id: str, s: Session = Depends(db)) -> dict:
        """The amendment history (FR-CONV-4.6): versions, summaries, approvers,
        artifacts — a quiet record that evolution is normal. Carries the study's
        current revision and whether new sessions are paused (the banner)."""
        evo = s.get(StudyEvolution, study_id)
        amendments = [
            _amendment_json(a)
            for a in s.scalars(
                select(Amendment)
                .where(Amendment.study_id == study_id)
                .order_by(Amendment.from_version)
            )
        ]
        return {
            "studyId": study_id,
            "ethicsApprovedAt": evo.ethics_approved_at if evo else "",
            "currentVersion": evo.current_version if evo else 1,
            "pendingReapproval": evo.pending_reapproval if evo else "",
            "amendments": amendments,
        }

    @app.get(
        "/studies/{study_id}/amendments/{amendment_id}/summary",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def amendment_summary(
        study_id: str, amendment_id: str, s: Session = Depends(db)
    ) -> PlainTextResponse:
        """The ethics-board amendment delta as Markdown (FR-CONV-4.3): what
        changed, why, consent impact — generated deterministically from the
        amendment record (FR-ANA-6 style), the document S1 sends S3."""
        amend = s.get(Amendment, amendment_id)
        if amend is None or amend.study_id != study_id:
            raise HTTPException(404, "amendment not found")
        doc = evolution.amendment_summary_doc(
            study_id=study_id,
            from_version=amend.from_version,
            to_version=amend.to_version,
            rationale=amend.rationale,
            changes=amend.changes,
            consent_relevant=bool(amend.consent_relevant),
            consent_reasons=amend.consent_reasons,
            grounding=amend.grounding,
            approved_by=amend.approved_by,
            approved_at=amend.created_at,
        )
        return PlainTextResponse(doc, media_type="text/markdown")

    @app.post(
        "/studies/{study_id}/conversation/turns/{turn_id}/feedback",
        dependencies=[Depends(require_project_for_study("contribute"))],
    )
    def mark_feedback(
        study_id: str, turn_id: str, body: FeedbackIn, s: Session = Depends(db)
    ) -> dict:
        """Mark a conversation turn as platform feedback (FR-CONV-5.1). The
        turn becomes a Finding (the FR-META-1 pipeline) with a
        ``conversationLocus`` pointing back at the exact turn — the platform's
        SRS grows from its users' conversations. The finding is platform-scoped
        data; its message carries no turn text, so rendering the locus still
        requires project membership (the boundary holds even for meta-data)."""
        turn = s.get(ConversationTurn, turn_id)
        if turn is None or turn.study_id != study_id:
            raise HTTPException(404, "conversation turn not found")
        finding = Finding(
            at=now(),
            source="conversation",
            kind="feedback",
            requirement_id="FR-CONV-5",
            # No turn text here: the locus points into project-scoped content,
            # which only a member may resolve (B.3). The note is the marker's.
            message=body.note or f"Feedback marked on turn {turn.seq}",
            context={
                "conversationLocus": {
                    "studyId": study_id,
                    "turnId": turn_id,
                    "seq": turn.seq,
                    "kind": body.kind,
                }
            },
            status="open",
        )
        s.add(finding)
        s.flush()
        return {"findingId": finding.id, "kind": body.kind}

    @app.get(
        "/studies/{study_id}/conversation/feedback-suggestions",
        dependencies=[Depends(require_project_for_study("view"))],
    )
    def feedback_suggestions(study_id: str, s: Session = Depends(db)) -> dict:
        """*Offer* the feedback marking when a researcher turn reads as feedback
        (FR-CONV-5.1 — detection is a freedom, marking is the requirement).
        Heuristic and always-confirmed: never auto-filed. Returns candidate
        turn ids, so the UI can nudge, not decide."""
        cues = (
            "it would be better",
            "i wish",
            "the platform should",
            "confusing",
            "hard to",
            "frustrating",
            "too many clicks",
            "couldn't find",
            "why doesn't",
            "annoying",
            "unclear",
        )
        already = {
            f.context.get("conversationLocus", {}).get("turnId")
            for f in s.scalars(select(Finding).where(Finding.kind == "feedback"))
        }
        suggestions = []
        for t in s.scalars(
            select(ConversationTurn)
            .where(
                ConversationTurn.study_id == study_id,
                ConversationTurn.role == "researcher",
            )
            .order_by(ConversationTurn.seq)
        ):
            if t.id in already or t.redacted:
                continue
            low = (t.text or "").lower()
            if any(cue in low for cue in cues):
                suggestions.append({"turnId": t.id, "seq": t.seq})
        return {"studyId": study_id, "suggestions": suggestions}

    @app.get("/platform/findings", dependencies=[Depends(view_auth)])
    def platform_findings(s: Session = Depends(db)) -> list[dict]:
        """The platform's feedback findings (FR-CONV-5.1, F5.1) — the loci only.
        The turn text lives behind the project-scoped conversation endpoint, so
        this platform-scoped surface leaks no project content."""
        rows = s.scalars(
            select(Finding).where(Finding.kind == "feedback").order_by(Finding.id)
        )
        return [
            {
                "id": f.id,
                "at": f.at,
                "note": f.message,
                "status": f.status,
                "locus": f.context.get("conversationLocus", {}),
            }
            for f in rows
        ]

    @app.post("/platform/aggregate", dependencies=[Depends(view_auth)])
    def compute_aggregate(s: Session = Depends(db)) -> dict:
        """Recompute the cross-project usage shapes (FR-CONV-5.3). Reads every
        project's conversation *shape* — template ids, unresolved-slot names,
        stall categories, rejected-move kinds — and writes only anonymous
        counts. No conversation text, protocol content, or project identifier
        is read into a shape row; the grep-the-output test (F5.3) asserts it."""
        return _run_aggregation(s)

    @app.get("/platform/aggregate", dependencies=[Depends(view_auth)])
    def get_aggregate(s: Session = Depends(db)) -> list[dict]:
        rows = s.scalars(
            select(AggregateShape).order_by(AggregateShape.metric, AggregateShape.key)
        )
        return [
            {
                "metric": r.metric,
                "key": r.key,
                "count": r.count,
                "computedAt": r.computed_at,
            }
            for r in rows
        ]

    @app.get("/platform/retrospective", dependencies=[Depends(view_auth)])
    def platform_retrospective(s: Session = Depends(db)) -> dict:
        """Draft the platform's own retrospective proposal (FR-CONV-5.2,
        extends FR-META-2): an **inert** draft that cites the findings rows and
        aggregate shapes it used. A human approves it; nothing self-applies."""
        findings = [
            {"id": f.id, "kind": f.kind, "context": f.context}
            for f in s.scalars(select(Finding).where(Finding.kind == "feedback"))
        ]
        shapes = [
            {"metric": r.metric, "key": r.key, "count": r.count}
            for r in s.scalars(select(AggregateShape))
        ]
        return evolution.draft_proposal(findings=findings, shapes=shapes)

    # ---------------------------------------------------------------- health

    @app.get("/health")
    def health() -> dict:
        try:
            with session_factory() as s:
                s.execute(sqltext("SELECT 1"))
            db_ok = True
        except Exception:
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
        """Which sign-in surface the platform should render (FR-OPS-5).

        Open by necessity (the platform asks before it can sign in);
        carries no secrets - see ``auth.public_config``.
        """
        return auth.public_config(settings)

    # ---------------------------------------------- platform SPA (NFR-7)
    # Production mode serves the built React `platform/` app from the same
    # process: `docker compose up` is the whole stack. Dev mode uses the Vite
    # proxy instead, so a missing build directory just means API-only.
    #
    # The app is entered at `/` (the hero) and routes client-side. The explicit
    # fallbacks below re-serve the shell on a deep-link refresh of the app's
    # own route prefixes.
    #
    # None of the SPA's client routes share a path with a GET API endpoint
    # below (2026-07-21: `/projects` used to, until the SPA's project-list
    # route moved to `/home` — a hard navigation/refresh/the sign-in/sign-out
    # `location.reload()` while on that screen was hitting `list_projects`'s
    # JSON response directly instead of ever reaching the SPA shell; same
    # fix already applied once before for the same reason). Keep it that way
    # for any new top-level client route: check it against the API surface
    # first, or give it its own fallback below like `/p/*` and
    # `/invitations/*` already have.

    dist = settings.spa_dist
    index_html = dist / "index.html"
    if index_html.is_file():
        # The shell must always revalidate: Vite's assets are content-hashed
        # (safe to cache), but a cached index.html pins users to a stale
        # bundle across deploys - the app keeps running old code from disk.
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

        app.mount("/", StaticFiles(directory=dist), name="platform")

    return app


def _ensure_study_row(s: Session, study_id: str, protocol_doc: dict) -> None:
    """Create or backfill a study row for the loaded protocol.

    The row lives in the ``studies`` table, owned by the implicit project,
    so the project choke point can resolve ``study_id -> project ->
    membership``. Idempotent: only ``project_id`` is patched on an existing
    row that pre-dates the column.
    """

    row = s.scalar(select(Study).where(Study.id == study_id))
    if row is not None:
        # Pre- row with no project_id — adopt it (the migration ran
        # for orphan studies, but this row might have been created before
        # the migration existed).
        if not row.project_id:
            row.project_id = IMPLICIT_PROJECT_ID
        return
    phase = ""
    pv = ""
    if protocol_doc:
        phase = current_phase(protocol_doc, set()) or ""
        pv = str(protocol_doc.get("protocolVersion", ""))
    s.add(
        Study(
            id=study_id,
            project_id=IMPLICIT_PROJECT_ID,
            protocol_version=pv,
            phase=phase,
        )
    )


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
    """Aggregate one session's per-producer gap facts.

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


def _amendment_json(a: Amendment) -> dict:
    """One amendment row as JSON (FR-CONV-4): version delta, summary, consent
    verdict + reasons, approver, and the re-approval artifact once uploaded."""
    return {
        "id": a.id,
        "compilationId": a.compilation_id,
        "fromVersion": a.from_version,
        "toVersion": a.to_version,
        "summary": a.summary,
        "changes": a.changes,
        "rationale": a.rationale,
        "grounding": a.grounding,
        "consentRelevant": bool(a.consent_relevant),
        "consentReasons": a.consent_reasons,
        "approvedBy": a.approved_by,
        "role": a.role,
        "reapprovalArtifact": a.reapproval_artifact or None,
        "reapprovedAt": a.reapproved_at or None,
        "at": a.created_at,
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
