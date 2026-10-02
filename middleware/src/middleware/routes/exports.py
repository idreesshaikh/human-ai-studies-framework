import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from protocol.errors import ProtocolError
from sqlalchemy.orm import Session

from middleware.exports import notebook_archive, replication_archive
from middleware.measurements import measurement_report


def export_router(db, authorize, resolve_protocol, study_data):
    router = APIRouter(
        prefix="/studies/{study_id}", dependencies=[Depends(authorize("view"))]
    )

    def protocol_for(s, study_id):
        protocol = resolve_protocol(s, study_id)
        if protocol is None:
            raise HTTPException(
                409,
                "This study has no compiled protocol. Apply a draft in Setup.",
            )
        return protocol

    @router.get("/dataset")
    def dataset(
        study_id: str,
        format: str = "json",
        includeSynthetic: bool = False,
        s: Session = Depends(db),
    ):
        rows = study_data.rows(s, study_id, includeSynthetic)
        if format == "json":
            return {"studyId": study_id, "rows": rows}
        if format != "csv":
            raise HTTPException(400, "format must be 'json' or 'csv'")
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        header = [
            "source",
            "ts",
            "sessionId",
            "participantId",
            "condition",
            "taskId",
            "schemaVersion",
            "type",
            "seq",
            "flags",
            "payload",
        ]
        writer.writerow(header)
        for row in rows:
            writer.writerow(
                [
                    json.dumps(row[key]) if key in {"flags", "payload"} else row[key]
                    for key in header
                ]
            )
        return PlainTextResponse(buffer.getvalue(), media_type="text/csv")

    @router.get("/measurements")
    def measurements(study_id: str, s: Session = Depends(db)):
        return measurement_report(
            protocol_for(s, study_id), study_data.rows(s, study_id)
        )

    @router.get("/notebook")
    def notebook(
        study_id: str, includeSynthetic: bool = False, s: Session = Depends(db)
    ):
        content = notebook_archive(
            protocol_for(s, study_id),
            study_data.rows(s, study_id, includeSynthetic),
            study_id,
        )
        return download(content, "application/zip", f"{study_id}-notebook.zip")

    @router.get("/replication-kit")
    def replication_kit(
        study_id: str, includeSynthetic: bool = False, s: Session = Depends(db)
    ):
        try:
            content = replication_archive(
                protocol_for(s, study_id),
                study_data.rows(s, study_id, includeSynthetic),
                study_id,
            )
        except ProtocolError as exc:
            raise HTTPException(422, str(exc)) from exc
        return download(
            content, "application/gzip", f"{study_id}-replication-kit.tar.gz"
        )

    return router


def download(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
