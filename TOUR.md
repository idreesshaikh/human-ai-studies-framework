# The tour - what this project is, in plain language

You (or a new teammate, or an examiner) are looking at a lot of moving
parts. This page is the decoder: what the platform does, what the codes
like `FR-PROT-7` mean, and how thirty minutes of clicking shows you all of
it. The dashboard has an interactive twin of this page - the **guided
tour** that starts on your first visit ("✦ Take the tour" in the sidebar,
any time after that).

## What this platform is

A researcher writes **one YAML file** - the study protocol - saying what
they want to study: the research questions, the two conditions (working
with AI vs without), how many participants, which instruments, what
analyses. The platform does the rest:

- **configures the instruments** from that file (nothing is set up by hand),
- **records each session from four angles** on one shared timeline - how
  the participant *felt* (in-editor micro-surveys), what they *did* (tab
  switches, edits and where each edit came from: typed, pasted, or
  AI-generated), what their *code* looked like (nine complexity metrics),
  and what the *AI agent* did (conversation turns, tool calls),
- **manages the study itself** - a lifecycle with gates (no data collection
  before the ethics approval is uploaded) and a task board that derives its
  cards from the study's state and clears them itself,
- **grows the literature** - papers by DOI / arXiv / PDF become a
  citation graph plus a grounded, citing assistant,
- **writes up honestly** - exact statistical tests with effect sizes and
  per-group sample sizes, a per-question report, a compilable LaTeX paper
  draft, and a byte-reproducible replication kit,
- and **improves itself** - the framework logs its own defects and, after a
  study, drafts a change proposal a human reviews.

The whole thing runs on one laptop, offline, with participant data never
leaving `.study-data/` (which never enters git).

## Decoding the IDs (FR-PROT-7 and friends)

Every feature traces to a numbered requirement in `requirements/srs.md` -
that's the point of the project (it is a requirements-engineering thesis:
the paperwork is the science). The grammar:

| Piece | Meaning |
| ----- | ------- |
| `FR-` / `NFR-` | Functional Requirement (a feature) / Non-Functional (a quality, e.g. "reproducible") |
| `PROT` `INST` `ING` `DASH` `LIT` `ANA` `META` `ETH` `AGENT` | the area: protocol, instruments, ingestion, dashboard, literature, analysis, self-improvement, ethics, agent capture |
| the number | a stable sequence number - never renumbered, so references never rot |

**They are grep targets, not vocabulary.** Hover any pill in the dashboard
to read one in plain English, or:

```bash
grep "FR-PROT-7" requirements/srs.md          # what was promised
grep "FR-PROT-7" requirements/traceability.md # where it was built + proven
```

The four you'll meet most often in the docs:

| ID | In plain English |
| -- | ---------------- |
| FR-PROT-7 | Package a finished study so anyone can re-run it and get identical results (the replication kit) |
| FR-ANA-5 | Run a published paper's analysis method on your own data ("papers become recipes") |
| NFR-6 | Same inputs → byte-identical outputs, always |

## The vision → what got built

| The original idea | Where it lives now |
| ----------------- | ------------------ |
| "Requirements collected as if by a dynamic/AI project manager" | The protocol *is* a machine-readable requirements spec; the dashboard's task board derives cards from it and they clear themselves |
| "Derive post-analysis similar to other papers" | `analysis run` → per-question report → `analysis paper` → compilable LaTeX draft with your real numbers |
| "References from papers with the same studies" | Knowledge view: citation graph, auto-seeded related-work section |
| "Help them be lean, not overcomplicate" | `protocol validate` + `analysis validate` name everything missing *before* a session is wasted |
| "Replicate studies" | `protocol export replication-kit` - byte-stable archive, proven by re-running it |
| "Fetch algorithms directly from papers" | Two published studies already run as recipes (an AI-acceptance-rate metric, a work-fragmentation metric) |
| "Beautiful, clean, smart platform" | `docker compose up` → http://127.0.0.1:8000 |

## The seven components, one sentence each

| Where | What it is |
| ----- | ---------- |
| `protocol/` | The study-as-code language: validate a protocol, drive its lifecycle, derive instrument configs, export replication kits |
| `extension/` | The VS Code extension participants run - the feelings leg (micro-surveys) and the behavior leg (edits, focus, AI interactions) |
| `metrics/` | Nine code-complexity measurements over the participant's code |
| `agent-capture/` | The AI's side of the session: Claude Code hooks, transcript import, workspace snapshots, task pass/fail harness |
| `middleware/` | The hub on port 8000 everything reports to; stores every event, detects loss, serves the joined dataset and the dashboard |
| `dashboard/` | Mission control: overview, lifecycle, task board, live sessions, timeline, metrics, knowledge - with the guided tour |
| `analysis/` | Recipes → report → paper draft → retrospective |

## Thirty minutes, hands on

```bash
docker compose up            # 1. the whole stack + demo data
open http://127.0.0.1:8000   # 2. the tour starts on first visit
```

Take the tour (12 stops). Two things in the demo are *deliberately* broken
so you can watch the framework catch them: the red **seq gaps** warning (a
planted data loss - detected, never silent) and the lifecycle **parked at
the ethics gate** (data collection is unreachable until approval documents
are uploaded).

Then make the paper:

```bash
uv run analysis run   protocol/examples/pilot-study.yaml --out results
uv run analysis paper protocol/examples/pilot-study.yaml --out results
cd results/pilot-2026/paper && tectonic draft.tex && open draft.pdf
```

That's the full arc - protocol in, paper out.

## Going deeper

| You want | Read |
| -------- | ---- |
| To run any component, end to end | [`RUNBOOK.md`](RUNBOOK.md) |
| The argument and architecture | [`docs/archive/roadmap/00-VISION.md`](docs/archive/roadmap/00-VISION.md) |
| What any ID means | `requirements/srs.md` (lookup, never cover-to-cover) |
| To develop on the repo | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| To run a real participant session | [`study/pilot/runbook.md`](study/pilot/runbook.md) |
