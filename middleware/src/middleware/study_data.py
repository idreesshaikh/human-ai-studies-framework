from sqlalchemy import or_, select, union
from sqlalchemy.orm import Session

from middleware.db import Event, MetricRow, SessionBlock, SessionOpen
from middleware.demo import DEMO_SESSION_IDS


class StudyData:
    def __init__(self, loaded_study_id: str | None, auth_mode: str):
        self.loaded_study_id = loaded_study_id
        self.auth_mode = auth_mode

    def synthetic_sessions(self):
        return union(
            select(Event.session_id).where(Event.payload["synthetic"].as_boolean()),
            select(MetricRow.session_id).where(MetricRow.row["synthetic"].as_boolean()),
            select(SessionBlock.session_id).where(
                SessionBlock.session_id.in_(DEMO_SESSION_IDS)
            ),
        )

    def scope(self, study_id: str, include_synthetic: bool = False):
        scoped = union(
            select(SessionOpen.session_id).where(SessionOpen.study_id == study_id),
            select(SessionBlock.session_id).where(SessionBlock.study_id == study_id),
        )
        mapped = union(select(SessionOpen.session_id), select(SessionBlock.session_id))
        adopt = self.auth_mode != "clerk" and self.loaded_study_id == study_id

        def belongs(column):
            predicate = column.in_(scoped)
            if adopt:
                predicate = or_(predicate, column.notin_(mapped))
            if not include_synthetic:
                predicate &= column.notin_(self.synthetic_sessions())
                predicate &= column.notin_(DEMO_SESSION_IDS)
            return predicate

        return belongs

    def rows(
        self, s: Session, study_id: str, include_synthetic: bool = False
    ) -> list[dict]:
        in_this_study = self.scope(study_id, include_synthetic)
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
                "payload": e.payload,
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
        rows.sort(key=lambda r: (r["ts"], r["source"], r["seq"] or 0))
        return rows
