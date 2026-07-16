# Build from the REPO ROOT (the uv workspace is the build context):
#   docker build -f middleware/Dockerfile .

# Stage 1: build the dashboard SPA (MP-06) so the middleware can serve it -
# one process is the whole stack (NFR-7).
FROM node:22-alpine AS dashboard
WORKDIR /dash
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
RUN npm run build

# Stage 2: the middleware itself.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Workspace metadata first for layer caching, then the two packages the
# service needs (middleware depends on protocol for FR-ING-6 validation).
COPY pyproject.toml uv.lock ./
COPY middleware/ middleware/
COPY protocol/ protocol/
# Documents of record for the dashboard's plain-language tooltips
# (FR-DASH-9): /requirements + /glossary parse these live.
COPY requirements/ requirements/
# Satisfy workspace member resolution without shipping unrelated code.
COPY metrics/pyproject.toml metrics/pyproject.toml
COPY analysis/pyproject.toml analysis/pyproject.toml
COPY agent-capture/pyproject.toml agent-capture/pyproject.toml

RUN uv sync --frozen --no-dev --package middleware

COPY --from=dashboard /dash/dist dashboard/dist

ENV MIDDLEWARE_DB=/data/middleware.sqlite3 \
    MIDDLEWARE_DATA_DIR=/data \
    MIDDLEWARE_PROTOCOL=/app/protocol/examples/pilot-study.yaml \
    MIDDLEWARE_DASHBOARD=/app/dashboard/dist

EXPOSE 8000
VOLUME /data

HEALTHCHECK --interval=5s --timeout=3s --retries=12 CMD \
    uv run python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uv", "run", "python", "-m", "middleware"]
