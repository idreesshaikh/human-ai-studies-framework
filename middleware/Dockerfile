# Build from the REPO ROOT (the uv workspace is the build context):
#   docker build -f middleware/Dockerfile .

# Stage 1: build the React platform/ SPA so the middleware can serve it.
FROM node:22-alpine AS web
WORKDIR /web
COPY platform/package.json platform/package-lock.json ./
RUN npm ci
COPY platform/ ./
RUN npm run build

# Stage 2: the middleware itself — single process serves API + SPA (NFR-7).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Workspace metadata first for layer caching.
COPY pyproject.toml uv.lock ./
COPY middleware/ middleware/
COPY protocol/ protocol/
COPY curated/ curated/
COPY analysis/ analysis/
COPY requirements/ requirements/
# The template registry (FR-TPL): read from templates/registry at runtime by
# template_registry.py. Without it the deployed platform shows zero templates.
COPY templates/ templates/
COPY metrics/pyproject.toml metrics/pyproject.toml
COPY agent-capture/pyproject.toml agent-capture/pyproject.toml

RUN uv sync --frozen --no-dev --package middleware

COPY --from=web /web/dist platform/dist

# The corpus the grounding engine reads (FR-LIT-8): the Tier A seed table and
# the harvested Tier B index. Without these the `papers` table can't be
# imported, so `match_papers` finds nothing and every design move degrades to
# "unsourced". A late layer (changes only on re-harvest) so it doesn't bust the
# dependency cache. PDFs are gitignored/optional — title+why text suffices.
COPY docs/papers/README.md docs/papers/corpus-index.json docs/papers/

ENV MIDDLEWARE_DATA_DIR=/data \
    MIDDLEWARE_PROTOCOL=/app/protocol/examples/pilot-study.yaml \
    MIDDLEWARE_WEB=/app/platform/dist

EXPOSE 8000
# Uploaded artifacts (consent PDFs, paper PDFs) live under here as plain
# files — only their hash/path go in Postgres. On Railway this path must be
# backed by an attached Volume (see railway.toml) or every redeploy/restart
# silently drops them; docker-compose.yml already mounts a named volume here
# for local dev. No Dockerfile VOLUME instruction here — Railway's builder
# rejects it ("use Railway Volumes" instead), and it isn't needed: Railway
# mounts its Volume at /data by dashboard configuration regardless of any
# image-level VOLUME declaration.

HEALTHCHECK --interval=5s --timeout=3s --retries=12 CMD \
    uv run python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uv", "run", "python", "-m", "middleware"]
