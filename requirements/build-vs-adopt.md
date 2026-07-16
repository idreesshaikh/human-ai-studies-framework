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

### D9 - Zotero (local/web API) - **ADOPT (stretch)** → FR-LIT-5

The one end-user integration that proves the paper-ingest extension point;
clean documented API. Could-priority: after the sprint.
**Built (MP-09, 2026-07-12):** consumed via the desktop app's local
read-only API v3 (`localhost:23119`, no key) with the hosted API as
fallback. We adopt the *API*, not a library - the two calls (list
collections, list a collection's top items) are one-liners over stdlib
`urllib`, so no `pyzotero` dependency was added (zero-bloat discipline).

### D10 - Claude API (Anthropic) - **ADOPT, bounded** → FR-LIT-4, FR-META-2

Powers the knowledge assistant and retrospective drafting. Bounds are
requirements, not implementation details: FR-ETH-4 (no row-level
participant data leaves the machine), answers must cite sources, and the
retrospective's output is a *proposal* a human approves. Implementer must
check the official API docs at build time for current models/pricing;
default to the current Sonnet-class model, temperature low, tool-use for
querying the middleware's aggregate endpoints.
**Built (MP-10, 2026-07-12):** the official `anthropic` Python SDK, model
`claude-sonnet-5` (the current Sonnet-class model, verified against the
`claude-api` skill at build time). Note the "temperature low" clause is now
*unsatisfiable and dropped*: the current models reject `temperature`/`top_p`
with a 400, so determinism is steered by prompting instead (documented
deviation). FR-ETH-4 is enforced server-side in `assistant.py`: a hand-rolled
tool-use loop exposes exactly three tools (`search_papers`, `get_protocol`,
`get_dataset_summary`), none of which can return a row-level participant
event - the model cannot leak what it cannot see (grep-the-output test).
Absent `ANTHROPIC_API_KEY`, the endpoint degrades gracefully (503 with a
plain-language message; every offline feature keeps working).

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

### D22 - `anthropic` Python SDK - **ADOPT** (realizes D10) → FR-LIT-4

The official first-party SDK for the Claude API, per the `claude-api`
skill's guidance (never hand-roll the wire protocol). Realizes D10's
adopt decision; see D10 for the model choice (`claude-sonnet-5`), the
FR-ETH-4 server-side tool boundary, and the graceful-degradation posture.
Pinned via the uv lockfile (D16).

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

## Summary table

| # | Candidate | Decision | Satisfies | Key reason |
| - | --------- | -------- | --------- | ---------- |
| D1 | wandb | Reject / concepts only | - | human-subject data can't go to third-party cloud; wrong unit of record |
| D2 | Tako | Adapt | FR-INST-8,10 | AI-completion lifecycle hooks |
| D3 | ActivityWatch | Adapt | FR-ING-1, NFR-1 | sensor→local-daemon architecture |
| D4 | WakaTime | Adapt | FR-INST-11,12 | active/idle + language filter logic |
| D5 | SonarQube | Adopt (optional profile) | FR-INST-4 | industry-standard cognitive complexity |
| D6 | tree-sitter, Radon | Adopt | FR-INST-4 | parsers adopted, metrics built |
| D7 | ResearchRabbit | Reject / replicate view | FR-LIT-2 | no API; closed service |
| D8 | Semantic Scholar API | Adopt | FR-LIT-1,2 | open citation graph + recommendations |
| D9 | Zotero | Adopt (stretch) | FR-LIT-5 | proves ingest extension point |
| D10 | Claude API | Adopt (bounded) | FR-LIT-4, FR-META-2 | assistant + retrospective, FR-ETH-4 bounds |
| D11 | FastAPI/SQLite/React | Adopt | FR-ING, FR-DASH | one-laptop production (NFR-7/9) |
| D12 | Cognitive Overlay | Keep & extend | FR-INST-5,8–13 | one extension, one pipeline |
| D13 | Claude Code hooks + transcripts | Adopt | FR-AGENT-1,2 | only lossless machine-readable agent capture |
| D14 | git shadow repo | Adopt | FR-INST-15 | snapshots/diffs/time-series for free |
| D15 | Svelte 5 + Vite | Adopt (supersedes D11 frontend) | FR-DASH | compiled reactivity for data-dense live UI; maintainer preference |
| D16 | uv + Python 3.12 workspace | Adopt | all Python | lockfile reproducibility, one-command setup |
| D17 | LayerChart vs d3-scale | Build charts, adopt d3-scale | FR-DASH-4,5 | bespoke chart shapes; scales are the only hard part |
| D18 | SPA routing library | Build (hand-rolled) | FR-DASH | one fixed route shape; middleware re-serves the shell |
| D19 | Vitest | Adopt | MP-06 tests | pure-TS logic tests on the app's own Vite config |
| D20 | pandas + scipy + matplotlib | Adopt | FR-ANA-1..5, NFR-8 | exact test distributions are not something to hand-roll; pinned via D16 |
| D21 | PyMuPDF (`pymupdf`) | Adopt | FR-LIT-1 | fast single-wheel PDF text extraction; metadata still from S2 (D8) |
| D22 | `anthropic` Python SDK | Adopt (realizes D10) | FR-LIT-4 | first-party Claude SDK; never hand-roll the wire protocol |
| D23 | `tectonic` TeX engine | Adopt (test-time only) | FR-ANA-6 | prove `draft.tex` compiles; ~30 MB self-contained vs ~4 GB MacTeX; not in the lockfile |
