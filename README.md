# PHOENIX: a conversational designer for Human–AI studies

Design a Human–AI study by talking it through, then set it up in one click.

You describe what you want to find out in plain English. PHOENIX asks the
questions a research methodologist would, suggests design choices backed by a
15,000-paper corpus, and compiles your answers into a study protocol that
validates. That protocol configures **TERN**, a VS Code extension, on each
participant's machine  -  so the study you designed is the study that runs.

It handles design, setup, and curation, then stops: you get the data, a data
dictionary, and an analysis plan, ready for your own notebook.

## How it works

1. **Talk it through.** Describe your idea; accept or reject suggestions one at
   a time. Every suggestion cites a real paper, or says it doesn't.
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
for the design conversation. PHOENIX uses Mistral Large only, keeping model
processing on the EU Mistral route. Everything else works without a model key.

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

The design conversation has one provider and one model: Mistral Large
(`mistral-large-latest`) through Mistral's EU service. There are no alternate
gateway or model routes to configure. The conversation still enforces the
platform contract itself: one question, one reversible move, valid grounding,
and compiler-checked protocol patches.

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
| What the AI does | agent-capture | Tool calls, transcripts, suggestion lifecycle (shown/accepted/dismissed) |
| What the code looks like | metrics | Complexity profile of the code produced |

Every leg is configured per study from the protocol and disclosed in the
participant's consent statement; a capture config the researcher has not
approved never runs.

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

Follow one study from idea to notebook with the real generated artifacts in
[`docs/examples/`](docs/examples/): the protocol, a dry-run report, the data
dictionary, and the starter notebook.

## Status

A master's research project, under active development. See
[`SCOPE.md`](SCOPE.md) for the boundary: the five steps this handles, what
it deliberately does not do, and the constraints that bind future work.

## License

Released under the MIT License. See [`LICENSE`](LICENSE) for details.
