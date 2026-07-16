# Dashboard - the dynamic project manager (`:8000/`)

The study's mission control (FR-DASH-1..8, MP-06): every view is a
**projection over the protocol + the middleware store** - nothing on screen
is hand-maintained state. Svelte 5 + Vite + TypeScript (decision D15);
charts are hand-rolled SVG on d3-scale (D17) following the project's
data-viz conventions.

## Views

| Route (`/study/:id/…`) | View | Requirement |
| ---------------------- | ---- | ----------- |
| `overview` | protocol card, RQ coverage, participant grid with integrity badges | FR-DASH-1 |
| `board` | lifecycle kanban; current phase **computed** from uploaded gate artifacts; click a missing chip to see what satisfies it and upload it | FR-DASH-2 |
| `tasks` | task board: derived cards (unsatisfied gates, uncovered RQs, missing sessions, integrity warnings, un-run recipes) that clear themselves, plus manual todos | FR-DASH-7 |
| `live` | sessions with ingests in the last 5 min - rate sparkline, last event, gap banner (2 s polling) | FR-DASH-3 |
| `sessions/:sid` | swimlane timeline: all legs on one time axis (brush to zoom, hover for payloads, table-view twin) + the agent conversation panel, two-way linked | FR-DASH-4 |
| `metrics` | 9-metric distributions split by condition - every point drawn, per-cell n, small-n honest | FR-DASH-5 |
| `knowledge` | mount points for the papers graph + assistant (built in MP-10) | FR-DASH-8 |

Every chart/card carries a traceability chip ("answers RQ-P4", "gate:
ethics") - click it for the full trace chain (FR-DASH-6).

## Run

```bash
# dev - Vite on :5173, API proxied to the middleware on :8000
npm install
npm run dev

# production - the middleware serves the built SPA itself (NFR-7)
npm run build          # -> dist/, picked up via MIDDLEWARE_DASHBOARD
docker compose up      # or: MIDDLEWARE_DASHBOARD=dashboard/dist uv run python -m middleware
```

Seed demo data (NFR-9) so every view renders without live participants:

```bash
uv run python middleware/scripts/replay_session.py
```

If the middleware sets `MIDDLEWARE_TOKEN`, store the same value in the
browser as `localStorage['middleware.token']`.

## Checks

```bash
npm run check   # svelte-check + tsc + vitest (the gate - keep it green)
npm test        # vitest only: timeline lane assembly + task-card derivation
```

The two logic-heavy pieces are pure modules with component tests
(mega-prompt 06 §4): `src/lib/lanes.ts` (heterogeneous events → swimlane
geometry) and `src/lib/derive.ts` (middleware status doc → task cards).
Views stay thin.
