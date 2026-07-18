# Build vs. adopt - decision record (NFR-10)

Every subsystem decides: **adopt** (use as-is), **adapt** (borrow
architecture/code patterns, implement ourselves), **build** (from scratch),
or **reject** (considered, not used - with why). Decisions are appendable,
not editable: supersede with a new row. This record is itself RE evidence
(S4): reuse is an elicitation and trade-off exercise, not a default.

## Decisions

### D1 - Weights & Biases (wandb) - **REJECT (adapt its concepts)**

Considered for: experiment tracking, dashboards, artifact storage.
wandb is the obvious "don't rebuild tracking" candidate - and a bad fit:
(a) its unit of record is an ML *training run*, not a *human session*;
our rows are consented human-subject events, and shipping them to a
third-party cloud violates NFR-5/FR-ETH before the ethics board even asks;
(b) its dashboards can't render our core views (lifecycle gates, task
board, swimlane event timelines); (c) self-hosted wandb is heavier than our
entire stack. **What we take instead of the tool:** its conceptual model -
run ≈ session, artifact ≈ gate artifact, workspace ≈ study - and its
standard: every run reproducible from its logged config, which our protocol
already enforces. If a future study is *about* ML training, wandb ingestion
becomes a new instrument leg (extension point, not scope).

### D2 - Tako (si-codelounge/tako) - **ADAPT** → FR-INST-8, FR-INST-10

Open-source VS Code plugin capturing developer actions incl. AI-completion
accept/reject. We adapt its VS Code API hooking strategy (text-document
mutations + inline-completion lifecycle) into our existing extension rather
than installing it: our events must carry our join keys, schema version,
and sink pipeline, and land in `src/core`-testable logic. Study its source
during MP-05 before writing ours.

### D3 - ActivityWatch (`aw-watcher-vscode`) - **ADAPT** → FR-ING-1, NFR-1

Privacy-first tracker with the exact architecture we standardize on: a
dumb, lightweight in-IDE sensor firing JSON heartbeats to a local daemon.
We adopt the *architecture* (sensor → localhost:8000 middleware,
fire-and-forget, zero typing latency) but not the daemon - our middleware
must be protocol-aware, idempotent on `(sessionId, seq)`, and serve our
dashboard. Their watcher code is the reference for cheap, debounced
window/file heartbeats.

### D4 - WakaTime (`vscode-wakatime`) - **ADAPT** → FR-INST-11, FR-INST-12

Battle-tested logic for two problems we'd otherwise get wrong: active-vs-
idle detection (heartbeat + rolling-window model, so "2h session" doesn't
count 40min of lunch) and language/path filtering. Port the *logic pattern*
into `src/core` (injected clock, unit-tested); their cloud sync is
irrelevant to us.

### D5 - SonarQube Community (Docker) - **ADOPT, degradable** → FR-INST-4

Industry-standard Cognitive Complexity, per `metrics/docs/static_code_metrics.md`.
Adopted via its Web API from a local container as an optional
`docker compose --profile sonar` service; the orchestrator stub-degrades to
NaN with one warning when absent (already planned in
`metrics/docs/implementation_plan.md`). We never reimplement the metric -
comparability to industry baselines is the point of including it.

### D6 - tree-sitter + Radon - **ADOPT** → FR-INST-4 *(already in use)*

