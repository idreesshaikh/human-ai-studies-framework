# Build from the REPO ROOT (the uv workspace is the build context):
#   docker build -f middleware/Dockerfile .

# Stage 1: build the React `platform/` SPA so the middleware can serve it -
# one process is the whole stack (NFR-7).
FROM node:22-alpine AS web
WORKDIR /web
COPY platform/package.json platform/package-lock.json ./
RUN npm ci
COPY platform/ ./
RUN npm run build

# Stage 2: the middleware itself.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Workspace metadata first for layer caching, then the packages the service
# needs at runtime in full: protocol (join-key validation) and curated (the
# curated-dataset leg the mining endpoints import).
COPY pyproject.toml uv.lock ./
COPY middleware/ middleware/
COPY protocol/ protocol/
COPY curated/ curated/
# Documents of record for the platform's plain-language tooltips
# (FR-DASH-9): /requirements + /glossary parse these live.
COPY requirements/ requirements/
# Satisfy workspace member resolution without shipping unrelated code.
COPY metrics/pyproject.toml metrics/pyproject.toml
COPY analysis/pyproject.toml analysis/pyproject.toml
COPY agent-capture/pyproject.toml agent-capture/pyproject.toml

RUN uv sync --frozen --no-dev --package middleware

COPY --from=web /web/dist platform/dist

ENV MIDDLEWARE_DB=/data/middleware.sqlite3 \
    MIDDLEWARE_DATA_DIR=/data \
    MIDDLEWARE_PROTOCOL=/app/protocol/examples/pilot-study.yaml \
    MIDDLEWARE_WEB=/app/platform/dist

EXPOSE 8000
VOLUME /data

HEALTHCHECK --interval=5s --timeout=3s --retries=12 CMD \
    uv run python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uv", "run", "python", "-m", "middleware"]
