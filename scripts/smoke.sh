#!/usr/bin/env bash
# Exercise a development instance with an isolated synthetic study.
# Run normally to start Docker, or set SMOKE_NO_COMPOSE=1 and SMOKE_SERVER.
set -euo pipefail

SERVER="${SMOKE_SERVER:-http://127.0.0.1:8000}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$(mktemp -d)"
cd "$ROOT"

if [ -z "${SMOKE_NO_COMPOSE:-}" ]; then
  docker compose up -d --build middleware
fi

uv run python - "$SERVER" "$OUT" <<'PY'
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import yaml
from protocol.loader import load_protocol

server, output = sys.argv[1].rstrip("/"), Path(sys.argv[2])
token = os.environ.get("MIDDLEWARE_TOKEN")
headers = {"Authorization": f"Bearer {token}"} if token else {}

def request(path, body=None):
    req = urllib.request.Request(
        server + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={**headers, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()

for attempt in range(60):
    try:
        health = json.loads(request("/health"))
        assert health["status"] == "ok", health
        break
    except (OSError, AssertionError):
        if attempt == 59:
            raise
        time.sleep(1)

assert b"<!doctype html" in request("/").lower(), "built frontend is missing"
print("Server and frontend are available.", flush=True)

protocol = load_protocol(Path("protocol/examples/pilot-study.yaml"))
name = "smoke-" + uuid.uuid4().hex[:10]
project = json.loads(request("/projects", {"name": name}))
study = json.loads(request(
    f"/projects/{project['slug']}/studies",
    {"name": name, "protocol": protocol},
))["id"]
protocol["study"]["id"] = study

outcome = json.loads(request(
    f"/studies/{study}/simulate", {"count": 4, "seed": 42},
))
assert outcome["events"] > 0
assert not outcome["plan"].get("errors"), outcome["plan"]
dataset = json.loads(request(f"/studies/{study}/dataset"))
rows = dataset["rows"]
assert {row["sessionId"] for row in rows} == set(outcome["sessionIds"])
assert all(row["payload"].get("synthetic") is True for row in rows)
print(f"Created {study}: {len(rows)} scoped synthetic rows.", flush=True)

# Replay one stored event, then leave a deliberate gap in its producer stream.
row = next(row for row in rows if row["source"] != "metrics")
event = {key: row[key] for key in (
    "sessionId", "participantId", "condition", "taskId", "ts", "seq", "type", "payload"
)}
event["v"] = row["schemaVersion"]
batch = {"source": row["source"], "events": [event]}
replay = json.loads(request("/ingest/events", batch))
assert replay["inserted"] == 0 and replay["duplicates"] == 1, replay
event["seq"] = max(r["seq"] for r in rows
    if r["sessionId"] == row["sessionId"] and r["source"] == row["source"]) + 2
event["type"] = "editor_focus"
json.loads(request("/ingest/events", batch))
gaps = json.loads(request(f"/sessions/{row['sessionId']}/gaps"))
assert gaps["gaps"], gaps
csv_header = request(f"/studies/{study}/dataset?format=csv").splitlines()[0]
assert b"taskId" in csv_header and b"schemaVersion" in csv_header
print("Replay is idempotent; sequence gaps and CSV join keys are present.", flush=True)

# Analyze the original rehearsal, before the deliberately incomplete event.
protocol_path, dataset_path = output / "protocol.yaml", output / "dataset.json"
protocol_path.write_text(yaml.safe_dump(protocol, sort_keys=False))
dataset_path.write_text(json.dumps(dataset))
for command in ("run", "notebook"):
    subprocess.run([
        sys.executable, "-m", "analysis.cli", command, str(protocol_path),
        "--dataset", str(dataset_path), "--out", str(output),
    ], check=True)

assert (output / study / "report.md").is_file()
assert (output / study / "notebook.ipynb").is_file()
print(f"SMOKE OK: {output / study}")
print(f"Synthetic test study retained on the development server: {study}")
PY