tree-sitter for language-agnostic AST queries (future multi-language per
the docs' roadmap); Radon for Halstead and raw/comment metrics. Custom
metrics (nesting penalty, scope distance) are *our* queries on top -
adopted parser, built science.

### D7 - ResearchRabbit - **REJECT (replicate the view, not the service)** → FR-LIT-2

No public API; a closed service can't sit inside a reproducible,
self-hosted framework. What users actually love about it - seed papers →
interactive related-work graph - we rebuild on open data (D8) in our own
dashboard, where nodes can link back to protocol elements (FR-LIT-3),
which ResearchRabbit could never do.

### D8 - Semantic Scholar Graph API - **ADOPT** → FR-LIT-1, FR-LIT-2

Free academic citation API: paper lookup by DOI/arXiv ID, references,
citations, and a recommendations endpoint - exactly the edges the graph
view needs. Metadata-only calls (paper IDs/titles), so NFR-5-compatible.
Rate limits are fine at our scale; cache responses in the middleware DB so
the graph renders offline after first fetch.

### ~~D9 - Zotero (local/web API) - **ADOPT (stretch)**~~ **WITHDRAWN** (2026-07-16) → FR-LIT-5

Built in MP-09 (local read-only API v3 over stdlib `urllib`, no
`pyzotero`); withdrawn with FR-LIT-5 (owner decision): DOI/arXiv/PDF
ingest covers the need. It proved the paper-ingest extension point.
Full narrative in git history.

### ~~D10 - Claude API (Anthropic) - **ADOPT, bounded**~~ **SUPERSEDED by D32** (2026-07-16) → FR-LIT-4, FR-META-2

Powered the knowledge assistant + retrospective (built MP-10 via the
`anthropic` SDK, D22): FR-ETH-4 enforced server-side by a hand-rolled
three-tool loop that cannot see row-level events; graceful degradation
without a key. Superseded by D32 (owner decision: free-tier providers);
the bounds, cite-every-claim prompt, and degradation posture carried
over verbatim. Full narrative in git history.

### D11 - FastAPI + SQLite / ~~React~~ + Vite - **ADOPT** → FR-ING, FR-DASH

Boring, single-laptop-deployable, well-documented. SQLite over Postgres:
participant counts are ≤ dozens; one file *is* the backup strategy (NFR-7).
Postgres remains a config swap if a lab ever scales it. *(Frontend half
superseded 2026-07-11 by D15: Svelte, per maintainer preference.)*

### D12 - Existing Cognitive Overlay - **KEEP & EXTEND** → FR-INST-5/8–12

The behavioral leg extends the built extension (new event types, bumped
`SCHEMA_VERSION`) rather than shipping a second plugin: one install, one
sink pipeline, one core/adapter discipline. `extension/docs/developer_behavior_capture.md`
described a standalone plugin; superseded by this decision - the *capture
list* is unchanged, the *packaging* is unified.

### D13 - Claude Code hooks + transcript JSONL - **ADOPT** → FR-AGENT-1/2

The agent leg's primary source. Claude Code is the only mainstream agent
tool offering lossless, machine-readable capture without scraping: hooks
(PreToolUse/PostToolUse/Stop/…) fire shell commands with structured JSON we
POST to the middleware live, and complete session transcripts persist as
JSONL under `~/.claude/projects/` for post-session import (the completeness
backstop - hooks can miss turns that transcripts keep). Consequence for
study design: the pilot's `ai-assisted` condition standardizes on Claude
Code in the VS Code integrated terminal. Copilot Chat and browser chats
have no equivalent surface (export-only / closed) - they stay behind the
FR-AGENT-4 adapter extension point. Implementer: verify current hook names
and transcript format against the official docs at build time, not memory.

### D14 - git (shadow repo) for workspace snapshots - **ADOPT** → FR-INST-15

Snapshotting = a hidden `--git-dir` shadow repository committing the task
workspace on save + timer. Free time-series storage, diffing, and
reconstruction; no custom snapshot format to invent. The participant's own
git usage (if any) stays untouched - separate git-dir, same worktree.

### D15 - Svelte 5 + Vite - **ADOPT** (supersedes D11's frontend half) → FR-DASH

Maintainer preference with engineering merit for this exact app: the
dashboard is a data-dense, chart-heavy SPA where Svelte's compiled output
and fine-grained reactivity keep live views (2 s polling, streaming
assistant responses) cheap, and its single-file components keep a
one-person codebase small. Same deployment story as before: `vite build` →
static files served by the middleware (NFR-7). Charts via LayerChart or
hand-rolled SVG + d3-scale rather than a React-ecosystem port.

### D16 - uv + Python 3.12 workspace - **ADOPT** → all Python packages

One `uv` workspace at the repo root (`pyproject.toml`, members: metrics,
protocol, middleware, analysis, agent-capture; single shared venv;
`uv sync --all-packages`). Replaces per-directory requirements.txt/venv:
lockfile reproducibility (NFR-6), one-command setup (NFR-9), and pinned
Python 3.12 (`.python-version`). ruff + pytest configured at the root.

### D17 - LayerChart vs hand-rolled SVG + d3-scale - **BUILD (charts), ADOPT (d3-scale)** → FR-DASH-4/5

D15 left the charting approach open (LayerChart *or* hand-rolled). Decided
during MP-06: the centerpiece charts are a swimlane event timeline and a
small-n distribution plot - neither is a standard chart-library shape, so a
component library would be fought, not used. Svelte renders SVG natively;
the only genuinely hard part is scales/ticks, so we adopt **d3-scale**
(~10 kB, zero DOM opinions) and build the marks ourselves following the
project's data-viz conventions (thin marks, hairline grid, table-view
twins, validated palette). LayerChart rejected: a dependency tree for two
bespoke charts.

