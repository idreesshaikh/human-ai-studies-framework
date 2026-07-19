# Phase 03 — Ingestion middleware (the :8000 hub)

> Read first: `requirements/srs.md` §FR-ING, `middleware/README.md`.
> **Satisfies:** FR-ING-1..6, NFR-2, NFR-7. **Status:** ✅ built.

## The idea

Every instrument leg reports to one hub: a FastAPI service on **port 8000**
(the contract every sensor assumes). It accepts event batches unchanged from
the extension's HttpSink, stores them idempotently, detects loss without
preventing it, and exports the joined one-timeline dataset that all analysis
consumes. The hub later grows into the whole platform backend (the conversation
service, the knowledge layer, mining, the manifest) and serves the `platform/`
app at `/` — but the ingestion contract here is the foundation.

## What it builds

`middleware/` (Python package, `python -m middleware`):
- `app.py` — the FastAPI app and routes.
- `db.py` — SQLAlchemy models over one SQLite file; idempotency lives in the
  schema (`UNIQUE(session_id, source, seq)`), so replays are dropped by the DB.
- ingest: `POST /ingest/events` · `POST /ingest/metrics` · `POST /ingest/files`.
- integrity: `GET /sessions/{id}/gaps` reports per-producer `seq` gaps —
  loss is always *visible*, since prevention is best-effort (NFR-2).
- export: `GET /studies/{id}/dataset?format=json|csv` — the joined timeline.
- rows with unknown participant/condition are stored and flagged, never dropped
  (FR-ING-6).

## Acceptance

- Re-sent batches create no duplicates (FR-ING-2).
- A missing event is detectable as a `seq` gap (FR-ING-3).
- `docker compose up` brings the hub up with the pilot protocol + demo seed;
  one process is the whole stack (NFR-7).

## Verification

- `uv run pytest middleware` — idempotent ingest, gap facts, dataset export.
- `scripts/smoke.sh` exercises ingest → dataset → report from a clean bring-up.
