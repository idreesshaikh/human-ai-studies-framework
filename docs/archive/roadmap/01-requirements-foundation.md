# Mega-Prompt 01 - Requirements Engineering Foundation

> Self-contained: execute this file in a fresh working session at the repo
> root to (re-)execute. Read `docs/archive/roadmap/00-VISION.md` first for the big picture.

**Depends on:** nothing (this is the root of all traceability)
**Status:** ✅ Done (2026-07-11) - deliverables live in `requirements/`

## Context

This is a Masters project in **requirements engineering**. The platform being
built (see `docs/archive/roadmap/00-VISION.md`) claims that a study protocol is a
requirements specification. That claim is only credible if the platform
itself is requirements-engineered: every later phase must trace its work to
requirement IDs defined here. What already exists and constrains the
requirements: `extension/` (VS Code extension, JSONL event schema v2
with `ts`/`participantId`/`condition`/`sessionId` on every row, HTTP sink
ready), `metrics/` (tree-sitter metrics, orchestrator planned in
`metrics/docs/implementation_plan.md`).

## Objective

Produce the complete RE artifact set for the platform, in `requirements/`.

## Deliverables

1. `requirements/README.md` - index + how the artifacts relate.
2. `requirements/glossary.md` - controlled vocabulary (study, protocol,
   instrument, condition, session, phase, gate, recipe, leg, …). Every other
   document uses these terms exactly.
3. `requirements/stakeholders.md` - stakeholder analysis: researcher/PI,
   participant, ethics board, thesis examiner, replicating researcher,
   platform developer. Goals, concerns, and conflicts (e.g. data richness
   vs. participant privacy).
4. `requirements/research-questions.md` - two tiers:
   - Framework RQs (the thesis): can a protocol be captured as a
     machine-readable requirements spec; does end-to-end traceability reduce
     study setup cost and errors.
   - Pilot-study RQs (the evaluation): effect of AI assistance on cognitive
     load, code quality, and behavior.
5. `requirements/srs.md` - the SRS: functional requirements grouped by
   subsystem (protocol, instrumentation, ingestion, dashboard, analysis,
   ethics/consent, traceability) and non-functional requirements
   (non-intrusiveness, data integrity, portability, extensibility, privacy,
   reproducibility). Every requirement has a stable ID (`FR-x.y` / `NFR-n`),
   a MoSCoW priority, and a rationale. Must/Should = the vertical slice;
   Could/Won't = the deferred vision, kept visible.
6. `requirements/traceability.md` - the living matrix: RQ → requirement →
   component → data element → analysis, plus a requirement → implementing
   phase (mega-prompt) → status table that later phases update.

## Acceptance criteria

- Every FR/NFR traces to at least one stakeholder goal and at least one RQ
  (or is explicitly infrastructure supporting one).
- Every mega-prompt 02–09 can cite requirement IDs from the SRS that it
  satisfies - no phase exists without requirements, no Must requirement
  exists without a phase.
- Existing artifacts (Cognitive Overlay schema v2, planned metrics) appear
  in the matrix as already-implemented rows, not retrofitted afterthoughts.
- Documents use glossary terms consistently.

## Verification

- Cross-check: grep the SRS for requirement IDs; confirm each appears in
  `traceability.md`. Confirm each mega-prompt's "RE traceability" section
  cites only IDs that exist.
