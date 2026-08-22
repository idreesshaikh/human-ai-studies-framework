# Project Guide  -  the platform

This is the guide for working *on* the frontend. The [README](README.md)
covers what the app is and how to run it; this covers how it's built  -
the data layer, the state model, the parts that mirror the server, and the
conventions the build enforces.

## 1. Stack and the philosophy behind it

React 19 + Vite + TypeScript + Tailwind v4 + shadcn/Radix, routed with
react-router. What's notable is what's **absent**: no state-management
library, no data-fetching library, no chart library. Those are deliberate.

- **shadcn components are vendored and owned** (`src/components/ui/`). They're
  edited in-repo, not consumed as a dependency  -  the look is ours, not a
  library's default.
- **Charts are hand-built SVG** (`src/components/charts/`, `src/lib/
  forceLayout.ts`). One design-token system covers the app and the charts, so
  a chart can't drift from the rest of the UI.
- **Data fetching is hand-rolled** (`useAsync` + fetch clients). This keeps the
  bundle small and the behaviour explicit, at the cost of writing the
  loading/error/retry logic ourselves.

If you're reaching for a new dependency, that's a `requirements/build-vs-adopt.md`
decision first  -  the leanness is a requirement (NFR-10), not an accident.

## 2. Architecture at a glance

```mermaid
flowchart TD
    subgraph client [platform/ SPA]
      pages[pages/ + components/] --> shell[useApi()  -  Api interface]
      pages --> study[studyApi / conversationApi / templatesApi]
      shell --> backends{VITE_API_BASE?}
      backends -->|live| http[HttpBackend]
      backends -->|offline| mem[InMemoryBackend]
      study --> fetchc[per-call fetch + OfflineError]
    end
    http --> mw[Middleware :8000]
    fetchc --> mw
    mem -. seeded demo .-> pages
```

The middleware serves the built app at `/`, so in production the API is
same-origin and `VITE_API_BASE` is empty. Set it only for a separate-origin
deployment.

## 3. The data layer  -  two patterns, know which is which

This is the part that isn't obvious from the folder names. There are **two
different ways** a component talks to the backend.

### Pattern A  -  the `Api` interface (the shell)

`src/lib/api.ts` defines one `Api` interface (`me`, `listProjects`,
`createStudy`, `members`, `createInvitation`, `mintEnrollmentTokens`, …) with
**two implementations**:

- `HttpBackend`  -  talks to the middleware.
- `InMemoryBackend`  -  a self-contained fake that seeds a couple of projects
  and the demo, so the whole shell is explorable and testable with no server.

`getApi()` returns `withOfflineFallback(new HttpBackend(base), new
InMemoryBackend())`: live calls go to the middleware, and a network failure
falls through to the fake. Components reach it through context  -
`ApiProvider` at the root, `useApi()` in a component. This pattern covers
**projects, studies, members, invitations, enrollment, preferences**.

### Pattern B  -  standalone fetch clients (the study workspace)

`studyApi.ts`, `conversationApi.ts`, and `templatesApi.ts`
are **not** part of the `Api` interface and are **not** wrapped in
`withOfflineFallback`. Each is a small module with its own `req()` helper and
shares one `OfflineError` (exported from `studyApi.ts`). When the server is
unreachable they *raise* `OfflineError`, and the calling component decides
what to show (usually a calm "you're offline" note, sometimes a fall-through
to a stub). This pattern covers **the design conversation, the Library, the
Data tab, and the templates surfaces**.

Why two patterns: the shell benefits from a swappable fake so the app is fully
navigable offline; the workspace surfaces are richer and handle offline
per-action rather than pretending a fake dataset is real.

### The auth seam

Every client gets its bearer token through one indirection:
`tokenProvider` (a module-level function in `api.ts`), installed by
`setTokenProvider()`. `auth.tsx` installs the real getter once sign-in
resolves; until then it returns `null`. A `401` calls `notifyUnauthorized()`,
which raises the sign-in surface. This is why auth is pluggable (token or
Clerk) without any client knowing which mode is active  -  see §7.

## 4. State and data fetching

There is no store library. State lives in three places:

- **Local component state** (`useState`) for view state  -  the conversation
  thread, form inputs, which tab is open.
- **React Context** for two cross-cutting things: the `Api` instance
  (`useApi`) and the signed-in session (`useSession`, holds `me` and the
  project role). Both live in `src/lib/session.tsx`.
- **`useAsync(loader, deps)`** (`src/lib/useAsync.ts`)  -  the one data-fetching
  primitive. It runs a loader, tracks `{ data, loading, error, reload }`, and
  cancels stale results with a `live` flag.

One subtlety worth knowing: a page can mount and fire its first load *before*
Clerk has installed the token provider, get a `401`, and be stuck showing that
error. `useAsync` listens for a `CREDENTIAL_READY_EVENT` and reloads when auth
catches up. If you write a data loader that seems to "stick" on a stale error
right after sign-in, this is the mechanism to look at.

`useAsync` has no cache and no request dedup  -  two components loading the same
resource make two requests. That's a deliberate simplicity trade; keep it in
mind before fetching the same thing in several places.

## 5. Routing and adding a page

Routes are declared in `src/App.tsx`. Public routes (`/`, invitation accept)
sit outside the authenticated `Shell`; everything else renders inside it.

One non-obvious rule, called out in `App.tsx`: the projects list is at `/home`,
**not** `/projects`  -  because `/projects` is the backend's API path, and a
same-path SPA route can't coexist with an API route on a hard navigation
(refresh, bookmark). When you add a page, don't collide its path with a
middleware route.

