"""FastAPI ingestion service (FR-ING-1..6)."""

import logging
import math
import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from fastapi import (
    FastAPI,
    Header,
)
from fastapi.responses import (
    FileResponse,
)
from fastapi.staticfiles import StaticFiles
from protocol.capture import (
    privacy_policy,
)
from sqlalchemy import func, or_, select, union
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

from middleware import (
    auth,
    authz,
    compiler,
    corpus_importer,
    corpus_refresh,
)
from middleware.db import (
    ConversationTurn,
    DesignMoveRow,
    EnrollmentToken,
    Event,
    MetricRow,
    ProtocolDraftRow,
    SessionAnnotation,
    SessionBlock,
    SessionOpen,
    make_session_factory,
)
from middleware.evidence_routes import register_routes as register_evidence_routes
from middleware.route_helpers import (
    Clock,
    _capture_payload,
    _ensure_study_row,
    _ProtocolCheck,
)
from middleware.route_helpers import (
    _slug_from_text as _slug_from_text,
)
from middleware.route_helpers import (
    canonical_source as canonical_source,
)
from middleware.routes import (
    conversation,
    ingest,
    library,
    meta,
    participants,
    projects,
    study_data,
)
from middleware.routes.deps import ApiDeps
from middleware.settings import Settings

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, clock: Clock | None = None) -> FastAPI:
    settings = settings or Settings()
    clock = clock or (lambda: datetime.now(UTC))
    web_index = settings.spa_dist / "index.html"
    if not web_index.is_file() and settings.spa_required:
        raise FileNotFoundError(
            f"Platform build missing: {web_index}. "
            "Run npm --prefix platform run build, or set "
            "MIDDLEWARE_API_ONLY=1 for API-only operation."
        )
    web_hash = sha256()
    if web_index.is_file():
        for asset in sorted(settings.spa_dist.rglob("*")):
            if asset.is_file():
                web_hash.update(str(asset.relative_to(settings.spa_dist)).encode())
                web_hash.update(asset.read_bytes())
        log.info(
            "Serving platform from %s (build sha256 %s)",
            settings.spa_dist,
            web_hash.hexdigest(),
        )
    else:
        log.warning("API-only mode: platform build missing at %s", web_index)
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

    refresh_hours = os.environ.get("MIDDLEWARE_REFRESH_INTERVAL_H", "").strip()
    if refresh_hours:
        try:
            hours = float(refresh_hours)
            if not math.isfinite(hours) or hours <= 0:
                raise ValueError("must be positive")
        except ValueError as exc:
            log.warning(
                "MIDDLEWARE_REFRESH_INTERVAL_H=%r ignored: %s", refresh_hours, exc
            )
        else:
            corpus_refresh.start_scheduler(
                interval_hours=hours,
                run=lambda: corpus_refresh.run_once(
                    session_factory,
                    config_path=(
                        Path(os.environ["MIDDLEWARE_REFRESH_QUERIES"])
                        if os.environ.get("MIDDLEWARE_REFRESH_QUERIES")
                        else None
                    ),
                ),
            )

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

    verify_view_auth = auth.verifier_from_settings(settings)

    def view_auth(authorization: str = Header(default="")) -> None:
        verify_view_auth(authorization)

    authz_dep = authz.build_authz(
        session_factory, verify_view_auth, loaded_study_id=lambda: check.study_id
    )
    require_project_for_study = authz_dep["require_project_for_study"]
    resolve_identity = authz_dep["resolve_identity"]

    def _session_scope(study_id: str, include_synthetic: bool = False):
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
        synthetic = union(
            select(Event.session_id).where(Event.payload["synthetic"].as_boolean()),
            select(MetricRow.session_id).where(MetricRow.row["synthetic"].as_boolean()),
            # Older seed sessions remain synthetic even after seed paths are removed.
            select(SessionBlock.session_id).where(
                SessionBlock.session_id.in_([f"S-sample-{i:03d}" for i in range(1, 12)])
            ),
        )

        def in_this_study(column):
            here = column.in_(scoped)
            predicate = or_(here, column.notin_(mapped)) if adopt_unattributed else here
            return (
                predicate if include_synthetic else predicate & column.notin_(synthetic)
            )

        return in_this_study

    def _joined_rows(
        s: Session, study_id: str, include_synthetic: bool = False
    ) -> list[dict]:
        """Join events and metrics belonging to this study, for every export."""
        in_this_study = _session_scope(study_id, include_synthetic)
        raw_code = privacy_policy(_resolve_study_protocol(s, study_id) or {})["rawCode"]
        rows = [
            {
                "source": e.source,
                "ts": e.ts,
                "sessionId": e.session_id,
                "participantId": e.participant_id,
                "condition": e.condition,
                "taskId": e.task_id,
                "schemaVersion": e.v,
                "type": e.type,
                "seq": e.seq,
                "flags": e.flags,
                "payload": _capture_payload(e.payload, raw_code),
            }
            for e in s.scalars(select(Event).where(in_this_study(Event.session_id)))
        ] + [
            {
                "source": "metrics",
                "ts": m.timestamp,
                "sessionId": m.session_id,
                "participantId": m.participant_id,
                "condition": m.condition,
                "taskId": m.task_id,
                "schemaVersion": m.schema_version,
                "type": m.table,
                "seq": None,
                "flags": m.flags,
                "payload": m.row,
            }
            for m in s.scalars(
                select(MetricRow).where(in_this_study(MetricRow.session_id))
            )
        ]
        annotations = {
            a.session_id: a
            for a in s.scalars(
                select(SessionAnnotation).where(SessionAnnotation.study_id == study_id)
            )
        }
        for row in rows:
            annotation = annotations.get(row["sessionId"])
            if annotation:
                row["pilot"] = bool(annotation.pilot)
                row["inclusionDecision"] = annotation.decision
                if annotation.pilot:
                    row["flags"] = [*row["flags"], "pilot"]
        rows.sort(key=lambda r: (r["ts"], r["source"], r["seq"] or 0))
        return rows

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

    def _conversation_seq(s: Session, study_id: str) -> int:
        last = s.scalar(
            select(func.max(ConversationTurn.seq)).where(
                ConversationTurn.study_id == study_id
            )
        )
        return (last or 0) + 1

    def _conversation_moves(s: Session, study_id: str) -> list[dict]:
        """Return the ordered move ledger used for compilation and verification."""
        return [
            {
                "moveId": mv.id,
                "kind": mv.kind,
                "target": mv.target,
                "proposal": mv.proposal,
                "patch": mv.patch,
                "grounding": mv.grounding,
                "status": mv.status,
                "decidedBy": mv.decided_by,
                "decidedAt": mv.decided_at,
            }
            for mv in s.scalars(
                select(DesignMoveRow)
                .join(ConversationTurn, DesignMoveRow.turn_id == ConversationTurn.id)
                .where(DesignMoveRow.study_id == study_id)
                .order_by(ConversationTurn.seq, DesignMoveRow.seq)
            )
        ]

    deps = ApiDeps(
        settings=settings,
        session_factory=session_factory,
        check=check,
        protocol_loaded=lambda: protocol_doc is not None,
        web_index=web_index,
        web_hash=web_hash,
        db=db,
        now=now,
        resolve_credential=resolve_credential,
        session_scope=_session_scope,
        authz=authz_dep,
        view_auth=view_auth,
        resolve_study_protocol=_resolve_study_protocol,
        joined_rows=_joined_rows,
        conversation_moves=_conversation_moves,
        clock=clock,
        export_elicitation=lambda *args, **kwargs: export_elicitation(*args, **kwargs),
        conversation_seq=_conversation_seq,
        adopt_corpus_paper=lambda *args, **kwargs: _adopt_corpus_paper(*args, **kwargs),
    )

    ingest.register(app, deps)

    study_data.register(app, deps)

    _adopt_corpus_paper = library.register(app, deps)

    meta.register(app, deps)

    export_elicitation = conversation.register(app, deps)

    projects.register(app, deps)

    participants.register(app, deps)

    def evidence_draft(s, study_id):
        existing = s.get(ProtocolDraftRow, study_id)
        return compiler.compile_moves(
            _conversation_moves(s, study_id),
            base_yaml=existing.yaml if existing else "",
        ).draft

    register_evidence_routes(
        app, db, require_project_for_study, now, _conversation_seq, evidence_draft
    )
    from middleware.planner_routes import register_routes as register_planner_routes

    register_planner_routes(
        app,
        db,
        require_project_for_study,
        _resolve_study_protocol,
        _joined_rows,
        now,
        resolve_identity,
    )

    dist = settings.spa_dist
    index_html = dist / "index.html"
    if index_html.is_file():
        _no_store = {"Cache-Control": "no-cache"}

        def _shell() -> FileResponse:
            return FileResponse(index_html, headers=_no_store)

        # Every route App.tsx renders. A path missing here would 404 on the
        # server for a refresh or bookmark even though the client router handles
        # it from a soft navigation.
        for client_route in (
            "/",
            "/home",
            "/start",
            "/settings",
            "/repertoire",
            "/signin",
            "/p/{rest:path}",
            "/invitations/{rest:path}",
        ):
            app.get(client_route, include_in_schema=False)(_shell)

        class _AppFiles(StaticFiles):
            """Static files, plus the app shell for an unknown *browser* path.

            A page request for a URL the server does not know gets the app, which
            renders its own "not found" page (status 404), never raw JSON. API
            clients (no ``text/html`` in Accept) and missing assets (a path with
            a file extension) still get a plain 404.
            """

            async def get_response(self, path: str, scope):  # type: ignore[override]
                try:
                    response = await super().get_response(path, scope)
                except StarletteHTTPException as exc:
                    if exc.status_code != 404:
                        raise
                    response = None
                if response is not None and response.status_code != 404:
                    return response
                accept = dict(scope["headers"]).get(b"accept", b"").decode()
                if "text/html" in accept and "." not in path.rsplit("/", 1)[-1]:
                    return FileResponse(index_html, status_code=404, headers=_no_store)
                if response is None:
                    raise StarletteHTTPException(404)
                return response

        app.mount(
            "/",
            GZipMiddleware(
                _AppFiles(directory=dist), minimum_size=1000, compresslevel=6
            ),
            name="platform",
        )

    return app
