# `platform/` — the conversational study designer

The web app where a researcher describes a study idea and the platform
proposes grounded design moves that compile into a protocol draft. React 19
+ Vite + TypeScript + Tailwind v4 + shadcn/ui (vendored, owned in-repo).

This is the new v2 surface. The older operational console in `dashboard/`
(Svelte) stays as-is until this app reaches feature parity view by view.

## What's built so far

The design-conversation surface, runnable with **no backend and no LLM
key**. A researcher types an idea; the platform replies with grounded
design-move cards (accept/reject, keyboard `a`/`r`) and paper
recommendations; accepted moves compile into a live protocol-draft rail
with a completeness meter.

With no LLM configured the conversation runs on `src/lib/designStub.ts` —
a deterministic scripted assistant, not throwaway mock data. It's the real
fallback path, and the backend swaps in behind the same shapes later.

Still to come: loading the real paper corpus and matching against it, the
study-template registry with statistical plans, and moving compilation +
storage server-side.

## Commands

```bash
npm install
npm run dev        # dev server at localhost:5173
npm run check      # typecheck + lint + verify + build (the gate)
npm run verify     # runs the checks in scripts/verify-slice1.mjs
npm run build      # production build (served by the middleware)
```

Keep `npm run check` green before committing.

## Conventions

- **Design tokens are the source of truth.** All colour, motion, and radius
  values live in `src/styles/tokens.css`; components use them via Tailwind
  utilities or `var()`. `scripts/lint-no-raw-literals.mjs` fails the build
  on a raw hex/ms/px in a component.
- **Accessible by default.** Light and dark themes both meet WCAG AA
  contrast; `prefers-reduced-motion` turns off animation with no loss of
  function; the conversation is fully keyboard-operable.
- **The compiler is deterministic.** `src/lib/compiler.ts` is a pure
  `(draft, acceptedMoves) → draft'` — no LLM — so replaying the same moves
  always yields the same draft (`npm run verify` checks this).
- **Citations are honest.** Every design move shows its source papers or is
  labelled "unsourced"; the assistant only cites papers it actually holds.

## Layout

```
src/
  components/ui/            base components (button, card, badge)
  components/conversation/  MoveCard, GroundingChip, RecommendationCard,
                            SlotMeter, DraftRail, StreamingTurn, …
  lib/types.ts              the conversation domain model
  lib/designStub.ts         the deterministic no-LLM assistant
  lib/compiler.ts           the move → draft compiler
  styles/tokens.css         the only home for raw design values
scripts/
  lint-no-raw-literals.mjs  token-system guard
  verify-slice1.mjs         behavioural checks
```
