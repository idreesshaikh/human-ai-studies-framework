# Configuration

The StudyLoop server reads its settings from environment variables. You keep them
in a local file, `.env.local`, and pass it on every start with `--env-file`. This
page lists the server settings, how access works and the server's commands. The
model settings have [their own page](model-providers.md).

```bash
cp .env.example .env.local
uv run --no-sync --env-file .env.local python -m middleware
```

Restart the server after you change the file. Git ignores `.env.local`, so
credentials stay out of the repository.

## Server settings

| Variable | Use |
| --- | --- |
| `MIDDLEWARE_HOST` | Listen address. The sample uses `127.0.0.1`; without the setting the server binds to `0.0.0.0` |
| `MIDDLEWARE_PORT` | Listen port; defaults to 8000 |
| `MIDDLEWARE_DB` | SQLite path; defaults to `.study-data/middleware.sqlite3` |
| `DATABASE_URL` | Optional PostgreSQL URL; takes precedence over SQLite |
| `MIDDLEWARE_DATA_DIR` | Uploaded files and local study artifacts |
| `MIDDLEWARE_PROTOCOL` | Optional boot-protocol YAML, for a single study that never goes through Setup |
| `MIDDLEWARE_WEB` | Built web app directory; defaults to `platform/dist` |
| `MIDDLEWARE_API_ONLY` | Set to `1` to run without a built web app |
| `MIDDLEWARE_AUTH` | `none` (default, single user) or `token` |
| `MIDDLEWARE_TOKEN` | Shared token for token mode |
| `MIDDLEWARE_CORPUS_BOOTSTRAP` | Set to `0` to turn off the background import of the paper corpus |
| `MIDDLEWARE_REFRESH_INTERVAL_H` | Scheduled paper refresh interval in hours, at least 1. Defaults to 24 when corpus bootstrapping is enabled. Set to `off` for manual refreshes |
| `MIDDLEWARE_REFRESH_QUERIES` | Optional JSON file with refresh queries |
| `MIDDLEWARE_CONTACT_EMAIL` | Contact address sent with requests to arXiv |
| `MIDDLEWARE_S2_API_KEY` | Optional Semantic Scholar key for higher rate limits. StudyLoop paces its own requests to one per second either way |
| `MIDDLEWARE_LIVE_SEARCH` | Set to `0` to stop design-chat turns from searching Semantic Scholar when the local library has little on a topic. The search sends keywords from the conversation, never the full message |

The `LLM_*` settings are listed under [Connect a model](model-providers.md#settings).

## Access

The default mode is single-user: anyone who can reach the server is you. It is for
a trusted machine. To require a shared token, set `MIDDLEWARE_AUTH=token` and
`MIDDLEWARE_TOKEN`; PHOENIX then asks for a **Session token** before it shows a
study. Before participants on other machines connect, run the server behind HTTPS
with an explicit listen address and the access controls you need. Passing tests is
not a security or ethics certification. See the
[security policy](https://github.com/idreesshaikh/human-ai-studies-framework/blob/main/SECURITY.md#access-and-capture).

## Commands

`uv run --no-sync --env-file .env.local python -m middleware <command>`:

| Command | What it does |
| --- | --- |
| `serve` | Run the server (the default) |
| `seed-example` | Add the labelled synthetic example study; safe to repeat |
| `templates` | Validate and list the template registry |
| `corpus-import` | Import the bundled paper corpus |
| `corpus-verify` | Check the imported corpus is complete |
| `corpus-enrich` | Fill in missing abstracts from Semantic Scholar |
| `corpus-curate --dry-run` | Preview curation using stored metadata; makes no network calls or changes |
| `corpus-curate` | Refresh paper metadata and apply curation decisions |
| `corpus-review` | List papers awaiting review |
| `corpus-refresh`, `corpus-candidates`, `corpus-decide` | Collect and decide on new papers; see [Keep the literature library current](literature-library.md) |

## Next steps

- [Connect a model](model-providers.md)
- [Keep the literature library current](literature-library.md)
