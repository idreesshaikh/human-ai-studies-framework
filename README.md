# PHOENIX: run reproducible Human–AI developer studies

Configure and run a task-based Human–AI developer study from VS Code.

You describe the coding task, the AI comparison, and the outcome you want to
capture. PHOENIX turns that brief into a validated study protocol, configures
**TERN** on each participant's machine, and keeps the collected human, AI, and
code signals on the same study timeline.

It is deliberately narrow: human–AI software-development studies. It is not a
general research-methods assistant for exams, classroom studies, healthcare,
marketing, or other study families.

[![CI](https://github.com/idreesshaikh/human-ai-studies-framework/actions/workflows/ci.yml/badge.svg)](https://github.com/idreesshaikh/human-ai-studies-framework/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

The [demo runbook](docs/demo-runbook.md) covers the local researcher and
participant flow. Provider limits are recorded in the protocol's capture
configuration; unsupported transcript sources are reported instead of guessed.

## How it works

1. **Configure.** Describe the coding task, AI-assisted versus unassisted
   condition, and outcome. PHOENIX keeps the protocol explicit and reviewable.
2. **Compile.** Your accepted choices become a protocol, deterministically  -
   the same answers always produce the same protocol, no AI involved. If
   something is missing, it tells you what.
3. **Run.** The protocol configures TERN on each participant's machine and
   rotates task order so every participant meets every condition. A click
   produces participant links (`vscode://…/pair` deep links) that install the
   study on the editor  -  consent statement, capture config, everything.
4. **Collect.** TERN tracks how participants felt (short surveys), what they
   did (edits, tab switches), and what the AI did  -  never raw code, keystrokes,
   or clipboard content. Every event is stored idempotently and flagged, never
   dropped.
5. **Analyse elsewhere.** You get a dataset shaped for your design, a data
   dictionary, and a starter notebook with the exact test to run  -  curated by
   PHOENIX, analysed in whatever notebook you already use.

### The design contract

PHOENIX keeps the researcher in the loop without turning the conversation into
an empty chat stream. The assistant opens the study conversation, asks one
focused question at a time, and presents consequential suggestions as cards.
Accept, reject, or note a card and the next turn explains what changed before
moving to the next decision. Accepted cards compile deterministically into the
protocol rail; the visible rail contains only decisions the researcher can
change (research questions, design, participants, conditions, measures,
instruments, analysis, and ethics). Workspace identity and schema-required
fields remain available in the header and raw YAML.

The Library uses ingested papers as readable anchors, admits a capped mix of
related, recommended, and fresh low-citation work, and treats publication year
as a soft cue rather than a wall. This keeps citations useful without letting a
large reference list bury the papers the researcher actually chose.
Harvested graph metadata is the warm preview cache: selecting a suggestion shows
the stored title and abstract, adding it does not repeat a rate-limited provider
fetch, and removing it only removes edges touching that study copy. Shared corpus
and library records remain intact.

Before collecting anything you can run a **synthetic dry run**: simulated
participants through the real capture path, so the analysis plan is proven
against data before a single real session happens.

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/), Node 22, and a Mistral API key
for the design conversation. PHOENIX uses Mistral Medium for short protocol-shaping
turns and keeps Mistral Large for citation-heavy knowledge answers, all on the EU
Mistral route. Everything else works without a model key.

```bash
git clone https://github.com/idreesshaikh/human-ai-studies-framework.git
cd human-ai-studies-framework

uv sync --all-packages
(cd platform && npm ci && npm run build)

echo "MISTRAL_API_KEY=..." >> .env

uv run python -m middleware corpus-import   # load the 15,000-paper index
uv run python -m middleware serve           # web app on :8000
```

Open <http://localhost:8000> and describe your idea. Or use Docker, which
brings its own Postgres: `docker compose up`.

The design conversation uses the fast Mistral Medium default
(`mistral-medium-latest`) through Mistral's EU service. Set
`MISTRAL_DESIGN_MODEL` to override it when needed. Knowledge answers continue to use
Mistral Large. There are no alternate gateway routes to configure. The conversation still enforces the
platform contract itself: one question, one decision card, valid grounding,
and compiler-checked protocol patches. See the [design conversation
contract](documentation/docs/platform/design-conversation.md) and [protocol
draft contract](documentation/docs/platform/protocol-draft.md) for the
interaction and compiler rules.

### Running a session

Create a participant link on the **Participants** tab. TERN ships as a `.vsix`
on the [releases page](https://github.com/idreesshaikh/human-ai-studies-framework/releases/latest)  -
install it via **Extensions: Install from VSIX…** and open the link. The editor
joins the study already configured as designed.

### The CLI, end to end

The same paths the web app drives are one command each (all take
`MIDDLEWARE_TOKEN` for auth and `--server` to point elsewhere):

```bash
uv run python -m middleware simulate pilot-2026 --count 10 --seed 42
# simulated 10 participants (mixed): 20 sessions, 713 events, …
# plan validation: 4 recipe(s) ran, 0 check(s) failed; report under results/

uv run python -m analysis.cli run protocol/examples/pilot-study.yaml --server http://127.0.0.1:8000
uv run python -m analysis.cli notebook protocol/examples/pilot-study.yaml --server http://127.0.0.1:8000
uv run python -m analysis.cli paper protocol/examples/pilot-study.yaml
```

- `simulate`  -  synthetic dry run over plain HTTP, then validates the study's
  analysis plan against the synthetic data. Exit 0 only when every planned
  recipe ran. The server route (`POST /studies/{study_id}/simulate`) and the
  Data tab's **Run a dry run** button do the same thing in-process.
- `notebook`  -  the curated handoff: `results/<study>/notebook.ipynb` (a loaded,
  documented dataframe with every planned recipe imported  -  never run) plus a
  standalone `data-dictionary.md`.
- `paper`  -  a first-draft Methods + Results paper section, from the same plan.
- `run` / `validate` / `list`  -  execute recipes, check plan satisfaction, and
  catalogue what exists (see `uv run python -m analysis.cli --help`).

## The four angles, in one place

| Leg | Instrument | What it captures |
| --- | --- | --- |
| How participants feel | TERN probes | Fatigue Likert, end-of-session TLX survey |
| What participants do | TERN telemetry | Focus switches, edit bursts, pastes (sizes only), stuck episodes |
| What the AI does | agent-capture | Claude tool-call/transcript metadata; provider fallback is explicit |
| What the code looks like | metrics | Complexity profile of the code produced |

Every leg is configured per study from the protocol and disclosed in the
participant's consent statement; a capture config the researcher has not
approved never runs.

External producers can consume the same manifest with
`protocol derive session-manifest`; TERN remains the participant-facing capture
boundary. The platform reports what was configured and what data actually
arrived.

## Repository layout

| Folder | What's in it |
| --- | --- |
| `platform/` | The web app: design conversation and study workspace |
| `middleware/` | The server: API, search, design assistant; serves the web app |
| `protocol/` | Study schema, validator, counterbalanced assignment |
| `extension/` | TERN, the VS Code extension participants run |
| `templates/` | 16 ready-made study designs, each citing the papers behind it |
| `analysis/` | The recipe catalogue: which exact test to run for which design |
| `agent-capture/` | The AI's side: transcripts, snapshots, task harness |
| `metrics/` | Code-complexity measurements |
| `curated/` | Dataset curation and authorship checks |

## Worked example

For the complete local PHOENIX + TERN walkthrough, including participant
rehearsal, screenshots, recovery notes, and the researcher notebook handoff,
see the [demo runbook](docs/demo-runbook.md).

Follow one study from idea to notebook with the real generated artifacts in
[`docs/examples/`](docs/examples/): the protocol, a dry-run report, the data
dictionary, and the starter notebook.

## Status

A master's research project, under active development. See
[`SCOPE.md`](SCOPE.md) for the boundary: the five steps this handles, what
it deliberately does not do, and the constraints that bind future work.

## License

Released under the MIT License. See [`LICENSE`](LICENSE) for details.
