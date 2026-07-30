# PHOENIX: Framework for Conducting Human-AI Studies

*PHOENIX: **P**rotocol for **H**uman-**O**riented **E**vidence, **N**etworked
**I**teration & e**X**perimentation, reborn each phase, the mythical bird
matching the platform's own evolution-from-feedback story.*

[![CI](https://github.com/idreesshaikh/human-ai-studies-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/idreesshaikh/human-ai-studies-framework/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](pyproject.toml)
[![TypeScript](https://img.shields.io/badge/TypeScript-React%2019-3178C6.svg?logo=typescript&logoColor=white)](platform/package.json)

An open-source platform that carries a human-AI developer study from research
question to publishable paper on a single timeline, with one command.

You describe a study in one YAML file: the research questions, the conditions
(for example, coding with AI versus without), the participants, the
instruments, and the analyses. The platform does the rest. It configures the
instruments, guards the study lifecycle so that no data is collected before
ethics approval is uploaded, records every session from four angles, runs the
analyses, and generates a compilable LaTeX paper draft populated with your real
numbers.

## Contents

- [The four angles, one timeline](#the-four-angles-one-timeline)
- [Quick start](#quick-start)
- [Repository layout](#repository-layout)
- [Highlights](#highlights)
- [Documentation](#documentation)
- [For researchers](#for-researchers)
- [Contributing](#contributing)
- [License](#license)

## The four angles, one timeline

Every data point carries the same participant, condition, and session keys plus
a timestamp, so all four streams join cleanly in analysis.

| Angle | What gets captured | How |
| ----- | ------------------ | --- |
| **How it felt** | fatigue micro-surveys timed into typing pauses, stuck-moment detection, end-of-session debrief | VS Code extension, unobtrusive in-editor surfaces |
| **What they did** | tab switches, edits with provenance (typed, pasted, or AI-generated), scroll coverage, time spent reviewing AI suggestions before acceptance | VS Code extension |
| **What the code looked like** | nine complexity measurements over time-series snapshots of the workspace, plus task pass/fail ground truth | static analysis and a shadow git repository |
| **What the AI did** | conversation turns, tool calls, human-AI reliance loops | Claude Code hooks and transcript import |

Privacy is built in rather than bolted on. Instruments record aggregates,
shapes, and timings, never raw code, keystrokes, or clipboard content.
Participant data stays on the researcher's machine and never enters git.

## Quick start

**Prerequisites:** Docker (for the one-command demo), or Python 3.12 with
[uv](https://docs.astral.sh/uv/) and Node.js 22+ to run components directly.

```bash
git clone https://github.com/idreesshaikh/human-ai-studies-framework.git
cd human-ai-studies-framework
docker compose up
# open http://127.0.0.1:8000 for the platform, pre-loaded with a demo study
```

The demo explains itself. Two things are deliberately broken so you can watch
the platform catch them: a planted data loss (flagged, never silent) and a
lifecycle parked at its ethics gate.

To work without Docker, or to see every command, read the
[operator's guide](RUNBOOK.md).

```bash
# The full arc, protocol in to paper out:
uv sync --all-packages
uv run analysis run   protocol/examples/pilot-study.yaml --out results
uv run analysis paper protocol/examples/pilot-study.yaml --out results
```

## Repository layout

```
protocol/        Study-as-code: validate a protocol, drive its lifecycle,
                 derive every instrument's configuration from it
extension/       VS Code extension participants run (the two human angles)
metrics/         Nine code-complexity measurements
agent-capture/   The AI's side: hooks, transcripts, snapshots, task harness
curated/         The curated-dataset leg: normalizer, GitHub mining adapter,
                 authorship heuristics, threats record
middleware/      The hub on port 8000: ingestion, storage, integrity
                 checks, the joined dataset, and it serves the platform
platform/        The web app (React 19): the design conversation, the study
                 workspace (Library = live paper ingest, citation
                 constellation, and grounded assistant; Data; Lifecycle),
                 projects, and the evolution surfaces
analysis/        Pluggable analysis recipes, per-question report,
                 LaTeX paper draft, and post-study retrospective
```

## Highlights

- **The study evolves in the open.** Mid-study changes are spoken in the
  conversation, compiled deterministically, and, once ethics approval is in
  place, routed through version-visible, consent-gated amendments. Nothing is
  silent.
- **Honest statistics, enforced.** Every result reports an exact test, an
  effect size, and per-group sample sizes. The statistics layer makes a bare
  p-value impossible to emit.
- **Papers become recipes.** Two published studies' analysis methods run as
  built-in recipes on your data, with citations included.
- **Byte-reproducible replication.** A finished study exports a replication
  kit that regenerates the report byte for byte from a fresh checkout, proven
  in tests.
- **It studies itself.** The platform logs its own defects during a study and
  drafts an improvement proposal afterwards, which a human approves.
- **Everything external is optional.** Semantic Scholar, an LLM key (Mistral
  by default, or any OpenAI-compatible endpoint), SonarQube, and login
  providers each degrade gracefully, so the platform runs fully offline on
  one laptop.

## Documentation

| You want to | Read |
| ----------- | ---- |
| Get the whole picture in plain language, then click through it | [`TOUR.md`](TOUR.md) |
| Run any component, end to end, with troubleshooting | [`RUNBOOK.md`](RUNBOOK.md) |
| Deploy it (free-tier demo, persistent instance, releases) | [`RUNBOOK.md`](RUNBOOK.md) |
| Contribute (setup, gates, architecture, invariants) | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| See the formal requirements and decision record | [`requirements/`](requirements/README.md) |
| Follow the phase plan, phase by phase | [`docs/roadmap/`](docs/roadmap/README.md) |

## For researchers

This platform is itself the product of a requirements-engineering research
project. The central claim is that a study protocol is a machine-readable
requirements specification ("study-as-code"). The platform's complete
requirements record, in which every feature traces to a numbered requirement
and every dependency decision is argued, lives in
[`requirements/`](requirements/). If you use the platform in your research,
that directory is also the most precise description of what it guarantees.

## Contributing

Contributions are welcome. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md) for
local setup, the test and lint gates, the architecture, and the invariants that
keep the science honest. Please open an issue to discuss substantial changes
before sending a pull request.

## License

Released under the MIT License. See [`LICENSE`](LICENSE) for details.
