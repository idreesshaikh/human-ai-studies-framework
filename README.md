# StudyLoop

StudyLoop helps researchers configure, run, and inspect human–AI developer
studies. PHOENIX provides the researcher workspace; TERN collects disclosed
events and surveys in VS Code. Both use a reviewed, versioned study protocol.

## Run locally

Requires Python 3.12+, Node.js 22+, and uv. Install once:

```bash
uv sync --all-packages --frozen
npm --prefix platform ci
cp .env.example .env.local
```

Set `LLM_API_KEY` in `.env.local` to turn on the design chat. Without a key the
chat is off; the checklist, templates, capture, and
exports still work.

Start the server, which provides the API on port 8000 and stores data in
`.study-data/`:

```bash
uv run --no-sync --env-file .env.local python -m middleware
```

In a second terminal, start the web app and open <http://localhost:5173>:

```bash
npm --prefix platform run dev
```

- On first start the server imports the bundled paper corpus in the
  background, which takes about a minute. Literature suggestions and citations
  appear once <http://127.0.0.1:8000/corpus/status> reports `"ready"`.
- The web app reloads itself when its code changes; the server does not.
  Restart the server after `git pull`.
- To serve everything from the server instead, run
  `npm --prefix platform run build` and open <http://127.0.0.1:8000>.

See the [server guide](middleware/README.md) for storage, sign-in, and model
settings.

### Example study

A disposable copy with a labelled synthetic study, for exploring without
setting anything up. It needs the built web app:

```bash
npm --prefix platform run build
uv run --no-sync python scripts/run_demo.py
```

Open <http://127.0.0.1:8000>. Ctrl+C stops it and deletes its data. The chat is
off in this mode; add `--live` to use your model provider and the paper corpus
(`uv run --no-sync --env-file .env.local python scripts/run_demo.py --live`).
See the [example walkthrough](docs/demo-walkthrough.md).

## Workflow

1. **Setup:** enter a checklist, choose a template, or use model-assisted
   authoring. Review proposed changes and approve the compiled protocol.
2. **Plan:** record recruitment assumptions and save the plan against the
   protocol version.
3. **Run:** connect participants through [TERN](extension/README.md), disclose
   the capture configuration, and obtain consent before recording.
4. **Data:** inspect sessions and integrity signals, identify pilots, and record
   inclusion decisions. Check outcome capture to find missing measurement inputs
   in a rehearsal before collecting participant data.
5. Export datasets, design cards, analysis materials, and replication kits.

Calculations depend on their stated assumptions. TERN can record accepted inline
suggestions and agent activity from installed hooks, but it cannot verify that a
no-AI group stayed clean. Provider queries, bulk-edit heuristics, and pastes are
ambiguous; missing signals do not prove that no external AI was used. Synthetic
sessions are excluded from research exports and estimates. The tool does not
certify study validity or replace ethics review and statistical judgment.

## Documentation

- [Architecture](docs/architecture.md) and [supported scope](docs/scope.md)
- [Planning methods and limits](docs/planner.md)
- [Protocol v6 example](protocol/examples/planner-v6.yaml)
- [Evidence mapping](docs/evidence-workflow.md)
- [Development and checks](CONTRIBUTING.md)
- [Security and participant data](SECURITY.md)

## Validate

```bash
npm --prefix extension ci
npm --prefix platform exec playwright install chromium
uv sync --all-packages --group docs --frozen
uv run --no-sync python scripts/check_demo.py
```

The gate runs Python, extension, frontend, browser, and documentation checks.
See [verification](docs/demo-readiness.md) for individual commands and limits.

Code is available under the [MIT License](LICENSE). External sources and
dependencies retain their own terms.
