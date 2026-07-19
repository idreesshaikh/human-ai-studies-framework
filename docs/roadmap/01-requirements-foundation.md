# Phase 01 — Requirements & research foundation

> Read first: `docs/VISION.md`, `requirements/README.md`.
> **Satisfies:** RQ-F1..F4, NFR-10, NFR-11. **Status:** ✅ built.

## The idea

The whole platform rests on one claim — *a study protocol is a requirements
specification* — so the project requirements-engineers itself. This phase lays
the traceability spine every later phase hangs off: a controlled vocabulary, a
stakeholder analysis, the research questions, the SRS as the index of record,
the reuse-decision log, and the living traceability matrix. No feature exists
without a requirement ID; the matrix is the status of record.

## What it builds

`requirements/`:
- `glossary.md` — the controlled vocabulary every document and identifier uses
  (`participant` not `user`, `condition` not `group`, `recipe` not `script`).
- `stakeholders.md` — S1–S7, their goals, and the documented trade-offs.
- `research-questions.md` — framework RQs (the thesis) + pilot RQs (evaluation)
  + demonstrator RQs.
- `srs.md` — functional + non-functional requirements with MoSCoW; the index of
  record, parsed live by the platform (`/requirements`, FR-DASH-9).
- `build-vs-adopt.md` — every reuse decision (adopt/adapt/build/reject) with
  rationale (NFR-10).
- `traceability.md` — RQ → requirement → component → status, kept current.
- `specs/` — detailed family specs with numbered fit criteria.

## Acceptance

- Every requirement has a stable ID; the SRS ↔ traceability audit closes in
  both directions.
- Public surfaces read as a product (plain language, NFR-11); requirement IDs
  live in `requirements/`, `docs/roadmap/`, and code comments only.

## Verification

- The `redocs` parser reads `srs.md` + `glossary.md` without drift
  (`test_redocs.py`).
- `AGENTS.md` regenerates from these documents and the CI drift gate is green.
