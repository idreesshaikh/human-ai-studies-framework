# `platform/`: the web app

The sole frontend: a researcher describes a study idea and the platform
proposes grounded design moves that compile into a protocol draft, then runs
the study through to a paper. React 19 + Vite + TypeScript + Tailwind v4 +
shadcn/ui (vendored, owned in-repo). The middleware serves the built app at
`/`; one process is the whole stack (FR-PLAT, FR-CONV, NFR-12).

> Working on the frontend itself? See [`PROJECT_GUIDE.md`](PROJECT_GUIDE.md)
> for the data layer, the state model, the client/server mirrors, and the
> conventions the build enforces.

## What's here

- **The design conversation**: type an idea; the platform replies with
  grounded design-move cards (accept/reject, keyboard `a`/`r`) and paper
  recommendations; accepted moves compile into a live protocol-draft rail
  with a completeness meter. **Steer** (head of the thread) sets how much the
  assistant drives: register and initiative both move with it, enforced
  server-side, never the rigor of the method itself.
- **The study workspace** (tabs): **Library**: live paper ingest
  (arXiv/DOI/PDF) and the citation constellation;
  **Data**: honest per-condition metric shapes and session integrity;
  **Participants**: mint pairing links, watch who is streaming, and toggle
  what each instrument captures.
- **Projects, roles, hero, members**.

The study surfaces are explorable with **no backend**: they fall back to a
curated offline seed. The design conversation is the exception — it needs a
language model and says so when it has none, rather than answering from a
script that reads like the real thing. Live actions wire to the
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
  `(draft, acceptedMoves) → draft'` (no LLM), so replaying the same moves
  always yields the same draft (`npm run verify` checks this).
- **Citations are honest.** Every design move shows its source papers or is
  labelled "unsourced"; the assistant only cites papers it actually holds.
- **Stable `data-agent` names** on landmarks and decision points, documented
  in `docs/agent-annotations.md` and kept in sync by a lint (FR-AGF-3).
- **Type size is a role, not a utility.** The nine roles in `styles/index.css`
  (`type-title`, `type-body`, `type-quantity`, …) are the only way a
  component sets a font size; `lint-no-raw-literals.mjs` forbids a bare
  Tailwind `text-*` utility for the same reason it forbids a raw hex.
- **Provenance is a mark, never a colour.** A claim's grounding strength is a
  magnitude (size), unsourced is an open ring, superseded is struck through,
  a conflict is doubled — so every state survives a greyscale print and a
  colour-blind reader. One accent fill marks the single next action per
  region; a nav item, tab, or selected row is a *position* (an axis rule),
  never a fill.

## Layout

```
src/
  pages/                    Hero, Projects, ProjectHome, StudyHome, Members, …
  components/conversation/  the design conversation
  components/library/        LibraryTab, Constellation
  components/charts/         DataTab, MetricStrip, SwimlaneTimeline
  components/enrollment/     EnrollmentPanel, MintDialog, LiveSessions
  components/members/        MembersTable, InviteDialog
  components/shell/          AppFrame, ProjectSwitcher, RoleGate
  components/brand/          PhoenixMark
  components/hero/           HeroShowcase (the self-running demo on `/`)
  components/ui/             vendored shadcn primitives
  lib/                       api/studyApi clients, compiler, extension, forceLayout
  styles/tokens.css          the only home for raw design values; the world
scripts/                    lint + verify harnesses
```
