"""Participants API routes."""

import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import yaml
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import (
    Response,
)
from protocol.assignment import assign
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from middleware import (
    compiler,
    enrollment,
    workspace,
)
from middleware.db import (
    EnrollmentToken,
    Event,
    ProtocolDraftRow,
    SessionBlock,
    StudyWorkspace,
)
from middleware.routes.deps import ApiDeps
from middleware.schemas import (
    MintTokensIn,
    RedeemIn,
    ToggleIn,
)

log = logging.getLogger("middleware.app")


def register(app: FastAPI, deps: ApiDeps):
    @app.post(
        "/studies/{study_id}/enrollment/tokens",
        dependencies=[Depends(deps.authz["require_project_for_study"]("mint_token"))],
    )
    def mint_enrollment_tokens(
        study_id: str,
        body: MintTokensIn,
        request: Request,
        s: Session = Depends(deps.db),
    ) -> list[dict]:
        from datetime import timedelta as td

        protocol = deps.resolve_study_protocol(s, study_id)
        if protocol is None:
            raise HTTPException(404, f"no protocol for study {study_id!r}")
        if body.grain not in {"participant", "session"}:
            raise HTTPException(400, "grain must be 'participant' or 'session'")
        if body.count < 1 or body.count > 100:
            raise HTTPException(400, "count must be between 1 and 100")
        conditions = protocol["conditions"]
        existing = s.scalars(
            select(EnrollmentToken).where(EnrollmentToken.study_id == study_id)
        ).all()
        start = len(existing)
        base = str(request.base_url).rstrip("/")
        expires = (deps.clock() + td(days=30)).isoformat(timespec="milliseconds")
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
                created_at=deps.now(),
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
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def list_enrollment_tokens(
        study_id: str,
        request: Request,
        windowSeconds: int = 300,
        s: Session = Depends(deps.db),
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

        cutoff = (deps.clock() - timedelta(seconds=windowSeconds)).astimezone(UTC)
        cutoff_s = cutoff.isoformat(timespec="milliseconds")
        streaming_participants = set(
            s.scalars(
                select(Event.participant_id)
                .where(Event.received_at >= cutoff_s)
                .distinct()
            ).all()
        )

        protocol = deps.resolve_study_protocol(s, study_id)
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
        dependencies=[Depends(deps.authz["require_project_for_study"]("mint_token"))],
    )
    def revoke_enrollment_token(
        study_id: str, token_id: str, s: Session = Depends(deps.db)
    ) -> dict:
        """Revoke a pairing token (researcher+, study-scoped)."""

        row = s.get(EnrollmentToken, token_id)
        if row is None or row.study_id != study_id:
            raise HTTPException(404, "enrollment token not found")
        row.revoked_at = deps.now()
        s.commit()
        return {"revoked": token_id}

    @app.get(
        "/studies/{study_id}/enrollment/toggles/catalog",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def toggles_catalog(study_id: str, s: Session = Depends(deps.db)) -> list[dict]:
        """List togglable capture metrics for a study's protocol shape (FR-DASH-11)."""
        protocol = deps.resolve_study_protocol(s, study_id)
        if protocol is None:
            raise HTTPException(404, "study not found")
        return enrollment.toggle_catalog(protocol)

    @app.post(
        "/studies/{study_id}/enrollment/toggles",
        dependencies=[
            Depends(deps.authz["require_project_for_study"]("toggle_capture"))
        ],
    )
    def apply_toggle(
        study_id: str, body: ToggleIn, s: Session = Depends(deps.db)
    ) -> dict:
        """Apply one metric toggle to the protocol's instruments block (FR-DASH-11)."""
        before = deps.resolve_study_protocol(s, study_id)
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
        row.updated_at = deps.now()
        s.commit()
        return {"applied": True}

    @app.post("/pair/redeem")
    def pair_redeem(
        body: RedeemIn, request: Request, s: Session = Depends(deps.db)
    ) -> dict:
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
            if datetime.fromisoformat(row.expires_at) < deps.clock():
                raise HTTPException(
                    410, "this connection link has expired. Ask for a new one"
                )
        except (ValueError, TypeError):
            pass
        if row.grain == "session" and row.redeemed_at:
            raise HTTPException(
                410, "this single-use connection link has already been used"
            )
        protocol = deps.resolve_study_protocol(s, row.study_id)
        if protocol is None:
            raise HTTPException(404, "no protocol for this study")
        # Resolve the first task block at pairing time as display/config state,
        # without consuming a session. This lets the participant editor open
        # the assigned local workspace immediately after the link is redeemed.
        task, block = _block_for_session(s, protocol, row, None)
        if not row.credential:
            row.credential = secrets.token_urlsafe(32)
        if row.grain == "session" or not row.redeemed_at:
            row.redeemed_at = deps.now()
        s.commit()
        base = str(request.base_url).rstrip("/")
        effective = enrollment.apply_capture_overrides(protocol, row.capture_overrides)
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
            "consentStatement": enrollment.consent_statement(effective),
            "contentPolicy": enrollment.content_policy(effective),
        }

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
                        assigned_at=deps.now(),
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
            "workspace": _workspace_for(s, row.study_id, task),
        }

    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "study"

    def _workspace_for(s: Session, study_id: str, task: dict | None) -> dict | None:
        """The folder a minted link opens: the researcher's setting, else the task's."""
        row = s.get(StudyWorkspace, study_id)
        if row is not None and row.kind == "path":
            return {"kind": "path", "path": row.path}
        if row is not None and row.kind == "archive":
            return {
                "kind": "archive",
                "url": f"/studies/{study_id}/workspace/archive",
                "sha256": row.sha256,
                "size": row.size,
                "filename": row.filename,
            }
        materials = ((task or {}).get("materials") or "").strip()
        return {"kind": "path", "path": materials} if materials else None

    def _workspace_doc(row: StudyWorkspace | None) -> dict:
        if row is None:
            return {"kind": None}
        return {
            "kind": row.kind,
            "path": row.path,
            "filename": row.filename,
            "sha256": row.sha256,
            "size": row.size,
            "updatedAt": row.updated_at,
        }

    @app.get(
        "/studies/{study_id}/workspace",
        dependencies=[Depends(deps.authz["require_project_for_study"]("view"))],
    )
    def get_workspace(study_id: str, s: Session = Depends(deps.db)) -> dict:
        """The folder participants' minted links open, if the researcher set one."""
        return _workspace_doc(s.get(StudyWorkspace, study_id))

    @app.put(
        "/studies/{study_id}/workspace",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    async def set_workspace(
        study_id: str,
        path: str | None = Form(default=None),
        file: UploadFile | None = File(default=None),
        s: Session = Depends(deps.db),
    ) -> dict:
        """Name the study folder: a path on participants' machines, or a zip of it."""
        if (path is None) == (file is None):
            raise HTTPException(400, "send either a folder path or a zip, not both")
        row = s.get(StudyWorkspace, study_id) or StudyWorkspace(study_id=study_id)
        try:
            if file is not None:
                content = await file.read(workspace.MAX_ARCHIVE_BYTES + 1)
                workspace.validate_archive(content)
                digest = sha256(content).hexdigest()
                folder = deps.settings.data_dir / "workspaces"
                folder.mkdir(parents=True, exist_ok=True)
                stored = folder / f"{_safe_name(study_id)}-{digest[:16]}.zip"
                stored.write_bytes(content)
                row.kind = "archive"
                row.path = None
                row.filename = file.filename or "workspace.zip"
                row.stored_path = str(stored)
                row.sha256 = digest
                row.size = len(content)
            else:
                row.kind = "path"
                row.path = workspace.validate_path(path or "")
                row.filename = row.stored_path = row.sha256 = None
                row.size = None
        except workspace.WorkspaceError as exc:
            raise HTTPException(422, str(exc)) from exc
        row.updated_at = deps.now()
        s.add(row)
        s.flush()
        return _workspace_doc(row)

    @app.delete(
        "/studies/{study_id}/workspace",
        dependencies=[Depends(deps.authz["require_project_for_study"]("contribute"))],
    )
    def clear_workspace(study_id: str, s: Session = Depends(deps.db)) -> dict:
        row = s.get(StudyWorkspace, study_id)
        if row is not None:
            s.delete(row)
        return {"kind": None}

    @app.get("/studies/{study_id}/workspace/archive")
    def download_workspace_archive(
        study_id: str,
        authorization: str = Header(default=""),
        s: Session = Depends(deps.db),
    ):
        """The uploaded study folder, for a paired participant's extension."""
        cred = deps.resolve_credential(s, authorization)
        if cred is None or cred.study_id != study_id:
            raise HTTPException(401, "a valid session credential is required")
        row = s.get(StudyWorkspace, study_id)
        path = Path(row.stored_path) if row and row.stored_path else None
        if row is None or row.kind != "archive" or path is None or not path.is_file():
            raise HTTPException(404, "this study has no uploaded folder")
        return Response(
            content=path.read_bytes(),
            media_type="application/zip",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{_safe_name(study_id)}-workspace.zip"'
                ),
                "X-Content-SHA256": row.sha256 or "",
                "Cache-Control": "no-store",
            },
        )

    @app.get("/studies/{study_id}/capture-config")
    def get_capture_config(
        study_id: str,
        request: Request,
        sessionId: str | None = None,
        authorization: str = Header(default=""),
        s: Session = Depends(deps.db),
    ) -> dict:
        """
        Session-boundary re-pull of the capture config (FR-INST-21): the extension
        re-fetches this at the start of each session so a protocol change lands
        without re-pairing.
        """
        row = deps.resolve_credential(s, authorization)
        if row is None or row.study_id != study_id:
            raise HTTPException(401, "a valid session credential is required")
        protocol = deps.resolve_study_protocol(s, study_id)
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
