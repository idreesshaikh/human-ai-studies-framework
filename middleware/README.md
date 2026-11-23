# Study server

FastAPI service for study design, participant pairing, event and metric ingest,
literature retrieval, and exports. It serves the built web app at the same origin.

## Run

From the repository root, copy `.env.example` to `.env.local` once and keep any
local settings you already have.

```bash
uv sync --package middleware --no-dev --frozen
npm --prefix platform ci
npm --prefix platform run build
uv run --no-sync --env-file .env.local python -m middleware serve
```

Storage defaults to SQLite at `.study-data/middleware.sqlite3`. Set
`DATABASE_URL` to connect to your PostgreSQL database.

To load a protocol directly:

```bash
MIDDLEWARE_PROTOCOL=protocol/examples/pilot-study.yaml uv run --no-sync --env-file .env.local python -m middleware
```

Pass `.env.local` with `--env-file` each time you start the server. The sample
binds to loopback. Use an explicit listen address, access controls, and HTTPS
for a deployment that participants will reach. [Access and capture](../SECURITY.md#access-and-capture)

## Configuration

| Variable | Use |
| --- | --- |
| `MIDDLEWARE_HOST` | Listen address. The sample uses `127.0.0.1`; without the setting the server binds to `0.0.0.0` |
| `MIDDLEWARE_PORT` | Listen port; defaults to 8000 |
| `MIDDLEWARE_DB` | SQLite path; defaults to `.study-data/middleware.sqlite3` |
| `DATABASE_URL` | Optional PostgreSQL URL; takes precedence over SQLite |
| `MIDDLEWARE_DATA_DIR` | Uploaded files and local study artifacts |
| `MIDDLEWARE_PROTOCOL` | Optional boot-protocol YAML |
| `MIDDLEWARE_WEB` | Built frontend directory; defaults to `platform/dist` |
| `MIDDLEWARE_API_ONLY` | Set to `1` to run without a built frontend |
| `MIDDLEWARE_AUTH` | `none` (default, single user) or `token` |
| `MIDDLEWARE_TOKEN` | Shared bearer token for token mode |
| `LLM_API_KEY` | Enables the design conversation and model-assisted matching |
| `LLM_BASE_URL` | Chat-completions API base or full URL; defaults to Mistral's API; local servers need no key |
| `LLM_MODEL` | Shared model (default `ministral-14b-latest`) |
| `LLM_DESIGN_MODEL` | Optional design-only model override |
| `LLM_TIMEOUT_S` | Request timeout in seconds; default 60, range 1–600 |
| `LLM_STREAM_TIMEOUT_S` | Stream timeout in seconds; default 120, range 1–1800 |
| `LLM_MAX_RETRIES` | Retries for 429, transient server and connection failures; default 2, range 0–5 |
| `LLM_ALLOW_HTTP` | Set to 1 to allow plain HTTP to a non-local host |
| `MIDDLEWARE_CORPUS_BOOTSTRAP` | Set to 0 to disable background corpus import |
| `MIDDLEWARE_REFRESH_INTERVAL_H` | Optional interval for scheduled paper refreshes; unset disables the scheduler |
| `MIDDLEWARE_REFRESH_QUERIES` | Optional JSON file with refresh queries |
| `MIDDLEWARE_CONTACT_EMAIL` | Contact address in outbound arXiv requests |
| `MIDDLEWARE_S2_API_KEY` | Optional Semantic Scholar key for higher rate limits |

## Model settings and troubleshooting

The [model setup guide](../README.md#connect-a-model) has configurations for
Mistral, Ollama, and other OpenAI-compatible providers. Use a model that accepts
`response_format: json_object` on its chat-completions endpoint. Base URLs ending
in `/v1` are extended to `/v1/chat/completions`. You can also pass the full
chat-completions URL.

| Symptom | What to check |
| --- | --- |
| Design assistant says no model is connected | Start the server with `--env-file .env.local` and confirm your provider key or local endpoint is set. |
| Provider rejected the request | Confirm the key is active and has access to the exact `LLM_MODEL` or `LLM_DESIGN_MODEL` you selected. |
| Ollama times out or returns an unavailable model | Check that Ollama is running and the configured model appears in `ollama list`. Allow a longer timeout on slower hardware. |
| A model replies without a usable design | Confirm the endpoint and model support JSON output. You can continue from a template or enter the protocol manually. |

Restart StudyLoop after changing the settings. If port 8000 is in use, run
`uv run --no-sync python scripts/run_demo.py --port 8010` for the demo or set
`MIDDLEWARE_PORT=8010` in `.env.local` for the regular server.

Adding or searching for papers by arXiv id or DOI makes outbound requests to the
Semantic Scholar API. Results are cached in the database, so repeat lookups of the
same paper work offline.

## Commands

`uv run python -m middleware <command>`:

| Command | What it does |
| --- | --- |
| `serve` | Run the server (default) |
| `corpus-import` | Import the bundled literature corpus |
| `corpus-verify` | Check the imported corpus is complete |
| `corpus-enrich` | Fill in missing abstracts from Semantic Scholar |
| `corpus-curate --dry-run` | Preview literature curation using stored metadata; makes no network calls or changes |
| `corpus-curate` | Refresh literature metadata and apply curation decisions |
| `corpus-review` | List literature awaiting review |
| `templates` | Validate and list the template registry |
| `seed-example` | Add one labelled synthetic example study (protocol, plan, links, simulated sessions); idempotent |

The default access mode is single-user. To require a shared token, set
`MIDDLEWARE_AUTH=token` and `MIDDLEWARE_TOKEN`. See the
[security policy](../SECURITY.md).

Scheduled refreshes collect candidates; they do not run curation. Review the
curation preview before applying it, because curation can hide papers from search.

## Data flow

`POST /ingest/events` accepts event batches. Events are idempotent on
`(sessionId, source, seq)`; metrics are idempotent by content hash. Unknown
schema versions and protocol mismatches are stored with integrity flags.
Pairing credentials stamp session identity at ingest.

Use `GET /sessions/{id}/gaps` to inspect sequence gaps and
`GET /studies/{id}/dataset?format=json|csv` for an export. Dataset, notebook, and
replication-kit reads are scoped through the study's session mappings.
The running service's `/docs` page lists the complete API.

`POST /studies/{id}/plan` saves recruitment assumptions against the recorded protocol. Pilot updates, audit decisions and version/lineage records are described in [the planner guide](../docs/planner.md).

Optional producers share TERN's protocol-derived manifest; see
[agent capture](../agent-capture/README.md). The capture contract describes
capabilities and privacy policy; it is not a bearer credential.

## Development

Run `uv run pytest middleware`.

See [template review](docs/templates.md) for the corpus-to-template workflow.

## Planning and protocol v6

`GET /measure-catalog` returns the supported measurement declarations for a
signed-in identity. `POST /studies/{id}/measure-suggestions` requires contribution
access and returns read-only alias matches with `calibrated: false`. Confirmation
in Setup declares the corresponding capture, survey and analysis. Unsupported
designs and unresolved custom outcomes are explicit; editing v6 keeps existing
measurement definitions and configuration.

See [planner methods and API](../docs/planner.md). Plans, pilot tags and audit decisions use study-scoped authorization. `MIDDLEWARE_WEB` is resolved relative to the repository root. The default server requires a compiled frontend; `MIDDLEWARE_API_ONLY=1` allows an explicit API-only process. `/health` reports build availability and its hash.
