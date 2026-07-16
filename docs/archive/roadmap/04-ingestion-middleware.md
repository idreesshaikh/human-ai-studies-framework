# Mega-Prompt 04 - Ingestion Middleware

> Self-contained: execute this file in a fresh working session at the repo
> root. Read `docs/archive/roadmap/00-VISION.md` and `requirements/srs.md` first.

**Depends on:** 01 (requirement IDs); pairs naturally with 02 (protocol)
**Status:** ✅ Done (2026-07-11)

## Context

The single most leveraged missing piece. The Cognitive Overlay already ships
a batching `HttpSink` (`extension/src/vscode/sinks.ts`) that POSTs
JSONL study events - schema v2, every row stamped with
`v/ts/mono/sessionId/participantId/condition/seq/type/payload` - but nothing
listens yet. Static metrics (Mega-Prompt 03) will emit JSONL with the same
join keys. This phase builds the service that unifies all legs into one
queryable store.

## RE traceability

Satisfies FR-ING-1–6 and NFR-2; completes FR-ETH-1 (file store, joining
MP-02's gates); advances FR-META-1 (findings endpoints + auto-logged
integrity flags; full wiring MP-11) and NFR-7 (compose with demo seed +
sonar profile; dashboard joins in MP-06). Rows flipped in
`requirements/traceability.md` on completion (2026-07-11).

## Objective

A FastAPI service `middleware/` with persistent storage, ingest endpoints,
and query endpoints the dashboard (06) and recipes (07) will consume.

## Deliverables

1. **Service** (`middleware/app/`): FastAPI + SQLite via SQLAlchemy (single
   file DB - participants are ≤ dozens; keep Postgres a config swap, not a
   dependency). Listens on **port 8000** (FR-ING-1 - the port
   `extension/docs/developer_behavior_capture.md` and the ActivityWatch-style
   sensor→daemon architecture assume; configurable). Ship a `Dockerfile` +
   `docker-compose.yml` from this phase (NFR-7/9 start here, not on day 7):
   `middleware` service, optional `--profile sonar` SonarQube service, and
   a `demo-seed` one-shot service that replays the sample session so every
   downstream phase has data on bring-up. Also reserve two small endpoint
   groups later phases mount: `/findings` (FR-META-1, wired fully in
   MP-11) and `/tasks` (manual task-board cards, MP-06).
   - `POST /ingest/events` - accepts a JSON array of StudyEvents (match the
     extension's HttpSink payload exactly - read `sinks.ts` before coding).
     Idempotent on `(sessionId, seq)`: re-sent batches must not duplicate.
   - `POST /ingest/metrics` - accepts static-metrics JSONL rows.
   - `POST /ingest/files` - raw artifact upload (session JSONL files,
     consent PDFs) stored on disk, indexed in the DB.
   - `GET /studies/{id}/sessions`, `GET /sessions/{id}/events` (filter by
     type/time), `GET /studies/{id}/dataset` - the joined
     one-timeline export (JSON + CSV) that analysis consumes.
   - `GET /sessions/{id}/gaps` - seq-number gap report per session (the
     extension's `seq` exists precisely for this integrity check).
2. **Protocol awareness** (if 02 is done): on ingest, validate
   `participantId`/`condition` against the study's protocol; unknown values
   are stored but flagged - never dropped (data capture is subordinate to
   the study; mirror the extension's never-lose-data policy).
3. **Schema versioning**: store `v` per event; reject nothing, flag unknown
   versions.
4. **Tests** (pytest + httpx): ingest idempotency, gap detection, dataset
   join across two legs, unknown-participant flagging.
5. **Runbook** (`middleware/README.md`): run locally (`uvicorn`), point the
   extension at it (`cognitiveOverlay.output.httpEndpoint`), smoke-test with
   a bundled sample JSONL replay script (`scripts/replay_session.py`).

## Acceptance criteria

- A real session recorded by the extension in the Extension Development Host
  lands in the DB via the HTTP sink with zero code changes to the extension.
- Replaying the same batch twice yields no duplicates.
- `GET .../dataset` returns overlay events and metrics rows interleaved on
  one timeline for the same participant/condition.

## Verification

- `pytest` green; run the replay script against a live server and show the
  gap report + dataset export. Update `docs/archive/roadmap/00-VISION.md` tracker and
  `requirements/traceability.md`.
