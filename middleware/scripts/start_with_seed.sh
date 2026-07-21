#!/bin/sh
# Boot the middleware, then (re)seed the demo study once /health answers.
# Replay is idempotent on (sessionId, seq) (FR-ING-2), so reseeding on
# every boot is safe — it keeps the ephemeral Railway demo populated.
# Seed failures never kill the server.
set -eu

PORT="${PORT:-${MIDDLEWARE_PORT:-8000}}"

uv run python -m middleware &
SERVER_PID=$!

if [ "${MIDDLEWARE_SEED_ON_START:-0}" = "1" ]; then
  (
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
  ) &
fi

wait "$SERVER_PID"
