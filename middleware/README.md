# Study server

FastAPI service for study design, participant pairing, event and metric ingest,
literature retrieval, and exports. It serves the built web app at the same origin.

## Run

From the repository root:

```bash
uv sync --all-packages --frozen
npm --prefix platform run build
uv run python -m middleware serve
```

Storage defaults to SQLite at `.study-data/middleware.sqlite3`. Set
`DATABASE_URL` to use PostgreSQL. `docker compose up --build` starts PostgreSQL,
and the app in shared storage.

To load a protocol directly:

```bash
MIDDLEWARE_PROTOCOL=protocol/examples/pilot-study.yaml uv run python -m middleware
```

The [.env.example](../.env.example) lists common options. Pass an environment file
explicitly with `uv run --env-file .env python -m middleware`; it is not loaded
automatically.

## Configuration

| Variable | Use |
| --- | --- |
| `MIDDLEWARE_PORT` | Listen port; defaults to `PORT`, then 8000 |
| `MIDDLEWARE_DB` | SQLite path |
| `DATABASE_URL` | PostgreSQL URL; takes precedence over the SQLite path |
| `MIDDLEWARE_DATA_DIR` | Uploaded files and local study artifacts |
| `MIDDLEWARE_PROTOCOL` | Optional boot-protocol YAML |
| `MIDDLEWARE_WEB` | Built frontend directory; defaults to `platform/dist` |
| `MIDDLEWARE_AUTH` | `none`, `token`, or `clerk` |
| `MIDDLEWARE_TOKEN` | Shared bearer token for token mode |
| `MIDDLEWARE_PUBLIC_URL` | Public base URL used in participant links |
| `MIDDLEWARE_CORS_ORIGINS` | Comma-separated origins for a separate frontend |
| `LLM_API_KEY` | Enables the design conversation and model-assisted matching |
| `LLM_BASE_URL` | Chat-completions API base or full URL; defaults to Mistral's API; local servers need no key |
| `LLM_MODEL` | Shared model (default `ministral-14b-latest`) |
| `LLM_DESIGN_MODEL` | Optional design-only model override |
| `LLM_TIMEOUT_S` | Request timeout in seconds; default 60, range 1–600 |
| `LLM_STREAM_TIMEOUT_S` | Stream timeout in seconds; default 120, range 1–1800 |
| `LLM_MAX_RETRIES` | Retries for 429, transient server and connection failures; default 2, range 0–5 |
| `LLM_ALLOW_HTTP` | Set to 1 to allow plain HTTP to a non-local host |
| `MISTRAL_API_KEY` | Legacy alias for `LLM_API_KEY` |
| `MISTRAL_MODEL` | Legacy alias for `LLM_MODEL` |
| `MISTRAL_DESIGN_MODEL` | Legacy alias for `LLM_DESIGN_MODEL` |
| `MIDDLEWARE_CORPUS_BOOTSTRAP` | Set to 0 to disable background corpus import |
| `MIDDLEWARE_S2_API_KEY` | Optional Semantic Scholar key for higher rate limits (`S2_API_KEY` is a legacy alias) |

With no model key or local endpoint configured, the design assistant replies
that no language model is connected. Templates, the quick checklist and the rest of the app keep
working. Set the key and restart the server to enable it.

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
| `templates` | Validate and list the template registry |

The default is local single-user access. In Clerk mode, configure
`MIDDLEWARE_CLERK_JWKS_URL`, `MIDDLEWARE_CLERK_ISSUER`, and
`MIDDLEWARE_CLERK_PUBLISHABLE_KEY`. See the [security policy](../docs/security.md)
and [Clerk appearance notes](docs/clerk-appearance.md).

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