### D18 - SPA routing library - **BUILD (hand-rolled)** → FR-DASH app skeleton

The dashboard has one fixed route shape
(`/study/:id/{view|sessions/:sid}`). svelte-routing / svelte-spa-router
rejected: a dependency for a 60-line history-API router; SvelteKit rejected
(again, per D15) as a framework swap. Deep links work because the
middleware re-serves the SPA shell for `/study/*` (NFR-7).

### D19 - Vitest - **ADOPT** → dashboard component tests (MP-06 §4)

The dashboard's two logic-heavy pieces (timeline lane assembly, task-card
derivation) are pure TypeScript modules. Vitest runs them against the same
Vite config as the app (one toolchain, no ts-jest/babel bridge) and is
wired into `npm run check`. The extension keeps its existing node:test
setup - no churn where nothing is gained.

### D20 - pandas + scipy + matplotlib - **ADOPT** → FR-ANA-1..5, NFR-8

The recipe layer (MP-07) computes exact nonparametric statistics and emits
publication figures. **scipy.stats** provides the exact Wilcoxon
signed-rank / Mann-Whitney U / Fisher distributions NFR-8 demands -
reimplementing exact test distributions by hand is where statistics bugs
come from, so building was rejected outright. **pandas** is the join
surface for the one-timeline dataset (groupby per participant/condition,
timestamp joins across legs); **matplotlib** (Agg backend, headless)
renders the house figure styles in `analysis/figures.py` following the
data-viz conventions. Alternatives rejected: statsmodels (nothing needed
beyond scipy's exact tests), seaborn/plotly (styling is deliberately
hand-rolled so figures match the dashboard palette; plotly's HTML output
doesn't fit a paper pipeline). All three are pinned via the uv lockfile
(D16, NFR-6).

### D21 - PyMuPDF (`pymupdf`) for PDF text extraction - **ADOPT** → FR-LIT-1

The paper-ingest path accepts a PDF upload and needs its text + a title
guess for the assistant's full-text search. **PyMuPDF** (the `fitz` module)
extracts text and page structure fast, from a single wheel, with no system
dependencies (unlike `pdfminer.six`'s slower pure-Python parse or
`poppler`/`pdftotext`'s native binary). It is used only as an *extractor* -
the metadata of record still comes from Semantic Scholar (D8), so a scanned
or garbled PDF degrades to metadata-only rather than failing ingest. Adopted
via the uv lockfile (D16); PDF bytes are never re-uploaded to any external
service (NFR-5), extraction is local. FTS over the extracted text uses
SQLite's built-in **FTS5** - no vector DB at this scale (a build decision
recorded inline in the ingest code, not a new dependency).

### ~~D22 - `anthropic` Python SDK - **ADOPT** (realizes D10)~~ **SUPERSEDED by D32** (2026-07-16) → FR-LIT-4

Realized D10; removed with it. D32's provider is called over plain REST
(stdlib `urllib`), so no successor SDK was adopted.

### D23 - `tectonic` TeX engine (paper-compile proof) - **ADOPT** → FR-ANA-6

FR-ANA-6's acceptance is "produce a compilable `draft.tex` (run `pdflatex`
to prove it)". A TeX engine is a *test-time proof tool*, not a runtime or
packaged dependency - `analysis paper` emits `.tex` and never shells out to
LaTeX. **tectonic** (a single self-contained Rust binary that runs the full
latex + bib + `xdvipdfmx` pipeline and fetches only the packages a document
needs, ~30 MB) is adopted over a full **MacTeX** (~4 GB) or **BasicTeX**
(~500 MB, needs a privileged installer) purely to satisfy that proof with
minimal footprint (zero-bloat discipline). It is a developer/CI tool
installed via Homebrew, **not** added to the uv lockfile - nothing in the
shipped framework imports or requires it. The compile smoke test
(`test_draft_compiles_to_pdf_when_a_tex_engine_is_present`) prefers
`tectonic`, falls back to `pdflatex`+`bibtex` if those are on PATH instead,
and **skips cleanly** where no TeX engine is present, so CI without a TeX
install stays green (the LaTeX brace/environment-balance test remains the
always-on structural proxy).

