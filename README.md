# StudyLoop

StudyLoop helps researchers design, run and inspect studies of developers
working with AI. You describe a study in plain language; StudyLoop drafts the
whole design with sources from a bundled paper library, you review and approve
it as a versioned protocol, plan the sample size, and invite participants, whose
VS Code sessions are recorded by the TERN extension after they consent.

## Run it

You need Python 3.12+, Node.js 22+ and [uv](https://docs.astral.sh/uv/).

Once, after cloning:

```bash
uv sync --all-packages --frozen
npm --prefix platform ci
npm --prefix platform run build
cp .env.example .env.local
```

Put a Mistral API key in `.env.local` as `LLM_API_KEY=...`. Without one the
design chat is off; templates, the checklist, capture and exports still work.

Start StudyLoop:

```bash
uv run --no-sync --env-file .env.local python -m middleware
```

Open <http://127.0.0.1:8000>. Ctrl+C stops it.

- The first start imports the paper library in the background (about 90
  seconds). Sources appear on the design cards once
  <http://127.0.0.1:8000/corpus/status> says `"ready"`. Later starts take a
  couple of seconds.
- Your studies are kept in `.study-data/`. To keep a separate set, for a talk
  for example, start with
  `MIDDLEWARE_DB=.study-data/talk/middleware.sqlite3 MIDDLEWARE_DATA_DIR=.study-data/talk`
  in front of the command.
- After `git pull`, rebuild (`npm --prefix platform run build`) and restart.

Storage, sign-in and model settings are in the [server guide](middleware/README.md).

### Look around first

To explore without a key or any setup of your own, run a throwaway copy that
contains a labelled synthetic example study (it needs the build step above):

```bash
uv run --no-sync python scripts/run_demo.py
```

Ctrl+C stops it and deletes its data. See the
[example walkthrough](docs/demo-walkthrough.md).

## How a study goes

1. **Setup:** describe the study in the chat (or pick a template), accept or
   reject each proposed decision, then approve the compiled protocol.
2. **Plan:** set your assumptions and get the sample size, saved against the
   protocol version.
3. **Run:** create participant links. Participants install
   [TERN](extension/README.md), see exactly what will be recorded, and consent
   before anything is captured.
4. **Data:** inspect sessions, mark pilots, record inclusion decisions, and
   export datasets, design cards and replication kits.

Calculations depend on their stated assumptions. TERN can record accepted inline
suggestions and agent activity from installed hooks, but it cannot verify that a
no-AI group stayed clean. Provider queries, bulk-edit heuristics, and pastes are
ambiguous; missing signals do not prove that no external AI was used. Synthetic
sessions are excluded from research exports and estimates. The tool does not
certify study validity or replace ethics review and statistical judgment.

## What is in the repository

| Path | What it is |
|---|---|
| `middleware/` | The server: API, storage, model calls; serves the web app |
| `platform/` | PHOENIX, the researcher web app (React) |
| `extension/` | TERN, the VS Code extension participants install |
| `protocol/` | The study protocol schema and its checks |
| `analysis/` | Sample-size planner, simulations and audits |
| `templates/` | Study design templates |
| `metrics/` | Code-quality measures computed from participants' code |
| `agent-capture/` | Claude Code hooks for recording agent activity |
| `scripts/` | The example launcher, checks and the AI-use calibration kit |
| `docs/` | Design notes and methods; `documentation/` is the user guide site |

## More

- [Architecture](docs/architecture.md), [scope](docs/scope.md) and
  [planning methods](docs/planner.md)
- [Contributing, development and checks](CONTRIBUTING.md)
- [Security and participant data](SECURITY.md)

The code is available under the [MIT License](LICENSE). External sources and
dependencies retain their own terms.
