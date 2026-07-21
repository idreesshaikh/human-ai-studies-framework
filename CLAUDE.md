# CLAUDE.md — agent guide for this repository

**Project:** PHOENIX (Protocol for Human-Oriented Evidence, Networked
Iteration & eXperimentation) — Framework for Conducting Human-AI Studies,
a Masters project. A conversational research platform:
researchers *talk* their study into existence — a design conversation
grounded in a 1,000+-paper corpus proposes citable design moves that compile
deterministically into the study-as-code protocol; paper-derived templates
prescribe the statistical formulation; data comes from live instrumented
sessions (four legs, one timeline) or curated GitHub mining through one
join-key schema; studies evolve on the fly through phase-aware amendments;
the platform itself evolves from researcher feedback. Multi-researcher
shell (projects, roles, hero), product-grade UI (D34 React + shadcn/ui),
agent-readable metadata throughout.
Read `docs/VISION.md` before any non-trivial work; detailed specs with fit
criteria live in `requirements/specs/`, and the phase plan in `docs/roadmap/`.

## Design philosophy — Railway first

Deployment targets **Railway** for both the middleware service and PostgreSQL.
Everything is designed around this:

- **PostgreSQL is the default database.** SQLite is a fallback for script-level
   testing only. `docker compose up` boots with Postgres so local dev mirrors
   production exactly.
- **Single container image** (middleware serves API + SPA, NFR‑7) built by the
  Railway Dockerfile pipeline and pushed to GHCR.
- **Railway handles TLS, domains, and PostgreSQL.** No Caddy, no VM SSH deploys,
   no Marketplace publishing. SonarQube runs separately on-demand
   (`docker compose --profile sonar up` or Azure VM) for the cognitive-complexity
   metric — not on Railway. The `railway.toml` at the repo root is the sole
   deployment config.
- **CI/CD:** GitHub Actions build → push to GHCR → trigger Railway redeploy via
  the Railway GraphQL API. Release tags produce versioned images + GitHub
  Releases with the extension `.vsix`.
- **Auth:** Clerk (JWT) is the recommended provider for Railway; token auth is
  the self-hosted fallback.

## The golden rules (the structure that keeps the platform honest)

1. **No orphan work.** Every feature traces to a requirement ID in
   `requirements/srs.md`. If asked to build something with no requirement,
   first add the requirement (with MoSCoW priority + rationale) and a row in
   `requirements/traceability.md`, then build.
2. **IDs are stable anchors.** Don't renumber requirement or decision IDs —
   code, tests, the agent manifest, and the generated `AGENTS.md` key on the
   numbers. If a requirement is dropped, remove it cleanly and update its
   references rather than renumbering the rest.
3. **A phase is done only when the matrices say so.** Finishing a phase means:
   its verification steps ran green, its tracker row in `docs/roadmap/README.md`
   is flipped, and its requirement rows in `requirements/traceability.md` are
   flipped.
4. **Glossary wins.** Use `requirements/glossary.md` terms in code
   identifiers, schema fields, and docs (`participant` not `user`,
   `condition` not `group`, `recipe` not `script`). Terminology disputes are
   settled by editing the glossary first.
5. **Reuse needs a decision.** Before adopting any new dependency/tool/
   service, add a row to `requirements/build-vs-adopt.md`
   (adopt/adapt/build/reject + rationale). NFR-10.
6. **MoSCoW is the cut line.** Must is defined against the current milestone;
   don't gold-plate a Must into a Could while Musts are open — no shell polish
   while the methodology engine has open Musts.

## Execution model

Work proceeds by **phases**: self-contained specs stating dependencies, the
requirement IDs satisfied, deliverables, acceptance criteria, and verification
steps — follow them literally; deviations are noted in the traceability log.
The plan is `docs/roadmap/`: a master README (the invariant "walls", an
explicit autonomy charter stating where the builder is free, the stretch-idea
ledger, the phase tracker) plus a spec per phase. Phases 01–13 are the built
foundation (protocol, instrument legs, ingestion, analysis, knowledge layer,
paper draft, replication, ethics/ops); phases 14–18 are the platform layer
(shell + hero, templates + conversational designer, curated-dataset leg,
agent-friendliness, evolution). Build order and rationale: `docs/VISION.md`
§ Build order. New dependencies go through `build-vs-adopt.md` before code.