### D24 - GitHub Actions + GHCR + GitHub Releases - **ADOPT** → FR-OPS-2

The release/deploy pipeline lives where CI already lives (`ci.yml`).
**Actions** is free at our scale (2,000 min/month private; the Student Pack's
GitHub Pro also unlocks protected *environments* on private repos - the
FR-OPS-2 manual approval gate). **GHCR** is the container registry: same
auth (`GITHUB_TOKEN`, no extra secret), free for the repo's visibility.
**Releases** hold the versioned artifacts (`.vsix`, image digest notes) -
RC tags are pre-releases. Alternatives rejected: Docker Hub (second account,
pull-rate limits), a self-hosted registry (a service to babysit, contra
NFR-7's no-IT-department posture).

### D25 - Render free tier (demo host) - **ADOPT** → FR-OPS-1(a)

The public seeded demo runs the existing `middleware/Dockerfile` on Render's
free web-service tier (still current in 2026: 750 instance-hours/month,
Docker support, free TLS subdomain, deploy-hook URL). Its two limitations
are *acceptable by design*: spin-down after 15 min idle (a demo tolerates a
cold start) and an **ephemeral disk** - which would be disqualifying for
real data, but the demo reseeds itself on every boot
(`start_with_seed.sh`; replay is idempotent per FR-ING-2) and NFR-5 forbids
real participant data on any public instance anyway. `autoDeploy` is off:
the pipeline triggers the deploy hook only after CI is green, so the demo
never runs a red build.

### D26 - Azure for Students (persistent VM + on-demand Sonar VM) - **ADOPT** → FR-OPS-1(b), FR-OPS-4

$100/year credit, renewable annually while enrolled, no card; includes
750 h/month of a B1s Linux VM free for 12 months. The B1s is the persistent
dev/staging host: `docker compose -f deploy/compose.prod.yml` pulls the
released GHCR image, the SQLite volume persists on the VM disk (exactly the
one-file-is-the-backup posture of D11), and **Caddy** (adopted here: single
static binary, automatic certificates; nginx+certbot is two moving parts
for the same job) terminates TLS on a Namecheap `.me` domain (also free in
the pack). For FR-OPS-4, a second **B2s (4 GB - SonarQube's floor; the B1s
1 GB cannot host it)** stays **deallocated** except during analysis
windows - a deallocated VM bills only pennies of disk against credit -
toggled by `sonar-vm.yml` (workflow-dispatch) or `az vm start|deallocate`.

### D27 - VS Code Marketplace via `@vscode/vsce` - **ADOPT** → FR-OPS-3

Publishing is free and `vsce` is already a devDependency (`npm run
package`). The release pipeline publishes on **final tags only**, because
the Marketplace rejects semver pre-release suffixes (`0.3.0-rc.1` is not a
legal Marketplace version) and its pre-release *channel* imposes a version
convention we don't want to carry - so RC builds are distributed as `.vsix`
assets on GitHub pre-releases instead (documented in FR-OPS-3). Requires a
one-time publisher account + `VSCE_PAT` secret; the `publisher` field in
`extension/package.json` must match the account. An Open VSX mirror is
deferred until someone on VSCodium asks (zero-bloat).

### D28 - Remaining student-pack / free-tier candidates - **REJECT (batch)**

Each was considered for the FR-OPS deployment slice and rejected:

- **DigitalOcean** - the pack's $200 credit sunsets **2026-07-31**
  (announced 2026-06-12); building on it now is building on sand.
- **Heroku** - $13/month × 24 months of pack credit is real money, but the
  dyno filesystem is ephemeral: SQLite (D11) would need a Postgres port
  *purely to fit the host*. The host should fit the architecture, not the
  reverse.
- **Fly.io** - no free tier for new organizations; not in the pack.
- **Railway** - trial credit only; no sustained free tier.
- **Supabase** - hosted Postgres/auth/storage would move study data to a
  third-party cloud (NFR-5 - same reasoning as D1's wandb reject) and
  replace the SQLite source-of-truth for zero benefit at ≤ dozens of
  participants.
- **Clerk** - auth SaaS for a dashboard with exactly one operator (the
  facilitator); `MIDDLEWARE_TOKEN` bearer auth (MP-06) already covers it,
  and a third-party login dependency contradicts NFR-7.
- **Blackfire.io** - profiler, free for students, but there is no open
  performance requirement: NFR-1's latency bound is enforced by sensor
  design (fire-and-forget, O(1) handlers) and tested. Revisit only if a
  measured performance defect ever appears in the findings log (FR-META-1).

### D29 - Clerk (+ `pyjwt[crypto]`) - **ADOPT as optional provider** → FR-OPS-5 *(partially supersedes D28's Clerk row, 2026-07-16)*

D28 rejected Clerk as a *mandatory* dependency - that half stands: an
open-source, offline-capable research tool must never require a third-party
account to self-host. What changed (owner elicitation, 2026-07-16): the
maintainer's *hosted* instance wants a polished login. Resolution: auth
becomes a provider seam in the middleware (`none` / `token` / `clerk`), the
zero-config token path stays the self-hosting default, and `clerk` verifies
Clerk-issued JWTs server-side against the instance's JWKS - adopted via
**`pyjwt[crypto]`** (the standard, minimal JWT library; hand-rolling RS256
verification is where security bugs come from). The Clerk *frontend* widget
is wired only on deployments that configure it; everyone else sees the
token sign-in. This is the same graceful-degradation posture as every other
external service (Semantic Scholar D8, the LLM provider D32, SonarQube D5, Zotero
D9): optional, replaceable, never load-bearing.
**Built (2026-07-16, client half):** clerk-js is **hot-loaded from the
Clerk instance's own domain** (the script URL is derived from the
publishable key), only when `/auth/config` says `clerk` - token/none
deployments load nothing. Self-bundling the npm package was tried first
and reverted the same day: its ESM build ships without the UI renderer
("Clerk was not loaded with Ui components" at mount), and hotload is
Clerk's documented pattern for non-React apps anyway. `@clerk/clerk-js`
stays as a **types-only devDependency**. Clerk's hosted sign-in UI mounts
in `SignIn.svelte`; the API client takes a live token getter
(`session.getToken()` per request - Clerk JWTs are short-lived and
refreshed by clerk-js). If the script can't load, the paste-a-token
surface remains as the fallback; a manually issued session token verifies
server-side identically.

### ~~D30 - Vercel v0 - **ADOPT as design tool only**~~ **RETIRED** (rev 4, 2026-07-17) → dashboard UI iteration

Four revs (design-tool-only → direct Svelte iteration in v0 → main-branch
deploys disabled → retired at owner direction) ended with Vercel/v0
removed from the workflow; its one merge landed as ordinary gated commits
(traceability log, 2026-07-16). FR-OPS-6 (separate-origin hosting + CORS
allow-list) stays - a general capability, no longer tool-tied. D35 is the
successor design workflow. Full narrative in git history.

### D31 - Public-docs architecture - **BUILD (two-layer, archive internals)** → NFR-11

The repo is open source and must read as a product. Decision (owner,
2026-07-16): internal build history (the mega-prompt phase specs, sprint
plans) moves to `docs/archive/` - kept intact for the examiner, out of the
public eye; README becomes the product front page; the contributor guide
consolidates into one `CONTRIBUTING.md`; RUNBOOK/TOUR keep their roles but
drop requirement-ID jargon per NFR-11. Alternatives rejected: deleting the
history (destroys the execution record) and a docs site generator
(a build system for a dozen Markdown files).

### D32 - Gemini + Mistral APIs (REST, no SDK) - **ADOPT, bounded** → FR-LIT-4, FR-META-2 *(supersedes D10, D22)*

Replaces the Claude API for the knowledge assistant and the retrospective
(owner decision, 2026-07-16: free-tier providers over a paid key). Two
providers, selected by which key is set (`GEMINI_API_KEY` preferred, then
`MISTRAL_API_KEY`; models `gemini-flash-latest` / `mistral-small-latest`),
so the feature survives either free tier tightening. Called over plain
REST via stdlib `urllib` - the same zero-bloat shape as the Semantic
Scholar client (D8) - because the assistant's hand-rolled tool-use loop
*is* the FR-ETH-4 enforcement boundary; no vendor SDK adopted. D10's
bounds carry over verbatim: aggregates only server-side, answers must cite
sources, the retrospective's output is an inert proposal a human approves,
and absent both keys everything degrades gracefully (503 / offline
template). Keys live only in runtime env (Render env / VM `deploy/.env`),
never in git or CI.
**Rev 2 (2026-07-16):** Gemini removed at the owner's request (one Mistral
key in active use); the dashboard's picker now selects among *Mistral model
tiers* (small/medium/large, validated server-side) instead of providers.
The seam stays one provider class - reintroducing a second provider is a
small, decision-gated change.

