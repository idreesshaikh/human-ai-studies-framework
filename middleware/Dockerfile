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

# Workspace metadata first for layer caching, then — in full — the three
# packages middleware declares as workspace dependencies, so uv can build each
# wheel: protocol (join-key validation), curated (the mining leg), and analysis
# (the retrospective + paper endpoints). All three need their source, not just
# a pyproject stub.
COPY pyproject.toml uv.lock ./
COPY middleware/ middleware/
COPY protocol/ protocol/
COPY curated/ curated/
COPY analysis/ analysis/
# Documents of record for the platform's plain-language tooltips
# (FR-DASH-9): /requirements + /glossary parse these live.
COPY requirements/ requirements/
# The remaining workspace members are NOT middleware dependencies; their
# pyproject alone satisfies workspace resolution, and uv never builds them.
COPY metrics/pyproject.toml metrics/pyproject.toml
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
