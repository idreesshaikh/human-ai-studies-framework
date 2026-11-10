# StudyLoop

StudyLoop helps researchers configure, run, and inspect human–AI developer
studies. PHOENIX provides the researcher workspace; TERN collects disclosed
events and surveys in VS Code. Both use a reviewed, versioned study protocol.

## Run locally

Requires Python 3.12+, Node.js 22+, and uv.

```bash
uv sync --all-packages --frozen
npm --prefix platform ci
npm --prefix platform run build
uv run --no-sync python scripts/run_demo.py
```

Open <http://127.0.0.1:8000>. This starts a disposable, offline example with
labelled synthetic sessions. Use the manual checklist to create a protocol;
Ctrl+C stops the server and removes rehearsal data. See the
[example walkthrough](docs/demo-walkthrough.md).

For persistent work, run `uv run --no-sync python -m middleware` instead.
Configure storage, authentication, and optional model access using the
[server guide](middleware/README.md) and [.env.example](.env.example).
Environment files must be loaded explicitly, for example with
`uv run --env-file .env python -m middleware`.

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

Calculations depend on their stated assumptions. Capture has blind spots;
missing AI signals do not prove that no external AI was used. Synthetic sessions
are excluded from research exports and estimates. The tool does not certify
study validity or replace ethics review and statistical judgment.

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
