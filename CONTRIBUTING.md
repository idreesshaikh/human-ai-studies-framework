# Contributing

StudyLoop includes the PHOENIX researcher workspace and TERN participant extension. Keep
changes focused, preserve protocol/API identifiers, and include regressions for
capture, approval, permissions, analysis, and exports.

## Reproduce the checks

Use Python 3.12+, Node.js 22+, and uv. From the repository root:

```bash
uv sync --all-packages --group docs --frozen
npm --prefix platform ci
npm --prefix extension ci
uv run --no-sync ruff check .
uv run --no-sync python scripts/check_workspace_config.py
uv run --no-sync pytest --cov --cov-report=term-missing --cov-fail-under=79
uv run --no-sync coverage report --include='metrics/src/*' --fail-under=95
npm --prefix platform run check
npm --prefix extension run check
uv run --no-sync mkdocs build --strict -f documentation/mkdocs.yml
```

CI is authoritative; do not lower coverage floors to pass a change. Install
Chromium using `npm --prefix platform exec playwright install chromium` before
browser rehearsals. Use a separate synthetic database, never a participant
deployment.

## Research and data

- Never commit `.env`, credentials, participant records, raw source snapshots,
  downloads, generated reports, model weights, or `.research-artifacts/`.
- Use clearly labelled synthetic fixtures in tests. A passing test, generated
  annotation, or simulated reviewer is not empirical evidence.
- Model/classifier adoption requires a frozen, independent evaluation. Preserve
  explicit abstention, deterministic validation, and researcher approval.
- Protocol changes need compatibility notes. Historical IDs are not UI labels;
  consult [terminology](docs/terminology.md).

## Delivery

Open a PR against `main`, link the issue, list the exact checks and remaining
limits, and obtain required code-owner review. Do not merge feature work into
an already-merged feature branch. Verify the final main tree and deployed build.
Do not bypass review rules or remove someone else's changes. Document exact
cleanup targets before deleting data or tickets.

Root and extension code carry MIT notices; preserve both attribution notices.
External papers, datasets, fonts, and dependencies retain their own terms.
See [security](SECURITY.md) for sensitive findings.
