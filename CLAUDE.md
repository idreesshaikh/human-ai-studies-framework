# CLAUDE.md — agent guide for this repository

**Project:** Framework for Conducting Human-AI Studies — a Masters
project. A conversational research platform:
researchers *talk* their study into existence — a design conversation
grounded in a 1,000+-paper corpus proposes citable design moves that compile
deterministically into the study-as-code protocol; paper-derived templates
prescribe the statistical formulation; data comes from live instrumented
sessions (four legs, one timeline) or curated GitHub mining through one
join-key schema; studies evolve on the fly through phase-aware amendments;
the platform itself evolves from researcher feedback. Multi-researcher
shell (projects, roles, hero), product-grade UI (D34 React + shadcn/ui),
agent-readable metadata throughout.
Read `docs/VISION.md` (v2, current direction) before any non-trivial work;
`docs/archive/roadmap/00-VISION.md` is the superseded-but-authoritative
record of the built v1 engine (MP-01..13). Detailed v2 specs with fit
criteria: `requirements/specs/`.

## The golden rules (the structure that keeps the platform honest)

*(Reframed 2026-07-17, MP-01 rev 14: the thesis is the platform, not an
RE showcase — the supervisor values RE but does not grade on it. Keep
these mechanics because a smart, evolving platform needs a memory and an
audit trail; drop RE-heavy framing and ID-jargon-first writing in any
new docs, summaries, or UI copy.)*

1. **No orphan work.** Every feature traces to a requirement ID in
   `requirements/srs.md`. If asked to build something with no requirement,
   first add the requirement (with MoSCoW priority + rationale) and a row in
   `requirements/traceability.md`, then build.
2. **IDs are stable.** Never renumber or delete a requirement/decision.
   Supersede: strike through, note the successor and date, append a row to
   the phase-completion log in `traceability.md`.
3. **A phase is done only when the matrices say so.** Finishing a mega-prompt
   means: its verification steps ran green, its tracker row is flipped
   (v1 phases: `docs/archive/roadmap/00-VISION.md`; v2 phases:
   `docs/roadmap/README.md`), and its requirement rows in
   `requirements/traceability.md` are flipped.
4. **Glossary wins.** Use `requirements/glossary.md` terms in code
   identifiers, schema fields, and docs (`participant` not `user`,
   `condition` not `group`, `recipe` not `script`). Terminology disputes are
   settled by editing the glossary first.
5. **Reuse needs a decision.** Before adopting any new dependency/tool/
   service, add a row to `requirements/build-vs-adopt.md`
   (adopt/adapt/build/reject + rationale). NFR-10.
6. **MoSCoW is the cut line.** Must is defined against the active milestone
   (v1 families: the one-week sprint, done; FR-PLAT/TPL/CUR/AGF: the v2
   milestone). Don't gold-plate a Must into a Could while Musts are open —
   in v2 terms: no shell polish while the methodology engine has open Musts.

## Execution model

Work proceeds by **mega-prompts**: self-contained phase specs stating
dependencies, the requirement IDs satisfied, deliverables, acceptance
criteria, and verification steps — follow them literally; deviations must
be noted in the traceability log. MP-01..13 live in
`docs/archive/roadmap/` (v1, built). **The living roadmap is
`docs/roadmap/`**: a master README (the invariant "walls", an explicit
autonomy charter stating where the builder is free, the stretch-idea
ledger, the phase tracker) plus full UI-to-backend specs for all five
v2 phases — MP-15 templates + conversational designer (**slice 1
built**: the `platform/` app + design-conversation surface on a
deterministic no-LLM stub), MP-16 curated-dataset leg, MP-14 platform
shell + hero, MP-17 agent-friendliness (incl. FR-PROT-9 agent
participants), MP-18 evolution (amendments + feedback). Build order and
rationale: `docs/VISION.md` § Build order — the conversation/templates
proof first, shell polish last. New dependencies still go through
`build-vs-adopt.md` before code.

## The v2 direction in one paragraph

