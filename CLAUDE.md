# CLAUDE.md — agent guide for this repository

**Project:** Framework for Conducting Human-AI Studies — a Masters project in
**requirements engineering**. A protocol-driven platform that instruments
human-AI developer studies (four data legs on one timeline), manages the
study lifecycle, and generates analysis, reports, and paper drafts.
Read `docs/archive/roadmap/00-VISION.md` before any non-trivial work.

## The golden rules (RE discipline — these are graded)

1. **No orphan work.** Every feature traces to a requirement ID in
   `requirements/srs.md`. If asked to build something with no requirement,
   first add the requirement (with MoSCoW priority + rationale) and a row in
   `requirements/traceability.md`, then build.
2. **IDs are stable.** Never renumber or delete a requirement/decision.
   Supersede: strike through, note the successor and date, append a row to
   the phase-completion log in `traceability.md`.
3. **A phase is done only when the matrices say so.** Finishing a mega-prompt
   means: its verification steps ran green, the tracker row in
   `docs/archive/roadmap/00-VISION.md` is flipped, and its requirement rows in
   `requirements/traceability.md` are flipped.
4. **Glossary wins.** Use `requirements/glossary.md` terms in code
   identifiers, schema fields, and docs (`participant` not `user`,
   `condition` not `group`, `recipe` not `script`). Terminology disputes are
   settled by editing the glossary first.
5. **Reuse needs a decision.** Before adopting any new dependency/tool/
   service, add a row to `requirements/build-vs-adopt.md`
   (adopt/adapt/build/reject + rationale). NFR-10.
6. **MoSCoW is the cut line.** Must = the one-week production slice; don't
   gold-plate a Must into a Could while Musts are open.

## Execution model

Work proceeds by **mega-prompts**: `docs/archive/roadmap/01..12` are self-contained,
detailed phase specs. Execute them in the sprint order in
`docs/archive/roadmap/00-VISION.md` (§ The one-week sprint). Each states its
dependencies, the requirement IDs it satisfies, deliverables, acceptance
criteria, and verification steps — follow them literally; deviations must be
noted in the traceability log.

## Repository map

| Path | What | Built by |
| ---- | ---- | -------- |
| `requirements/` | SRS, stakeholders, RQs, glossary, traceability matrix, build-vs-adopt decisions | MP-01 ✅ |
| `docs/archive/roadmap/` | Vision + mega-prompts 01–12 | — |
| `*/docs/` | Docs live with their component: `extension/docs/developer_behavior_capture.md` (+ `adaptation-notes.md` from MP-05), `metrics/docs/` (metrics matrix, implementation plan) | — |
| `extension/` | VS Code extension "Cognitive Overlay" — cognitive + behavioral legs (TypeScript) | built v0.1; MP-05 extends |
| `metrics/` | Static-metrics leg, 9-metric matrix (Python, flat `src/` scripts) | MP-03 |
| `protocol/` | Study-as-code schema, validator, lifecycle (Python pkg, CLI `protocol`) | MP-02 |
| `middleware/` | FastAPI ingestion service on :8000 (Python pkg) | MP-04 |
| `analysis/` | Recipes, runner, report, paper draft (Python pkg, CLI `analysis`) | MP-07, MP-11 |
| `agent-capture/` | Agent leg: hooks, transcript import, redaction, snapshots, task harness (Python pkg) | MP-12 |
| `dashboard/` | Svelte 5 + Vite + TS SPA — mission control: task board, lifecycle, timeline (`npm run check` is the gate) | MP-06 ✅ |

Directory history (for stale references): `extension/` was
`Cognitive Overlay/`; `metrics/` was `Static Code Metrics/`. The extension's
*product name* is still "Cognitive Overlay".

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
into a package mid-sprint.

**Extension (TypeScript, Node ≥ 20):** work in `extension/`; `npm run check`
(typecheck + lint + format + test) is the gate and must stay green. Deep
rules in `extension/PROJECT_GUIDE.md` — the sacred one: **`src/core` never
imports `vscode`.**

**Dashboard: Svelte 5 + Vite + TypeScript** (decision D15 — not React).
Scaffolded only by MP-06. Charts follow the `dataviz` skill.

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
  governed by the protocol's consent-matched content policy (FR-ETH-2 rev 2,
  FR-AGENT-5). The knowledge assistant may only ever see aggregates
  (FR-ETH-4) — enforce server-side, test with grep-the-output.
- **Port 8000** is the middleware contract all sensors assume (FR-ING-1).
- **Honest statistics:** exact tests, effect sizes, per-cell n; never bare
  p-values (NFR-8).
- **Participant data never enters git:** `.study-data/`, `*.sqlite3`,
  `results/`, `shadow.git/` are gitignored — keep it that way.

## When writing code here

- Match the existing style of the file/package you're in; Prettier owns the
  extension's formatting, ruff owns Python (`E,F,I,B,UP`, line length 88).
- Time-dependent logic gets an injected clock and mocked-timer tests (see
  `extension/test/` for the pattern).
- External APIs (Semantic Scholar, Claude, SonarQube) must degrade
  gracefully: cache, warn once, never block a session. For Claude API code,
  read the `claude-api` skill first; for Claude Code hook/transcript
  formats, verify against current docs via the `claude-code-guide` agent —
  not memory.
- Before committing: `uv run pytest && uv run ruff check .` (Python) and/or
  `npm run check` in `extension/`.
