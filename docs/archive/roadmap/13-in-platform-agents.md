# Mega-Prompt 13 - In-Platform Agents (FR-META-3)

> Self-contained: execute this file in a fresh working session at the repo
> root. Read first: `docs/archive/roadmap/00-VISION.md`, `requirements/srs.md`
> (FR-META-3, FR-ETH-4, FR-META-1/2), `middleware/src/middleware/assistant.py`
> (the D32 Mistral tool-use loop and the FTS5 index it searches), and
> `middleware/src/middleware/app.py` (findings scan, task cards).

**Depends on:** 04 (middleware), 10 (knowledge layer + FTS5 index),
11 (findings log + retrospective). **Satisfies:** FR-META-3.
**Elicited:** owner, 2026-07-16 ("things are inherently part of the
platform to use" - automation must be built-in, not hand-run).
**Status:** Not started

## The idea

The platform already has every ingredient of an autonomous colleague -
an inverted-index knowledge base (FTS5 over ingested papers), a bounded
tool-use loop (D32), a findings log (FR-META-1), a self-derived task board
(FR-DASH-7), and an inert-proposal discipline (FR-META-2). MP-13 wires
them into **agents**: named, scheduled workflows the middleware runs by
itself and whose output lands in the UI as cards and proposals.

Non-negotiable bounds, inherited verbatim:

- **FR-ETH-4:** every agent sees only what the assistant sees - papers,
  protocol, aggregates. No new tool may return a row-level participant
  event. The grep-the-output test pattern extends to every agent's output.
- **Human gate (FR-META-2 discipline):** agents *propose*; they never
  mutate requirements, protocol, or data. Their writes are limited to
  findings rows, task cards, and proposal documents.
- **NFR-1:** agent failures are swallowed, counted, and reported as
  findings - an agent can never take down ingest or block a session.
- **Offline-degradable:** without `MISTRAL_API_KEY`, LLM-backed agents
  skip with a logged notice; rule-based agents keep running.

## Part A - The agent runtime (middleware)

1. **`middleware/agents.py`** - an agent registry + scheduler:
   - An agent = `{id, description, cadence, run(session, protocol) ->
     AgentReport}`. Cadence is wall-clock (e.g. `hourly`, `daily`) driven
     by a background thread with an injected clock (mocked-timer tests,
     per the extension's pattern).
   - `AgentReport = {findings: [...], cards: [...], proposal: str | None}`
     - the only write surface. Reports are idempotent on
     `(agentId, contextHash)` so re-runs never duplicate cards.
   - `agent_runs` table: every run's start/end, outcome, and error (the
     ops trail; surfaces in the dashboard).
2. **Endpoints:** `GET /studies/{id}/agents` (registry + last runs),
   `POST /studies/{id}/agents/{agentId}/run` (manual trigger - the UI's
   "run now" button), all behind view auth.

## Part B - The first three agents

1. **Integrity sentinel** (rule-based, no LLM): runs the existing
   findings scan (seq gaps, gate blocks) plus recipe-coverage checks on a
   cadence; files findings/cards exactly as the manual
   `POST /findings/scan` does today. This is mostly wiring - the scan
   logic already exists.
2. **Literature scout** (LLM + citation API): for each ingested paper,
   re-harvests the citation neighbourhood (respecting the 1 req/s pacing;
   cached responses make re-runs cheap), diffs against the stored graph,
   and drafts a short **digest** - "3 new highly-cited papers cite your
   core reference" - grounded via `search_papers` over the FTS5 index,
   every claim cited. Output: one task card + a digest document.
3. **Retrospective drafter** (LLM): watches lifecycle transitions; when a
   phase completes, runs the existing `analysis retrospective` collection
   + drafting path server-side and files the proposal as a card linking
   to the inert document.

## Part C - Dashboard surface

- An **Agents panel** (Task board view or its own view): each agent with
  its description, last run, next run, outcome badge, and a "run now"
  button; failures show the finding they filed. Plain-language info
  toggles like every other panel.
- Agent-produced cards carry an agent byline ("filed by literature
  scout") so humans always know what was machine-initiated.

## Acceptance criteria

- With the demo seed and a mocked clock, the sentinel files the seeded
  seq-gap finding within one simulated cadence tick, idempotently across
  three ticks.
- The scout, run against recorded S2 fixtures, produces a digest whose
  every sentence carries a `[paper-ref §chunk]` citation; the
  grep-the-output test proves no participant identifiers appear in any
  agent artifact.
- Killing the Mistral key mid-run degrades: LLM agents log-and-skip,
  the sentinel still runs, ingest latency is unaffected.
- `GET /studies/{id}/agents` powers the panel; manual trigger works from
  the UI with the busy/buffering pattern (FR-LIT-6 style).

## Verification

`uv run pytest middleware` (agent runtime with mocked clock + fixtures),
`npm run check` in `dashboard/`, one live smoke: compose up, wait one
cadence tick (shortened via env), see the sentinel's card appear in the
task board with its agent byline, then flip the FR-META-3 rows in
`requirements/traceability.md` and log the phase completion.
