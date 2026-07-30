# design-sync notes: platform DS

Repo-specific gotchas for future re-syncs. One bullet per gotcha.

- **`platform/` is a Vite *app*, not a library.** No `exports`/`module`/`main`
  and `dist/` is an app build (not `dist/index.es.js`). The converter runs in
  **synth-entry mode** from `src/` (esbuild reads `tsconfig.app.json` `paths`,
  so `@/…` aliases resolve). There is no library build to run.
- **CSS comes from the compiled app bundle.** Tailwind v4 emits utilities only
  for classes it sees at build time, so `cfg.cssEntry` points at the compiled
  `platform/dist/assets/index-*.css` (holds the utility set + `@theme` mapping)
  and `cfg.tokensGlob` at `src/styles/tokens.css` (the `var(--*)` source).
- **Providers:** `src/lib/session.tsx` exports `ApiProvider` (API client) →
  `SessionProvider` (fetches `api.me()` on mount, network). Leaf `ui/`
  components need neither; shell/members/ConversationView read `useSession`/
  `useApi`. `srcDir=src/components` excludes `src/lib/session.tsx`, so those
  providers are NOT in the bundle; wire them via `cfg.extraEntries` if a
  shell preview needs one. Provider wiring resolved during the self-heal loop.

## Build setup (per-clone, the converter can't self-discover these)
- **Self-symlink required:** `platform` is not installed in its own
  `node_modules`, so `PKG_DIR = node_modules/platform` doesn't exist and the
  build dies in `dts.mjs`. Fix (recreate on every fresh clone):
  `ln -sfn .. platform/node_modules/platform` (points `PKG_DIR` at `platform/`).
- **All `cfg.*` path fields resolve relative to `PKG_DIR` (= `platform/`)**, NOT
  the repo root: `cfgPath()` always does `resolve(PKG_DIR, rel)` and only uses
  the "root" arg for the containment check. So `tsconfig:"tsconfig.app.json"`,
  `cssEntry:"dist/assets/index-*.css"`, `tokensGlob:"src/styles/tokens.css"`,
  `srcDir:"src/components"`: all bare, no `platform/` prefix.
- **`srcDir:"src/components"`** (not `src`) scopes synth-entry discovery to the
  reusable components and excludes `main.tsx` (which `@import`s the unbundlable
  Tailwind-source `index.css`), `App.tsx`, and `pages/*` (full screens).
- **Build command (from repo root):**
  `node .ds-sync/package-build.mjs --config .design-sync/config.json --node-modules platform/node_modules --out ./ds-bundle`
- **`import.meta` warning** (`api.ts` VITE env) is expected under the IIFE
  bundle and harmless; previews don't call the API.

## Authoring conventions that worked (for future preview authoring)
- Each preview export is a zero-prop PascalCase component; import DS parts from
  the bare specifier `"platform"`.
- Layout glue via inline `style={{}}` only (the shipped CSS carries just the
  classes the app already uses); the sole safe utility class is `"tabular"`.
- Compose compound sub-parts inside their parent: Card sub-parts inside
  `<Card>`; THead/TBody inside a full `<Table>`; open Radix overlays with
  `defaultOpen`.
- Content is study-domain (P-01, AI-assisted/Control, real corpus papers from
  `platform/src/lib/designStub.ts`), never foo/bar/test.
- Provider-dependent shell components wrap in `ApiProvider`/`SessionProvider`/
  `MemoryRouter` imported from `"platform"` (via `cfg.extraEntries`) so React/
  router context instances match the bundle's.

## Scope decisions
- **3 provider/router-bound app-chrome pieces ship as floor cards** (fully
  importable, no authored preview): `AppFrame`, `InviteDialog`, `MembersTable`.
  Root cause: the repo-local `./src/lib/session.tsx` provider, when exposed via
  `extraEntries`, bundles a SECOND `SessionContext`/`ApiContext` instance that
  doesn't dedupe against the components' `@/lib/session` alias import, so a
  preview's `SessionProvider` and the component's `useSession` read different
  contexts ("must be used inside <SessionProvider>"). `react-router-dom` (a bare
  node_modules specifier) dedupes fine, so `ProjectSwitcher` renders. To author
  these later: unify the module (e.g. add session.tsx to the same synth-entry
  graph as the components, or a re-export that resolves through the `@/` alias).
- **6 newer components excluded via `componentSrcMap: null`**: `Assistant`,
  `Constellation`, `DataTab`, `LibraryTab`, `LifecycleTab`, `MetricStrip`. They
  appeared in `src/components` mid-sync (another agent building the Phase B/C
  surfaces) and are router/data-bound (render "Not Found" without routes). They
  were outside this sync's validated scope: **author + include them on a future
  re-sync once they stabilize** (drop the null entries).

## Known render warns
- None outstanding. Final validate: 50/50 previews render cleanly, bad=0,
  thin=0, variantsIdentical=0, 3 floor cards (the three above).

## CSS stability (IMPORTANT: bit us mid-run)
- Tailwind v4's compiled CSS lives in `platform/dist/assets/index-<hash>.css`,
  and the hash changes on **every** `vite build`. During this sync another
  agent rebuilt `platform/dist`, the hash moved, `cfg.cssEntry` went stale, and
  the build silently wrote a placeholder `_ds_bundle.css` (all previews render
  UNSTYLED). Fix adopted: keep a **stable copy** at `platform/.ds-shipped.css`
  (gitignored) and point `cfg.cssEntry: ".ds-shipped.css"` at it, decoupling
  the sync from dist-hash churn.
- **On every re-sync: refresh the stable copy first**:
  `cp "$(ls -t platform/dist/assets/index-*.css | head -1)" platform/.ds-shipped.css`;
  then run `package-build.mjs`. (A future improvement: give Vite a
  stable-named CSS output so this copy step goes away.)

## Re-sync risks
- **Stale `.ds-shipped.css`**: it's a build artifact snapshot; if the app's
  styles changed since it was copied, previews render against old CSS. Always
  refresh it from the latest `dist/assets/index-*.css` before a re-sync build.
- **Concurrent agents rebuild `platform/dist`**: this repo is edited by
  several agents at once; a mid-sync `vite build` moves the CSS hash (see
  above). The stable-copy indirection makes the sync robust to it.
