"""Shared storage helpers for the ingest routes and the dry-run simulator."""

from __future__ import annotations

from middleware.db import Event, MetricRow, get_engine


def store_events(s, rows: list[dict], received: str) -> int:
    """Insert event rows idempotently; returns the count actually inserted."""
    if not rows:
        return 0
    engine = get_engine()
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _pg_insert

        stmt = _pg_insert(Event).values(rows).on_conflict_do_nothing()
    else:
        from sqlalchemy.dialects.sqlite import insert as _sq_insert

        stmt = _sq_insert(Event).values(rows).on_conflict_do_nothing(
            index_elements=["session_id", "source", "seq"]
        )
    return len(s.execute(stmt.returning(Event.id)).fetchall())


def store_metric_rows(
    s, rows: list[dict], received: str, flags: list[list[str]] | None = None
) -> int:
    """Insert metric rows idempotently (by ``row_hash``); returns inserted."""
    inserted = 0
    engine = get_engine()
    for i, row in enumerate(rows):
        table = "function_metrics" if "function" in row else "file_metrics"
        _row_vals = {
            "table": table,
            "session_id": str(row.get("sessionId", "")),
            "participant_id": str(row.get("participantId", "")),
            "condition": str(row.get("condition", "")),
            "timestamp": str(row.get("timestamp", "")),
            "schema_version": int(row.get("schemaVersion", -1)),
            "row": row,
            "row_hash": MetricRow.hash_row(table, row),
            "flags": flags[i] if flags else [],
            "received_at": received,
        }
        if engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as _pg_insert

            stmt = _pg_insert(MetricRow).values([_row_vals]).on_conflict_do_nothing()
        else:
            from sqlalchemy.dialects.sqlite import insert as _sq_insert

            stmt = _sq_insert(MetricRow).values([_row_vals]).on_conflict_do_nothing(
                index_elements=["row_hash"]
            )
        inserted += len(s.execute(stmt.returning(MetricRow.id)).fetchall())
    return inserted
