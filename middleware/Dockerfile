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
COPY metrics/pyproject.toml metrics/pyproject.toml
COPY agent-capture/pyproject.toml agent-capture/pyproject.toml

RUN uv sync --frozen --no-dev --package middleware

COPY --from=web /web/dist platform/dist

ENV MIDDLEWARE_DATA_DIR=/data \
    MIDDLEWARE_PROTOCOL=/app/protocol/examples/pilot-study.yaml \
    MIDDLEWARE_WEB=/app/platform/dist

EXPOSE 8000
# Uploaded artifacts (consent PDFs, paper PDFs) live under here as plain
# files — only their hash/path go in Postgres. On Railway this path must be
# backed by an attached Volume (see railway.toml) or every redeploy/restart
# silently drops them; docker-compose.yml already mounts a named volume here
# for local dev.
VOLUME /data

HEALTHCHECK --interval=5s --timeout=3s --retries=12 CMD \
    uv run python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uv", "run", "python", "-m", "middleware"]
