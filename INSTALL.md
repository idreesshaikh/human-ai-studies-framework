# Install

Two routes. Docker needs less on your machine; the native route is faster to
iterate on. Both start from a clone of the repository.

Read [REQUIREMENTS.md](REQUIREMENTS.md) first if you want to know what the
artifact needs before installing anything. Short version: Python 3.12+, uv,
Node 22+, no credentials, no network after install.

## Route A — Docker (least setup)

```bash
docker compose up --build
```

This starts the middleware, PostgreSQL, and a synthetic demo study. Open
<http://localhost:8000>. Stop with Ctrl-C; `docker compose down -v` also drops
the volumes.

## Route B — Native

```bash
uv sync --all-packages --frozen
npm --prefix platform ci
npm --prefix platform run build
uv run python -m middleware serve
```

Open <http://localhost:8000>. Storage defaults to
`.study-data/middleware.sqlite3`; no database service is required. The paper
index imports in the background on first start, or explicitly with
`uv run python -m middleware corpus-import`.

`--frozen` installs exactly the committed `uv.lock`. Drop it only if you
intend to re-resolve.

## Smoke test (about 10 minutes)

Each step is independent and prints its own verdict. Run them from the
repository root after either install route.

**1. The test suite.** No network or credentials required:

```bash
uv run pytest -q
```

**2. Workspace consistency and the size budget.** Fails if any workspace
member is missing from `testpaths` or the coverage source list — that is how a
package's tests get silently skipped:

```bash
uv run python scripts/check_workspace_config.py
```

**3. Protocol validation.** Checks a study protocol against the schema and
confirms every research question is covered by the analysis plan:

```bash
uv run protocol validate protocol/examples/pilot-study.yaml
```

Expected: `OK: ... is a valid study protocol (protocolVersion 4).`

To see validation *reject* something, run it against a broken fixture:

```bash
uv run protocol validate protocol/tests/fixtures/broken-missing-conditions.yaml
```

**4. The analysis catalogue.** Lists every recipe with the research questions
it answers and the event type it requires:

```bash
uv run analysis list
```

This is the core claim in one screen: a recipe cannot be planned unless the
protocol captures the event it needs.

**5. Lint.** The repository is clean under its own ruleset:

```bash
uv run ruff check .
```

## Provenance: what the numbers mean

The artifact ships no participant data and none is required. To exercise the
capture and analysis path, use the dry-run generator from the web workspace,
which writes labelled synthetic sessions.

Every synthetic row carries `synthetic: true`. Any report or figure computed
from such rows is banner-stamped as **SYNTHETIC DATA — not a research
finding**, figures are watermarked, and `analysis run` exits non-zero on a
dataset that mixes synthetic and participant rows unless
`--allow-mixed-provenance` is passed deliberately.

So a reviewer will see statistics, plots, and a full report — all correctly
labelled as describing simulated input. They demonstrate that the pipeline
connects end to end. They are not findings about how developers work, and the
tool is built so they cannot be mistaken for any.

## Participant session (optional)

Exercising TERN needs the VS Code extension. Install the VSIX from the
repository's releases via **Extensions: Install from VSIX…**, or build it
following [extension/docs/development.md](extension/docs/development.md).
The [rehearsal guide](docs/demo-runbook.md) walks the complete flow from
enrollment through export.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `uv: command not found` | Install uv, see [REQUIREMENTS.md](REQUIREMENTS.md). |
| Frontend shows a connection error | The middleware is not running; start it first. |
| Design conversation unavailable | Expected without `MISTRAL_API_KEY`. Everything else works. |
| Port 8000 in use | Stop the other process, or set a different port in the server config. |
