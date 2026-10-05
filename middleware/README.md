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
| `MISTRAL_MODEL` | Shared model (default `ministral-14b-latest`) |
| `MISTRAL_DESIGN_MODEL` | Optional design-only model override |
| `MIDDLEWARE_CORPUS_BOOTSTRAP` | Set to 0 to disable background corpus import |
| `MIDDLEWARE_S2_API_KEY` | Optional Semantic Scholar key for higher rate limits (the unprefixed `S2_API_KEY` is not read) |
| `MIDDLEWARE_SEED_ON_START` | Used by `scripts/start_with_seed.sh`; `1` (default) seeds the synthetic demo, `0` skips it |
| `MIDDLEWARE_ENRICH_ON_START` | Used by `scripts/start_with_seed.sh`; `0` (default) skips corpus enrichment, a number limits how many papers to enrich |

If `MISTRAL_API_KEY` is missing, the design assistant replies that no language
model is connected. Templates, the quick checklist and the rest of the app keep
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
| `demo-seed` | Create the synthetic demo study |
| `backup-seed` | Create the backup-session study mappings |
| `templates` | Validate and list the template registry |
| `simulate` | Dry-run a study over HTTP and check its analysis plan |

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

`GET /studies/{id}/run-plan?participantIndex=0&preview=true` previews the
participant journey from accepted decisions. Use `preview=false` for enrollment's
current protocol. The zero-based index is bounded to 0–9999. Both modes are
read-only and require project view access; neither creates participant links.

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