The corpus — 1,000 papers as the floor, uncapped and quality-first
(FR-LIT-8 rev 2) — (100+ hand-curated Tier A seeds in
`docs/papers/README.md` + harvested Tier B, FR-LIT-8) is the product's
knowledge, not background reading. The core interaction is the **design conversation**
(FR-CONV): platform-proposed design moves, each grounded (cited into the
corpus/templates) or labeled unsourced, individually accepted/rejected,
compiled *deterministically* (no LLM in the compiler) into protocol draft
diffs applied on human approval — the YAML protocol stays the sole
document of record, and the conversation is stored as the study's
elicitation record (the RE chain now starts at the idea). Templates
(FR-TPL) encode published designs and prescribe the exact statistics;
data converges from live capture or curated mining (FR-CUR) into one
join-key schema; projects/roles/hero (FR-PLAT) deliver it to S7; manifest
+ generated context files (FR-AGF) make it legible to agents; NFR-12
holds every v2 surface to a product bar. Not a task board; not an
Overleaf/Zotero competitor; fully usable with no LLM key (the structured
designer is the degradation path).

## Repository map

| Path | What | Built by |
| ---- | ---- | -------- |
| `requirements/` | SRS (index of record), stakeholders S1–S7, RQs, glossary, traceability, build-vs-adopt D1–D37, **`specs/` detailed v2 family specs with fit criteria** | MP-01 ✅ (rev 12 = regroup) |
| `docs/VISION.md` | **v2 platform vision — the current direction (conversational research platform)** | 2026-07-17 |
| `docs/papers/` | The corpus: Tier A seeds (`README.md`, hand-curated) + Tier B (`CORPUS.md`/`corpus-index.json`, generated by `scripts/corpus_harvest.py` — never hand-edit) | FR-LIT-8 |
| `docs/design/` | v2 design tree: C4 architecture, UML data model, sequences, state machines, flows, UI/motion spec | 2026-07-17 |
| `docs/archive/roadmap/` | v1 vision + mega-prompts 01–13 (superseded, kept authoritative for the built engine) | — |
| `*/docs/` | Docs live with their component: `extension/docs/developer_behavior_capture.md` (+ `adaptation-notes.md` from MP-05), `metrics/docs/` (metrics matrix, implementation plan) | — |
| `extension/` | VS Code extension "Cognitive Overlay" — cognitive + behavioral legs (TypeScript) | built v0.1; MP-05 extends |
| `metrics/` | Static-metrics leg, 9-metric matrix (Python, flat `src/` scripts) | MP-03 |
| `protocol/` | Study-as-code schema, validator, lifecycle (Python pkg, CLI `protocol`); `examples/` holds the pilot + the two v2 demonstrator drafts (comprehension-debt, context-ablation) | MP-02 |
| `middleware/` | FastAPI ingestion service on :8000 (Python pkg) | MP-04 |
| `analysis/` | Recipes, runner, report, paper draft (Python pkg, CLI `analysis`) | MP-07, MP-11 |
| `agent-capture/` | Agent leg: hooks, transcript import, redaction, snapshots, task harness (Python pkg) | MP-12 |
| `dashboard/` | Svelte 5 + Vite + TS SPA — the v1 operational console (maintained-frozen; `npm run check` is the gate) | MP-06 ✅ |
| `platform/` | v2 surface: React 19 + Vite + Tailwind v4 + shadcn/ui (D34/D37, NFR-12). **Built: MP-15 slice 1** — the design-conversation surface on a deterministic no-LLM stub (`npm run check` is the gate). Hero/projects (FR-PLAT) + server wiring are later slices/MP-14 | MP-15 (slice 1) |

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

**Frontend — two surfaces (D34):** the v1 operational console in
`dashboard/` stays **Svelte 5 + Vite + TS** (D15, maintained-frozen: bug
fixes only, `npm run check` gate) until the v2 surface reaches per-view
parity. The v2 platform surface is a **new `platform/` app: React 19 +
Vite + TypeScript + Tailwind v4 + shadcn/ui** (components vendored and
owned, never treated as an external library look). One design-token
system across both surfaces and all charts; charts follow the `dataviz`
skill; experience bar specced in
`requirements/specs/nfr-12-experience.md` (WCAG 2.2 AA, reduced-motion,
streaming, both themes — these are requirements, not options). UI is
designed with Claude in-repo (D35); every design iteration is an
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
- External APIs (Semantic Scholar, the LLM provider — Mistral per D32,
  SonarQube, GitHub for FR-CUR mining) must degrade gracefully: cache, warn
  once, never block a session. For Claude Code hook/transcript formats
  (agent-capture leg), verify against current docs via the
  `claude-code-guide` agent — not memory.
- Before committing: `uv run pytest && uv run ruff check .` (Python) and/or
  `npm run check` in `extension/`.
