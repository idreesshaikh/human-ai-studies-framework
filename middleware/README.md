# Study server

FastAPI service for study design, participant pairing, event and metric ingest,
literature retrieval, and exports. It serves the built web app at the same origin.

## Run

From the repository root:

```bash
uv sync --all-packages --frozen
uv run python -m middleware serve
```

Storage defaults to SQLite at `.study-data/middleware.sqlite3`. Set
`DATABASE_URL` to use PostgreSQL. `docker compose up --build` starts PostgreSQL,
the app, and a synthetic demo in shared storage.

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
| `MISTRAL_API_KEY` | Enables the design conversation and model-assisted matching |
| `MISTRAL_DESIGN_MODEL` | Design model override |
| `MIDDLEWARE_CORPUS_BOOTSTRAP` | Set to 0 to disable background corpus import |

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

Optional producers share TERN's protocol-derived manifest; see
[agent capture](../agent-capture/README.md). The capture contract describes
capabilities and privacy policy; it is not a bearer credential.

## Development

Run `uv run pytest middleware`. Use the repository
[smoke check](../scripts/smoke.sh) only against a development instance: it creates
a synthetic study and writes test events.

`middleware/scripts/replay_session.py` replays the bundled demo recordings.
`demo-seed` creates their study mappings; both must target the same database.
See [template review](docs/templates.md) for the corpus-to-template workflow.
