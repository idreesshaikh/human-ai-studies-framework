# Contributing

Keep changes focused and preserve protocol, capture, approval, access, and export
contracts. Read the [architecture](docs/architecture.md) and
[scope](docs/scope.md) before proposing a feature.

## Setup and checks

Use Python 3.12+, Node.js 22+, and uv:

```bash
uv sync --all-packages --group docs --frozen
npm --prefix platform ci
npm --prefix extension ci
npm --prefix platform exec playwright install chromium
```

Run checks for the code you change. CI checks the whole workspace:

```bash
uv run --no-sync ruff check .
uv run --no-sync python scripts/check_workspace_config.py
uv run --no-sync pytest --cov --cov-report=term-missing --cov-fail-under=79
uv run --no-sync coverage report --include='metrics/src/*' --fail-under=95
npm --prefix platform run check
npm --prefix extension run check
uv run --no-sync mkdocs build --strict -f documentation/mkdocs.yml
```

`uv run --no-sync python scripts/check_demo.py` runs these gates and records
versions and logs. See [verification](docs/demo-readiness.md),
[frontend development](platform/docs/development.md), and
[extension development](extension/docs/development.md).

## Implementation contracts

- `protocol/` owns schemas and deterministic derivations; `analysis/` consumes
  protocol data without accessing middleware storage.
- `middleware/` owns API, persistence, and provider orchestration. Keep route
  handlers thin and reusable rules in service modules.
- `platform/` renders server state. Its protocol preview is advisory; server
  validation and researcher approval remain authoritative.
- Preserve study attribution, participant and session identity, producer,
  sequence, timestamps, and schema versions throughout capture and export.
- Test contract and statistical changes with meaningful synthetic cases,
  including missing data. Keep simulated observations separate from findings.

## Public repository boundary

Commit source, tests, small synthetic fixtures, and maintained documentation.
Keep participant records, consent materials, interview sources, personal paths,
credentials, research administration, paper drafts, generated reports, and
builds outside the public tree. Private working material belongs in approved
storage; `.research-artifacts/` is ignored by Git.

Check screenshots for account details, local paths, recent files, and hostnames.
Use generic identities in examples. Preserve license notices, source attribution,
and identifiers required by published integrations.

## Pull requests

Describe the problem, resulting behavior, and checks run. Explain compatibility
or dependency changes and update relevant documentation. Update TERN's changelog
for extension changes. Do not lower coverage floors to pass a change.

Use [private reporting](SECURITY.md) for vulnerabilities. Contributions are
offered under the [MIT License](LICENSE); preserve existing attribution notices.