To add a page: create it under `src/pages/`, add a `<Route>` in `App.tsx`
(inside `<Shell>` if it needs auth), and link to it. If it loads data, use
`useAsync`; if it's a shell concern, add the method to the `Api` interface (and
to *both* backends); if it's a workspace concern, add it to the relevant fetch
client.

## 6. The parts that mirror the server (read this before editing them)

Two client modules deliberately re-implement server logic so parts of the app
work without a live backend. They must stay in sync with their server
counterparts:

| Client | Mirrors (server) | What it does |
| --- | --- | --- |
| `lib/compiler.ts` | `middleware/compiler.py` | Folds accepted moves into a draft  -  pure, deterministic. Gives the draft rail its instant preview; the server compile is authoritative. |

**Contributor warning:** these are not generated from the server  -  they're
hand-kept parallels. If you change a compile rule or a move shape on one side,
change the other, or the optimistic preview will quietly disagree with the
authoritative result. `npm run verify` checks the compiler's determinism but
does **not** currently check client/server agreement.

**The conversation has no such mirror  -  on purpose.** There used to be a
client-side scripted assistant (`designStub.ts`) that answered from a keyword
script whenever the server was unreachable. It was removed deliberately: a
script that reads on screen exactly like the real conversation is an
impersonation of it. Now the conversation needs the server (and a language
model); without them it shows an honest offline notice rather than faking a
reply. The only remnant is `conversationOpening.ts`  -  the opening prompt,
which asks a question and claims nothing. So the shell and study surfaces
degrade to seeded/offline data, but the conversation degrades to honesty, not
to a stub.

## 7. Auth (three modes)

The middleware announces its mode via `GET /auth/config`; the client adapts:

- **none**  -  no sign-in; every call is anonymous.
- **token**  -  paste a bearer token; it's stored where `tokenProvider` looks.
- **clerk**  -  clerk-js is hot-loaded from the Clerk instance's own domain (no
  npm runtime dependency; `@clerk/clerk-js` stays a types-only dev dep), and
  the live JWT getter is installed into `tokenProvider`. The paste-a-token
  fallback still works in this mode.

All of this lives in `src/lib/auth.tsx`. Because it depends on clerk-js
internals, treat it as fragile  -  verify against Clerk's current loader before
touching it.

## 8. The design system and the gates that enforce it

- **Design tokens are the only home for raw values.** Colour, motion, radius  -
  all in `src/styles/tokens.css`, including the chart palette; type sizes are
  named roles in `src/styles/index.css` (a component sets size through a role,
  not a bare `text-*` utility). Components use tokens via Tailwind utilities or
  `var()`. `scripts/lint-no-raw-literals.mjs` fails the build on a raw
  hex/px/ms  -  or a bare type utility  -  in a component.
- **`data-agent` annotations** on landmarks and decision points make the UI
  legible to agents (FR-AGF-3). They're documented in
  [`docs/agent-annotations.md`](docs/agent-annotations.md) and kept honest by
  `scripts/check-agent-annotations.mjs`.
- **Accessibility is a gate, not a nicety.** Both themes meet WCAG AA;
  `prefers-reduced-motion` disables animation with no loss of function;
  consent/ethics surfaces never animate. `usePrefersReducedMotion` is the hook.
- **`verify-*.mjs`** are behaviour harnesses (slice1, shell, library,
  timeline, layout, constellation, comparator, protocol-path) run by
  `npm run verify`. They are not component unit tests
   -  there is currently no vitest/RTL setup  -  so they check specific invariants
  rather than rendering.

`npm run check` (typecheck + lint + verify + build) is the gate. Keep it green.

## 9. Repository layout

```
src/
  App.tsx                   routes
  pages/                    Hero, Projects, ProjectHome, StudyHome, Members, Settings, …
  components/
    conversation/           the design conversation + Steer (SteerDial)
    library/                LibraryTab, Constellation
    charts/                 DataTab, MetricStrip, SwimlaneTimeline (hand-built SVG)
    shell/                  AppFrame, ProjectSwitcher, RoleGate, SignInScreen
    enrollment/ members/    participant enrollment; project members
    brand/ hero/            brand marks; the self-running demo on `/`
    ui/                     vendored shadcn primitives (owned)
  lib/
    api.ts                  the Api interface + HttpBackend + InMemoryBackend + auth seam
    studyApi / conversationApi / templatesApi   standalone fetch clients
    compiler.ts             client mirror of the server compiler
    conversationOpening.ts  the opening prompt (all that remains of the old design stub)
    steer.ts                the Steer control's levels (register + initiative)
    session.tsx             ApiProvider + SessionProvider (context)
    useAsync.ts             the data-fetching primitive
    forceLayout.ts          the citation-constellation layout
    theme.ts, cn.ts, types.ts
  styles/                   tokens.css (raw design values) + index.css (type-size roles)
scripts/                    lint-no-raw-literals, check-agent-annotations, verify-*.mjs
```

## 10. Conventions and gotchas, in one place

- Keep `npm run check` green before committing.
- No raw colour/px/ms in a component  -  use a token.
- Adding a shell data method means editing **both** backends in `api.ts`.
- Don't collide a route path with a middleware API path (`/home`, not
  `/projects`).
- If you touch `compiler.ts`, check the server counterpart named in §6. Don't reintroduce a scripted conversation stub  -
  its removal was deliberate (§6).
- New dependency → `requirements/build-vs-adopt.md` first.
