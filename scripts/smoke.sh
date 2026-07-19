#!/usr/bin/env bash
# Full-stack smoke test (NFR-9, roadmap/08-pilot-study.md deliverable 3).
#
#   bash scripts/smoke.sh                 # compose up --build, then verify
#   SMOKE_NO_COMPOSE=1 bash scripts/smoke.sh   # verify an already-running stack
#
# Proves, from a clean checkout: bring-up -> health -> platform served ->
# replay ingest (idempotent) -> gap detection -> one-timeline dataset export
# -> per-RQ analysis report -> paper draft (FR-ANA-6; compiled to PDF when a
# TeX engine is on PATH). Exits nonzero on the first failure.
set -euo pipefail

SERVER="${SMOKE_SERVER:-http://127.0.0.1:8000}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$(mktemp -d)"
cd "$ROOT"

step() { printf '\n== %s\n' "$*"; }
fail() { printf 'SMOKE FAIL: %s\n' "$*" >&2; exit 1; }

# -- 1. bring-up ------------------------------------------------------------
if [ -z "${SMOKE_NO_COMPOSE:-}" ]; then
  step "docker compose up -d --build middleware"
  docker compose up -d --build middleware
fi

# -- 2. health --------------------------------------------------------------
step "waiting for $SERVER/health"
for _ in $(seq 1 60); do
  if health="$(curl -sf "$SERVER/health" 2>/dev/null)"; then break; fi
  sleep 2
done
[ -n "${health:-}" ] || fail "middleware never became healthy at $SERVER"
echo "$health"
echo "$health" | grep -q '"studyId":"pilot-2026"' \
  || fail "protocol not loaded (expected studyId pilot-2026)"

step "platform SPA served at / (NFR-7: one process serves the stack)"
curl -sf "$SERVER/" | grep -qi "<!doctype html" || fail "platform not served at /"

step "requirements of record served (FR-DASH-9 tooltips)"
curl -sf "$SERVER/requirements" | grep -q '"FR-DASH-9"' \
  || fail "/requirements missing FR-DASH-9 (srs.md not shipped or parser broken)"

# -- 3. replay ingest (idempotent demo seed) ---------------------------------
step "replay ingest (middleware/scripts/replay_session.py)"
uv run python middleware/scripts/replay_session.py --server "$SERVER" \
  || fail "replay ingest failed"

# -- 4. dataset export -------------------------------------------------------
step "one-timeline dataset export (JSON + CSV)"
uv run python - "$SERVER" <<'PY' || fail "dataset export check failed"
import json, sys, urllib.request
server = sys.argv[1]
doc = json.loads(urllib.request.urlopen(f"{server}/studies/pilot-2026/dataset", timeout=30).read())
rows = doc["rows"]
assert rows, "dataset has no rows"
missing = [k for k in ("sessionId", "participantId", "condition", "ts") if k not in rows[0]]
assert not missing, f"join keys missing from dataset rows: {missing}"
csv_head = urllib.request.urlopen(f"{server}/studies/pilot-2026/dataset?format=csv", timeout=30).read(200)
assert b"sessionId" in csv_head, "CSV export missing header"
print(f"   {len(rows)} rows, join keys present, CSV header ok")
PY

# -- 5. per-RQ analysis report ------------------------------------------------
step "analysis run -> per-RQ report ($OUT)"
set +e
uv run analysis run protocol/examples/pilot-study.yaml \
  --server "$SERVER" --out "$OUT"
rc=$?
set -e
[ "$rc" -eq 0 ] || [ "$rc" -eq 2 ] || fail "analysis run hard-failed (exit $rc)"

report="$OUT/pilot-2026/report.md"
[ -f "$report" ] || fail "report.md not written"
for rq in RQ-P1 RQ-P2 RQ-P3 RQ-P4 RQ-P5; do
  grep -q "^## $rq" "$report" || fail "report has no section for $rq"
done
# Validation failures are loud by design; only the two event types that
# arrive with's instruments are tolerated here.
if [ "$rc" -eq 2 ]; then
  unexpected="$(grep "MISSING DATA" "$report" \
    | grep -v "'agent_turn'" | grep -v "'task_outcome'" || true)"
  [ -z "$unexpected" ] || fail "unexpected validation failures: $unexpected"
  echo "   exit 2 accepted: only the known requires-failures (agent_turn, task_outcome)"
fi

# -- 6. paper draft (FR-ANA-6) -----------------------------------------
step "analysis paper -> draft.md + draft.tex + references.bib"
uv run analysis paper protocol/examples/pilot-study.yaml \
  --server "$SERVER" --out "$OUT" || fail "analysis paper failed"
paper_dir="$OUT/pilot-2026/paper"
for f in draft.md draft.tex references.bib; do
  [ -f "$paper_dir/$f" ] || fail "paper export missing $f"
done
grep -q '%% trace:' "$paper_dir/draft.tex" || fail "draft.tex has no trace tags"

if command -v tectonic >/dev/null 2>&1; then
  step "compiling draft.tex with tectonic"
  (cd "$paper_dir" && tectonic draft.tex >/dev/null 2>&1) \
    || fail "draft.tex did not compile"
  [ -s "$paper_dir/draft.pdf" ] || fail "draft.pdf empty"
  echo "   draft.pdf compiled"
else
  echo "   (no tectonic on PATH - compile check skipped; structural test covers it)"
fi

printf '\nSMOKE OK  (report: %s, paper: %s)\n' "$report" "$paper_dir"