### D33 - `svelte-dnd-action` - **ADOPT** → FR-DASH-7

Drag-and-drop for the task board's manual cards, introduced by the v0
design iteration (D30 rev 2) and kept at merge review: it is the standard
Svelte DnD library (headless action, no UI opinions, keyboard-accessible),
and hand-rolling HTML5 DnD with keyboard support is exactly the
wheel-reinvention D30's workflow exists to avoid. Bounds: platform-derived
cards stay non-draggable (they clear themselves); only manual todos move.
Pinned via the npm lockfile.

### D34 - React 19 + Vite + Tailwind v4 + shadcn/ui (v2 platform surface) - **ADOPT** → FR-PLAT, FR-CONV, NFR-12 *(scopes D15, 2026-07-17)*

The v2 platform surface (hero page, projects, the conversational study
designer, chat-first study evolution) is a **new application**, not an
increment of the mission-control SPA - different information architecture
(marketing + auth + conversation vs. operational monitoring), different
component vocabulary (chat threads, streaming responses, command palettes,
forms-as-review-surfaces vs. swimlanes and gap strips). Decision (owner
direction 2026-07-17: "elements from shadcn... no need to stick with
Svelte"; framework call delegated to the implementer):

- **React 19 + TypeScript + Vite** for the new `platform/` app. shadcn/ui's
  canonical ecosystem is React; the AI-assisted design workflow (D35)
  and the strongest chat-UI primitives (streaming, optimistic updates,
  virtualized threads) live there. Vite (not Next.js): the middleware
  already serves SPAs and owns the API - a second server runtime adds an
  operational surface NFR-7 forbids.
- **Tailwind v4 + shadcn/ui**: shadcn is *vendored source, not a
  dependency* - components are copied in and owned, which fits the repo's
  zero-bloat and own-your-marks discipline (D17) far better than a
  component library ever did. Design tokens bridge to the existing
  dataviz palette so charts stay consistent across both surfaces.
- **D15 is scoped, not overturned:** the Svelte dashboard remains the v1
  operational console - built, tested, shipping - and is *maintained
  frozen* (bug fixes, no new features) until the v2 surface reaches
  feature parity view-by-view; each migrated view retires its Svelte twin
  in the same PR. No big-bang rewrite of working software.

Alternatives rejected: **shadcn-svelte** (a port perpetually trailing
upstream; the chat/streaming ecosystem gap is the real cost, not the
components); **Next.js** (server runtime duplication, contra NFR-7);
**big-bang Svelte→React rewrite** (discards 47 passing tests and a working
console for zero user value during the transition).

### D35 - Claude-driven design workflow ("Claude Design") - **ADOPT (workflow)** → NFR-12 *(succeeds retired D30)*

The owner designs the v2 surface *with Claude* (agentic coding + design
skills) instead of v0 (retired, D30 rev 4): design tokens, component
composition, motion, and dataviz follow the repo's skills (`dataviz`,
design-system conventions) applied by the agent directly in the codebase -
no external design SaaS, no port-back step, every iteration lands as an
ordinary gated commit. Bounds: accessibility and reduced-motion are
requirements (NFR-12), not aesthetic options; generated UI is reviewed
like any other code (CI gates unchanged).

