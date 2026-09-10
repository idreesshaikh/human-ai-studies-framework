# Contributing

Useful contributions make a study easier to run, its data more trustworthy, or
the implementation easier to maintain. Small, focused changes are welcome.

## Set up

Use Python 3.12+, uv, and Node.js 22+. From the repository root:

```bash
uv sync --all-packages --frozen
npm --prefix platform ci
npm --prefix extension ci
```

The [README](../README.md) explains how to run the app. Tests use temporary
databases and model fixtures; no live research data or model key is needed.
Use a separate database for manual experiments.

Read the [architecture guide](architecture.md) to find the relevant package.
For frontend work, see [platform development](../platform/docs/development.md);
for TERN, see [extension development](../extension/docs/development.md).

## Check your changes

Run checks for the code you touched. CI checks the whole workspace:

```bash
uv run ruff check .
uv run python scripts/check_workspace_config.py
uv run pytest --cov --cov-report=term-missing --cov-fail-under=79
uv run coverage report --include='metrics/src/*' --fail-under=95
npm --prefix extension run check
npm --prefix platform run check
```

For UI changes, run `npx playwright install chromium` and `npm run a11y`
from `platform/`.

For the documentation site, from the repository root:

```bash
uv sync --group docs --frozen
uv run --group docs mkdocs build --config-file documentation/mkdocs.yml --strict
```

`bash scripts/smoke.sh` checks the container stack and writes an analysis report
to a temporary directory. It ingests synthetic sessions: use a development
instance, never a participant database.

## Research and data contracts

- Scope reads and exports to their study. Knowing a session ID does not grant
  access to it.
- Preserve participant, condition, task, session, producer, sequence, timestamp,
  and schema version throughout capture and export.
- Keep compilation deterministic. Validate on the server before applying a
  protocol; the browser preview is advisory.
- Test statistical changes on constructed data with known answers and missing
  data. Keep simulated rows separate from participant findings.
- Respect each instrument's disclosed content policy. TERN excludes raw source,
  keystrokes, and clipboard text; external tools have separate policies.
- Keep participant data, credentials, databases, and generated builds out of
  contributions. Use small synthetic test fixtures.

## Propose a change

Describe the problem, resulting behavior, and checks you ran. For a bug, include
reproduction steps and expected versus observed behavior. Explain changes to
dependencies, exported schemas, and public commands.

Update TERN's changelog for extension changes. Existing browser selectors should
remain stable unless a change requires replacing them.

Use [private reporting](security.md) for vulnerabilities or participant-data
exposure. Contributions are offered under the [MIT License](../LICENSE).