## The direction in one paragraph

The corpus — 1,000 papers as the floor, uncapped and quality-first
(FR-LIT-8) — (100+ hand-curated Tier A seeds in `docs/papers/README.md` +
harvested Tier B) is the product's knowledge, not background reading. The core
interaction is the **design conversation** (FR-CONV): platform-proposed design
moves, each grounded (cited into the corpus/templates) or labeled unsourced,
individually accepted/rejected, compiled *deterministically* (no LLM in the
compiler) into protocol draft diffs applied on human approval — the YAML
protocol stays the sole document of record, and the conversation is stored as
the study's elicitation record (the decision chain starts at the idea).
Templates (FR-TPL) encode published designs and prescribe the exact
statistics; data converges from live capture or curated mining (FR-CUR) into
one join-key schema; projects/roles/hero (FR-PLAT) deliver it to the adopting
researcher; manifest + generated context files (FR-AGF) make it legible to
agents; NFR-12 holds every surface to a product bar. Not a task board; not an
Overleaf/Zotero competitor; fully usable with no LLM key (the structured
designer is the degradation path).

## Repository map

| Path | What |
| ---- | ---- |
| `requirements/` | SRS (index of record), stakeholders S1–S7, RQs, glossary, traceability, build-vs-adopt decisions, **`specs/` detailed family specs with fit criteria** |
| `docs/VISION.md` | The platform vision — the current direction (conversational research platform) |
| `docs/roadmap/` | The phase plan: master README (walls, autonomy charter, phase tracker) + a spec per phase (01–18) |
| `docs/papers/` | The corpus: Tier A seeds (`README.md`, hand-curated) + Tier B (`CORPUS.md`/`corpus-index.json`, generated by `scripts/corpus_harvest.py` — never hand-edit) |
| `docs/design/` | Design tree: C4 architecture, UML data model, sequences, state machines, flows, UI/motion spec |
| `*/docs/` | Docs live with their component: `extension/docs/developer_behavior_capture.md` (+ `adaptation-notes.md`), `metrics/docs/` (metrics matrix, implementation plan) |
| `extension/` | VS Code extension "TERN" — cognitive + behavioral legs (TypeScript) |
| `metrics/` | Static-metrics leg, 9 code complexity/readability metrics (Python, flat `src/` scripts) |
| `protocol/` | Study-as-code schema, validator, lifecycle (Python pkg, CLI `protocol`); `examples/` holds the pilot + the curated-mining demo (`cursor-mining-2026`). The FR-PROT-9 agent-participant fixture lives with its tests: `tests/fixtures/agent-participant-v3.yaml` |
| `middleware/` | FastAPI service on :8000 — ingestion + the platform backend; serves the `platform/` build at `/` (Python pkg) |
| `analysis/` | Recipes, runner, report, paper draft (Python pkg, CLI `analysis`) |
| `agent-capture/` | Agent leg: hooks, transcript import, redaction, snapshots, task harness (Python pkg) |
| `curated/` | Curated-dataset leg: normalizer, GitHub mining adapter, authorship heuristics, threats record (Python pkg) |
| `platform/` | **The sole frontend**: React 19 + Vite + Tailwind v4 + shadcn/ui (D34/D37, NFR-12). The design conversation, the study workspace (Library = live paper ingest + citation constellation + grounded assistant; Data = honest metric shapes; Lifecycle), projects/hero/members, evolution surfaces. `npm run check` is the gate. |

## Tooling & commands

**Python: 3.12, managed exclusively by uv** (never pip/venv by hand; never
add a `requirements.txt`). One workspace venv at the repo root.

