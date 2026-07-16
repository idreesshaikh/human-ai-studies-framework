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

Every chart/card carries a small "i" info toggle - hover for a
plain-language explanation, click for the full trace chain back to the
requirement it answers (FR-DASH-6).

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

## Theme

Light / dark / system, toggled from the nav footer and persisted as
`localStorage['dashboard.theme']`. Both palettes are the design tokens in
`src/app.css` keyed off `data-theme` on `<html>` (a pre-paint script in
`index.html` prevents any flash); charts reference token roles, never raw
hex, so they re-theme for free.

## Iterating the UI in v0 (design loop, D30 rev 2)

The dashboard is a self-contained Vite app, so it can be hosted separately
from the middleware for visual iteration:

1. In Vercel/v0, create a project from this repo with **Root Directory =
   `dashboard`** (keep it disconnected from the production pipeline - Render
   deploys the real app).
2. Point the preview at a live API: set `VITE_API_BASE` to the demo
   middleware's URL at build time.
3. On the middleware side, allow that one origin:
   `MIDDLEWARE_CORS_ORIGINS=https://<preview>.vercel.app` (FR-OPS-6 -
   unset means same-origin only, so nothing is exposed by default).
4. Bring accepted iterations back as ordinary commits; `npm run check` is
   still the gate.

## Checks

```bash
npm run check   # svelte-check + tsc + vitest (the gate - keep it green)
npm test        # vitest only: timeline lane assembly + task-card derivation
```

The two logic-heavy pieces are pure modules with component tests
(mega-prompt 06 §4): `src/lib/lanes.ts` (heterogeneous events → swimlane
geometry) and `src/lib/derive.ts` (middleware status doc → task cards).
Views stay thin.