### D36 - Corpus growth: Semantic Scholar snowballing now, agentic paper platforms later - **BUILD (pipeline) + ADOPT (S2, extends D8); alphaXiv et al. DEFERRED** → FR-LIT-8

The 1,000-paper corpus (FR-LIT-8) is grown by **citation snowballing**
over the Semantic Scholar Graph API (D8's provider, same self-paced/
cached posture): every reference and citation of every Tier A seed is a
candidate; a quality gate (verifiable external ID, age-scaled citation
floors, fresh-paper allowance) and a ranking function (freshness ×
impact × seed-connectivity × venue) pick Tier B. Built as
`scripts/corpus_harvest.py`, stdlib-only, resumable, deterministic given
its cache - rerunning refreshes the corpus as the literature moves.
**Why build:** no service emits a quality-tiered, provenance-tracked
corpus index keyed to *our* seeds; the gate/rank logic *is* editorial
judgment and must be ours, versioned in-repo. **Deferred, recorded as
the FR-LIT-8 adapter extension point:** agentic discovery platforms
(alphaXiv trending/discussion signals, Hugging Face daily papers,
OpenAlex, Connected Papers) as additional candidate sources feeding the
same gate - each future source is its own decision row; none may bypass
the gate (quality is non-negotiable, and a trending signal is not a
quality signal). Rejected: bulk arXiv category dumps (volume without
relevance; the seed-connectivity signal is what keeps the corpus *ours*).

