# Mega-Prompt 06 - Dashboard: the Dynamic Project Manager

> Self-contained: execute this file in a fresh working session at the repo
> root. Read first: `roadmap/00-VISION.md`, `requirements/srs.md`
> (FR-DASH-*), the middleware API (`middleware/README.md`), and the pilot
> protocol (`protocol/examples/pilot-study.yaml`).

**Depends on:** 02 (lifecycle), 04 (middleware API)
**Satisfies:** FR-DASH-1…8 (8 partially, completed by MP-10); NFR-7, NFR-9
contributions. **Sprint day 5.**
**Status:** ✅ Done (2026-07-11) - see the MP-06 row in
`requirements/traceability.md` (FR-DASH-1–7 ✅, FR-DASH-8 🔶 until MP-10;
deviations noted there)

## Context

The supervisor's headline feature: not a chart page but the study's
**mission control / dynamic project manager**. Everything on screen is a
*view over the protocol + the middleware store* - nothing is hand-maintained
state. The RE thread is literal here: the dashboard renders the
requirements-status of the study (which gates unsatisfied, which RQs
uncovered, which data missing) the way a build dashboard renders CI.

## Deliverables

### 1. App skeleton (`dashboard/`)

**Svelte 5 + Vite + TypeScript** (D15 - supersedes D11's React choice;
scaffold with `npm create vite@latest . -- --template svelte-ts` inside
`dashboard/`). Talks only to the middleware REST API (bearer token).
Production mode: built SPA served *by* the middleware (one process, NFR-7);
dev mode: Vite proxy to :8000. Client-side routing over
`/study/:id/{overview|board|tasks|live|sessions/:sid|metrics|knowledge}`.
Follow the project's data-viz conventions (consistent palette, labeled
axes, honest scales, light/dark support) in all chart code; one charting
approach throughout - prefer LayerChart (or hand-rolled SVG with d3-scale,
which Svelte does exceptionally cleanly) over React-ecosystem libraries.

### 2. Views

- **Overview** (FR-DASH-1) - protocol card (title, version, researchers,
  ethics ref), RQ list with per-RQ coverage status (recipes planned/ran),
  participant grid: planned vs. collected sessions per condition, with
  integrity badges (gap-free / gaps / flagged rows).
- **Lifecycle board** (FR-DASH-2) - columns = the seven phases; the current
  phase is *computed* by the lifecycle engine via the middleware, never
  hand-set. Each phase column lists its gate artifacts with
  satisfied/missing chips; clicking a missing chip shows what would satisfy
  it (file upload, approval record, N sessions collected…).
- **Task board - the project manager** (FR-DASH-7, the centerpiece):
  - *Derived cards* (auto): one card per unsatisfied gate artifact, per RQ
    with no runnable recipe (requires-check failing), per participant
    below planned session count, per open integrity warning (seq gaps,
    unknown-participant flags), per un-run recipe after data-collection.
    Each card shows: what, why (requirement/protocol clause it traces to),
    and how to clear it. Cards **clear themselves** when the middleware
    reports the condition satisfied - the board is a projection, not a
    database.
  - *Manual cards*: researcher-added todos (title, note, done) - the only
    mutable dashboard state, stored via a small middleware endpoint.
  - Columns: `Blocked / To do / Waiting on data / Done (auto-archived)`.
- **Live sessions** (FR-DASH-3) - sessions with ingests in the last 5 min:
  event-rate sparkline, last event type, seq-gap warning banner. Poll the
  middleware (2 s interval); WebSockets are gold-plating at this scale.
- **Session timeline** (FR-DASH-4 - the thesis screenshot) - one session as
  horizontal swimlanes on a shared time axis: fatigue responses (with
  Likert value), stuck episodes (spans), edit bursts (colored by `origin`),
  pastes, `ai_suggestion` accept/reject markers with review-latency
  tooltip, visible-range band, idle spans shaded - plus the **agent lane**
  (MP-12): `agent_turn` markers sized by response length, tool-call ticks,
  `reliance_loop` spans, `workspace_snapshot` ticks, and `task_outcome`
  flags (first-green highlighted). Brush to zoom; hover for payload
  details. The lane set is the four-legs claim in one picture.
- **Conversation view** (with MP-12) - per-session agent transcript
  rendered per the study's content policy: `metadata-only` shows turn
  structure, sizes, and tool calls only; `redacted`/`full` show text.
  Linked both ways with the timeline (click a turn → seek; click a
  reliance loop → highlight its turns).
- **Metrics compare** (FR-DASH-5) - per-metric distribution (violin or
  box + jittered points, small-n honest) split by condition, metric picker
  covering the 9-metric matrix.
- **Knowledge** (FR-DASH-8) - mount points + routing for the literature
  graph and assistant chat panel; the panels themselves are built in MP-10
  (stub with "coming in MP-10" cards if 10 isn't done yet).

### 3. Traceability chips (FR-DASH-6)

Every chart/card carries a small tag ("answers RQ-P4" / "gate: FR-ETH-1")
sourced from the protocol's analysis plan and gate definitions - click →
side panel showing the full trace chain for that element.

### 4. Tests

Component tests for the two logic-heavy pieces: timeline lane-assembly
(interleaving heterogeneous events onto one axis, span vs. point vs. band)
and task-card derivation (given a middleware status fixture → expected
cards). The rest stays thin.

## Acceptance criteria

- With the middleware seeded in demo mode (NFR-9), every view renders real
  data with zero manual setup.
- Lifecycle board shows the pilot protocol blocked at its ethics gate;
  uploading a consent/approval artifact via the UI clears the card and
  advances the computed phase.
- Session timeline shows ≥ 5 event types from ≥ 2 legs on one axis for a
  replayed session; origin coloring visibly distinguishes human/ai/paste
  bursts.
- Task board contains only derived + manual cards; deleting backing data
  (e.g. re-flagging a gap) makes the corresponding card reappear.

## Verification

- Seed → `docker compose up` → walk each route; screenshot overview, task
  board, and timeline for the thesis (browser tools). Component tests
  green. Update `roadmap/00-VISION.md` tracker +
  `requirements/traceability.md` (FR-DASH-1–7 → ✅, FR-DASH-8 → 🔶 until
  MP-10).
