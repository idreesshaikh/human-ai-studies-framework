# `platform/` — the web app

The sole frontend: a researcher describes a study idea and the platform
proposes grounded design moves that compile into a protocol draft, then runs
the study through to a paper. React 19 + Vite + TypeScript + Tailwind v4 +
shadcn/ui (vendored, owned in-repo). The middleware serves the built app at
`/` — one process is the whole stack (FR-PLAT, FR-CONV, NFR-12).

## What's here

- **The design conversation** — type an idea; the platform replies with
  grounded design-move cards (accept/reject, keyboard `a`/`r`) and paper
  recommendations; accepted moves compile into a live protocol-draft rail
  with a completeness meter.
- **The study workspace** (tabs): **Library** — live paper ingest
  (arXiv/DOI/PDF), the citation constellation, and the grounded assistant;
  **Data** — honest per-condition metric shapes and session integrity;
  **Lifecycle** — the phase/gate board.
- **Projects, roles, hero, members**, and the evolution surfaces (amendment
  banner + history, feedback → platform findings).

Everything is explorable with **no backend and no LLM key**: the conversation
runs on a deterministic scripted assistant (`src/lib/designStub.ts`), and the
study surfaces fall back to a curated offline seed. Live actions wire to the
middleware where it's running; the backend swaps in behind the same shapes.

## Commands

```bash
npm install
npm run dev        # dev server at localhost:5173
npm run check      # typecheck + lint + verify + build (the gate)
npm run verify     # runs the verify-*.mjs harnesses
npm run build      # production build (served by the middleware)
```

Keep `npm run check` green before committing.

## Conventions

- **Design tokens are the source of truth.** All colour, motion, and radius
  values live in `src/styles/tokens.css` (including the dataviz chart
  palette); components use them via Tailwind utilities or `var()`.
  `scripts/lint-no-raw-literals.mjs` fails the build on a raw hex/ms/px in a
  component.
- **Accessible by default.** Light and dark themes both meet WCAG AA
  contrast; `prefers-reduced-motion` turns off animation with no loss of
  function; surfaces are keyboard-operable. Consent/ethics surfaces never
  animate.
- **The compiler is deterministic.** `src/lib/compiler.ts` is a pure
  `(draft, acceptedMoves) → draft'` — no LLM — so replaying the same moves
  always yields the same draft (`npm run verify` checks this).
- **Citations are honest.** Every design move shows its source papers or is
  labelled "unsourced"; the assistant only cites papers it actually holds.
- **Stable `data-agent` names** on landmarks and decision points, documented
  in `docs/agent-annotations.md` and kept in sync by a lint (FR-AGF-3).

## Layout

```
src/
  pages/                    Hero, Projects, ProjectHome, StudyHome, Members, …
  components/conversation/  the design conversation + evolution surfaces
  components/library/        LibraryTab, Constellation, Assistant
  components/charts/         DataTab, LifecycleTab, MetricStrip
  components/shell/          AppFrame, ProjectSwitcher, RoleGate
  components/ui/             vendored shadcn primitives
  lib/                       api/studyApi clients, compiler, stubs, forceLayout
  styles/tokens.css          the only home for raw design values
scripts/                    lint + verify harnesses
```