<!-- A summary table duplicating the per-decision prose above was removed
     2026-07-17 (regroup pass); the prose is the record. Git history has it. -->

### D37 - Platform app dependency substrate (the shadcn/Vite baseline) - **ADOPT (pinned, vendored where possible)** → FR-PLAT, FR-CONV, NFR-12 *(implements D34, 2026-07-17)*

D34 adopted "React 19 + Vite + Tailwind v4 + shadcn/ui" as the `platform/`
surface; this row pins the concrete package set so the adoption is a
decision, not a drift (golden rule 5). The substrate is the minimum
shadcn/ui requires plus the design-system primitives - nothing
speculative:

- **Build/runtime:** `react`@19, `react-dom`@19, `vite`@7, `typescript`,
  `@vitejs/plugin-react`. Vite, not Next.js (NFR-7: the middleware owns
  the API and serves the SPA; no second server runtime).
- **Styling:** `tailwindcss`@4 + `@tailwindcss/vite` (v4's first-party
  plugin - no PostCSS config file). Design tokens live in one CSS layer
  (`src/styles/tokens.css`) bridged to the dataviz palette so charts read
  identically across both surfaces (D34's token-bridge clause).
- **shadcn substrate (vendored source, owned - D17):** `class-variance-
  authority`, `clsx`, `tailwind-merge` (the `cn()` util), `lucide-react`
  (icon set), `tw-animate-css` (v4's replacement for the retired
  `tailwindcss-animate`). Radix primitives (`@radix-ui/react-*`) are
  added *per vendored component*, not wholesale - a component that needs
  no Radix primitive pulls none.
- **Deferred to their own rows when first needed** (not adopted now):
  data fetching (`@tanstack/react-query`), routing
  (`react-router`), virtualized threads. The MP-15 first slice runs on a
  deterministic local stub (no network, no LLM) so none are required yet;
  each is a decision when the middleware wiring lands.

**Why adopt, not build:** re-implementing accessible menu/dialog/tooltip
behaviour (focus traps, ARIA, keyboard nav) is exactly what NFR-12 (WCAG
2.2 AA) forbids getting wrong by hand; Radix is the accessibility
substrate the industry has settled on and shadcn vendors it as owned
source. **Own-your-marks (D17):** shadcn components are copied into
`platform/src/components/ui/`, edited freely, never imported from an
upstream package - so there is no "external library look" and no
version-lock to a component vendor. Pinned via the lockfile.
**Rejected:** a component library imported as a dependency (MUI, Chakra -
the look is theirs, not ours; contra D34); CRA/Webpack (Vite is the
shadcn-canonical, faster path); adopting TanStack Query / router now
(YAGNI while the stub has no network - decide when wiring the middleware).

### D38 - Platform shell libraries (routing, palette, overlays) - **ADOPT (pinned)** → FR-PLAT *(extends D37, 2026-07-18)*

D37 deferred routing/overlays to "their own row when the shell needs
them." MP-14 needs them, so this row pins the set:

- **`react-router-dom`** (v7): the shell's routes (hero, projects, project
  home, study, members, settings, invite-accept) are real URLs, so links,
  deep-links, and the browser back button work. Client-side only — the
  middleware serves the SPA and owns the API (no server runtime added).
