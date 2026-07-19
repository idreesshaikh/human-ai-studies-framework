# Framework for Conducting Human-AI Studies

[![CI](https://github.com/idreesshaikh/human-ai-studies-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/idreesshaikh/human-ai-studies-framework/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**An open-source platform that takes a human-AI developer study from
research question to publishable paper — on one timeline, with one command.**

You describe your study in a single YAML file: the research questions, the
conditions (say, coding *with* AI vs *without*), the participants, the
instruments, the analyses. The platform does the rest — it configures the
instruments, guards the study lifecycle (no data collection before ethics
approval is uploaded), records every session from four angles, runs the
analyses, and generates a compilable LaTeX paper draft with your real
numbers in it.

## The four angles, one timeline

Every data point carries the same participant / condition / session keys
and a timestamp, so all four streams join cleanly in analysis:

| Angle | What gets captured | How |
| ----- | ------------------ | --- |
| 🧠 **How it felt** | fatigue micro-surveys timed into typing pauses, stuck-moment detection, end-of-session debrief | VS Code extension, unobtrusive in-editor surfaces |
| ⌨️ **What they did** | tab switches, edits with provenance (typed / pasted / AI-generated), scroll coverage, how long AI suggestions were reviewed before acceptance | VS Code extension |
| 📐 **What the code looked like** | nine complexity measurements over time-series snapshots of the workspace, plus task pass/fail ground truth | static analysis + a shadow git repo |
| 🤖 **What the AI did** | conversation turns, tool calls, human-AI reliance loops | Claude Code hooks + transcript import |

Privacy is built in, not bolted on: instruments record aggregates, shapes,
and timings — never raw code, keystrokes, or clipboard content. Participant
data stays on the researcher's machine and never enters git.

## Quick start

```bash
git clone https://github.com/idreesshaikh/human-ai-studies-framework.git
cd human-ai-studies-framework
docker compose up
# open http://127.0.0.1:8000 — the platform, pre-loaded with a demo study
```

The demo explains itself. Two things are deliberately broken so you can
watch the platform catch them — a planted data loss (flagged, never
silent) and a lifecycle parked at its ethics gate.

Working without Docker, or want every command? See the
[operator's guide](RUNBOOK.md).

```bash
# The full arc, protocol in → paper out:
uv sync --all-packages
uv run analysis run   protocol/examples/pilot-study.yaml --out results
uv run analysis paper protocol/examples/pilot-study.yaml --out results
```

## What's inside

```
protocol/        Study-as-code: validate a protocol, drive its lifecycle,
                 derive every instrument's configuration from it
extension/       VS Code extension participants run (the two human angles)
metrics/         Nine code-complexity measurements
agent-capture/   The AI's side: hooks, transcripts, snapshots, task harness
middleware/      The hub on port 8000 — ingestion, storage, integrity
                 checks, the joined dataset, and it serves the platform
platform/        The web app (React 19): the design conversation, the study
                 workspace (Library = live paper ingest + citation
                 constellation + grounded assistant; Data; Lifecycle),
                 projects, and the evolution surfaces
analysis/        Pluggable analysis recipes → per-question report →
                 LaTeX paper draft → post-study retrospective
```

Some things it does that we're proud of:

- **The study evolves in the open.** Mid-study changes are spoken in the
  conversation, compiled deterministically, and — after ethics approval —
  routed through version-visible, consent-gated amendments, never sneaky.
- **Honest statistics, enforced.** Every result reports an exact test, an
  effect size, and per-group sample sizes. The statistics layer makes a
  bare p-value impossible to emit.
- **Papers become recipes.** Two published studies' analysis methods run
  as built-in recipes on your data, citations included.
- **Byte-reproducible replication.** A finished study exports a
  replication kit that regenerates the report byte-for-byte from a fresh
  checkout — proven in tests.
- **It studies itself.** The platform logs its own defects during a study
  and drafts an improvement proposal afterwards (a human approves).
- **Everything external is optional.** Semantic Scholar, the Claude API,
  SonarQube, login providers — each degrades gracefully; the
  platform runs fully offline on one laptop.

## Documentation

| You want to… | Read |
| ------------ | ---- |
| Get the whole picture in plain language, then click through it | [`TOUR.md`](TOUR.md) |
| Run any component, end to end, with troubleshooting | [`RUNBOOK.md`](RUNBOOK.md) |
| Deploy it (free-tier demo, persistent instance, releases) | [`RUNBOOK.md` §9](RUNBOOK.md) |
| Contribute (setup, gates, architecture, invariants) | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| See the formal requirements & decision record | [`requirements/`](requirements/README.md) |
| The phase plan, phase by phase | [`docs/roadmap/`](docs/roadmap/README.md) |

## For researchers

This platform is itself the product of a requirements-engineering research
project: the central claim is that a study protocol *is* a machine-readable
requirements specification ("study-as-code"), and the platform's complete
requirements record — every feature traced to a numbered requirement, every
dependency decision argued — lives in [`requirements/`](requirements/). If
you use the platform in your research, that directory is also the most
precise description of what it guarantees.

## License

MIT — see [LICENSE](LICENSE).
