#!/bin/sh
# Boot the middleware, then (re)seed the demo study once /health answers.
# Replay is idempotent on (sessionId, seq) (FR-ING-2), so reseeding on
# every boot is safe — it keeps the ephemeral Railway demo populated.
# Seed failures never kill the server.
set -eu

# Same precedence as Settings.port (middleware/src/middleware/settings.py):
PORT="${MIDDLEWARE_PORT:-${PORT:-8000}}"

uv run python -m middleware &
SERVER_PID=$!

# Background bootstrap so /health answers immediately (the importer talks to
# the DB directly, not over HTTP, so it doesn't need the server up):
#   1. Ensure the corpus is imported — required for grounded citations
#      (FR-LIT-8). Guarded by corpus-verify so it only runs on a fresh/empty
#      DB; the import itself is idempotent (upsert), so a re-run is safe.
#   2. Seed the demo study's data (opt-in via MIDDLEWARE_SEED_ON_START).
(
  if ! uv run python -m middleware corpus-verify >/dev/null 2>&1; then
    echo "corpus not present — importing (FR-LIT-8)…"
    uv run python -m middleware corpus-import || \
      echo "corpus import failed; design moves will be unsourced until it succeeds"
  fi

  if [ "${MIDDLEWARE_SEED_ON_START:-0}" = "1" ]; then
    i=0
    while [ "$i" -lt 60 ]; do
      if uv run python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT}/health', timeout=2)" 2>/dev/null; then
        uv run python middleware/scripts/replay_session.py \
          --server "http://127.0.0.1:${PORT}" || true
        break
      fi
      i=$((i + 1))
      sleep 2
    done
  fi
) &

wait "$SERVER_PID"