- **`cmdk`** (v1): the ⌘K project switcher. Fuzzy match + full keyboard
  nav are exactly the accessibility behaviour we must not hand-roll; it's
  the shadcn-canonical command primitive and vendors as owned source.
- **`@radix-ui/react-dialog`, `@radix-ui/react-dropdown-menu`**: the
  invite dialog, delete confirmation, account menu, and member-role menu.
  Same reason Radix was adopted in D37 — accessible focus trapping, ARIA,
  and keyboard behaviour are requirements, not options.

**Still deferred** (decide when first needed): a data-fetching library
(`@tanstack/react-query`) — the shell talks to the API through a small
typed client with a plain `fetch`, and an in-memory backend stands in
offline, so a cache/query layer isn't earning its weight yet. **Rejected:**
a router that needs a server runtime (contra D34/NFR-7); a component
library imported wholesale (the look must stay ours, D17/D34).

### D39 - GitHub mining client: stdlib urllib + a fixture cassette - **BUILD (thin) + no new dependency** → FR-CUR-2 *(2026-07-18)*

The curated-mining leg needs to read GitHub (PRs, commits, reviews). The
freedom note in MP-16 allows a GitHub client *library* behind its own
D-row, or plain HTTP with nothing. Decision: **plain stdlib** (`urllib`),
matching the Semantic Scholar client's zero-bloat posture (D8) - the leg
issues a couple of GET shapes, not enough surface to justify PyGithub or
an httpx dependency. `middleware/github_fetch.py` is the thin live fetcher
(token-scoped; maps GitHub's 403/429 rate-limit signalling onto the
runner's pause contract, F2.3).

Offline is a **fixture cassette**, not a mock library: recorded, sanitized
(pseudonymized-at-record) API responses replayed deterministically
(`curated/src/curated/cassette.py` + `cassettes/cursor-mining-demo.json`).
This is the committed, zero-token, zero-network path CI and the demo run
on (F1.1/F1.2/F2.1), and it scripts rate-limit and interruption faults so
the pause/resume behaviour is tested without a live API. **Rejected:**
PyGithub / a GraphQL client library (unearned dependency weight for two
GET shapes; the look/rate-handling would be theirs, not ours); a generic
VCR library (a ~40-line request-shape cassette is simpler and owned).
The adapter contract keeps the source pluggable, so a heavier client is a
later per-source decision, never a rewrite.