```bash
uv sync --all-packages         # install everything (the setup command)
uv run pytest                  # all Python tests, from repo root
uv run ruff check .            # lint (config in root pyproject.toml)
uv run python metrics/src/parsers/ts_parser.py   # metrics demo
uv add --package middleware fastapi              # add a dep to one package
```

New Python packages: src layout (`<pkg>/src/<pkg>/`), hatchling backend,
added to `[tool.uv.workspace].members` in the root `pyproject.toml`.
`metrics/` is the exception: flat scripts (`src/parsers/`, `src/analyzers/`,
`src/main.py`) per `metrics/docs/implementation_plan.md` — don't "fix" it
into a package.

**Extension (TypeScript, Node ≥ 20):** work in `extension/`; `npm run check`
(typecheck + lint + format + test) is the gate and must stay green. Deep
rules in `extension/PROJECT_GUIDE.md` — the sacred one: **`src/core` never
imports `vscode`.**

**Frontend (D34):** the **`platform/` app: React 19 + Vite + TypeScript +
Tailwind v4 + shadcn/ui** (components vendored and owned, never treated as an
external library look) is the sole frontend; `npm run check` is the gate.
`docker compose up` serves its build at `/`. One design-token system across
the app and all charts; charts follow the `dataviz` skill; the experience bar
is specced in `requirements/specs/nfr-12-experience.md` (WCAG 2.2 AA,
reduced-motion, streaming, both themes — these are requirements, not options).
UI is designed with Claude in-repo (D35); every design iteration is an
ordinary gated commit.

## System invariants (violating these breaks the science)

- **Join keys everywhere:** every data row of every leg carries
  `participantId`, `condition`, `sessionId`, timestamp, and a schema
  version. A data source that can't provide them doesn't ship (FR-INST-6).
- **Schema versioning:** any change to event shape/meaning bumps
  `SCHEMA_VERSION` (extension: `src/core/types.ts`) or `protocolVersion`.
  Consumers branch on version, never guess (FR-PROT-2, NFR-4).
- **Never interrupt the participant:** sensors/sinks/hooks are
  fire-and-forget; failures are swallowed, counted, reported once. Local
  JSONL is the source of truth; HTTP mirroring is best-effort; loss must be
  *detectable* via `seq` gaps (NFR-1, NFR-2).
- **Privacy by construction:** no raw code content, keystrokes, or clipboard
  text in any instrument — aggregates, shapes, salted hashes only. The two
  scoped exceptions (agent-conversation content, workspace snapshots) are
  governed by the protocol's consent-matched content policy (FR-AGENT-5,
  FR-ETH-2). The knowledge assistant may only ever see aggregates
  (FR-ETH-4) — enforce server-side, test with grep-the-output.
- **Port 8000** is the middleware contract all sensors assume (FR-ING-1).
- **Honest statistics:** exact tests, effect sizes, per-cell n; never bare
  p-values (NFR-8).
- **Participant data never enters git:** `.study-data/`, `*.sqlite3`,
  `results/`, `shadow.git/` are gitignored — keep it that way.
- **Railway deploys from `railway.toml`** at the repo root. The container
  image is the sole artifact; Railway handles TLS, domains, and PostgreSQL.

## When writing code here

- Match the existing style of the file/package you're in; Prettier/ESLint own
  the extension's and platform's formatting, ruff owns Python (`E,F,I,B,UP`,
  line length 88).
- Time-dependent logic gets an injected clock and mocked-timer tests (see
  `extension/test/` for the pattern).
- External APIs (Semantic Scholar, the LLM provider — Mistral per D32,
  GitHub for FR-CUR mining) must degrade gracefully: cache, warn
  once, never block a session. For Claude Code hook/transcript formats
  (agent-capture leg), verify against current docs via the
  `claude-code-guide` agent — not memory.
- Before committing: `uv run pytest && uv run ruff check .` (Python),
  `npm run check` in `platform/` and/or `extension/`.
