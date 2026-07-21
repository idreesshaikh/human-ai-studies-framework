"""Replay the bundled sample sessions against a running middleware.

Smoke-test and demo seed in one command (stdlib only - runs anywhere
Python runs):

    uv run python middleware/scripts/replay_session.py

Posts the sample overlay session (which contains a deliberate seq gap) in
the extension's HttpSink wire format, posts the behavioral demo session
(cognitive + behavioral legs on one timeline), posts the sample
metrics rows, replays the first event batch a second time to prove
idempotency (FR-ING-2), uploads the design-phase gate artifacts so the
lifecycle computes to its ethics gate (FR-DASH-2 demo state, NFR-9), then
prints the gap report (FR-ING-3) and the one-timeline dataset summary
(FR-ING-4).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample-data"

#: Platform-facing endpoints (lifecycle/gaps/dataset) are auth-gated
#: whenever MIDDLEWARE_AUTH requires it (unlike /ingest/*, which NFR-1
#: keeps unauthenticated in every mode). In `token` mode this script can
#: authenticate itself with the same shared secret; in `clerk` mode there
#: is no static service credential, so those calls degrade gracefully
#: instead of crashing the seed run (F1: seed failures never kill the
#: server, and now never spuriously fail the report either).
_AUTH_HEADERS = (
    {"Authorization": f"Bearer {os.environ['MIDDLEWARE_TOKEN']}"}
    if os.environ.get("MIDDLEWARE_TOKEN")
    else {}
)

#: Design-phase gate artifacts (see protocol/examples/pilot-study.yaml).
#: Seeding these leaves the demo blocked at the *ethics* gate - the
#: platform acceptance walk uploads the ethics artifacts via the UI.
DESIGN_ARTIFACTS = {
    "protocol-validated.txt": (
        b"pilot-2026 validated by `protocol validate` (demo artifact)\n"
    ),
    "task-definitions.md": (
        b"# Task definitions\n\nTwo matched Python maintenance tasks "
        b"(demo artifact).\n"
    ),
}


def _call(method: str, url: str, body: object | None = None) -> dict | list:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"content-type": "application/json", **_AUTH_HEADERS}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _upload(server: str, filename: str, content: bytes) -> dict:
    """multipart/form-data upload with stdlib only."""
    boundary = uuid.uuid4().hex
    body = (
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = urllib.request.Request(
        f"{server}/ingest/files",
        data=body,
        method="POST",
        headers={
            "content-type": f"multipart/form-data; boundary={boundary}",
            **_AUTH_HEADERS,
        },
    )
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--events", type=Path, default=SAMPLE_DIR / "sample-session.jsonl"
    )
    parser.add_argument(
        "--events2",
        type=Path,
        default=SAMPLE_DIR / "sample-session-2.jsonl",
        help="behavioral demo session",
    )
    parser.add_argument(
        "--events3",
        type=Path,
        default=SAMPLE_DIR / "sample-session-3.jsonl",
        help="unassisted demo session, so both conditions "
        "render (P02's counterbalanced pair)",
    )
    parser.add_argument(
        "--metrics", type=Path, default=SAMPLE_DIR / "sample-metrics.jsonl"
    )
    args = parser.parse_args()

    try:
        health = _call("GET", f"{args.server}/health")
    except (urllib.error.URLError, OSError) as exc:
        print(
            f"error: middleware not reachable at {args.server}: {exc}", file=sys.stderr
        )
        return 1
    study_id = health.get("studyId") or "adhoc"
    print(f"middleware ok - study {study_id!r}")

    events = _read_jsonl(args.events)
    session_id = events[0]["sessionId"]
    wire = {"source": "cognitive-overlay", "events": events}
    first = _call("POST", f"{args.server}/ingest/events", wire)
    replay = _call("POST", f"{args.server}/ingest/events", wire)
    print(
        f"events: {first['inserted']} inserted, then replayed -> "
        f"{replay['duplicates']} duplicates, {replay['inserted']} inserted "
        "(idempotent)"
    )

    if args.events2.exists():
        behavior = _read_jsonl(args.events2)
        wire2 = {"source": "cognitive-overlay", "events": behavior}
        b = _call("POST", f"{args.server}/ingest/events", wire2)
        types = len({e["type"] for e in behavior})
        print(
            f"behavioral session {behavior[0]['sessionId']}: "
            f"{b['inserted']} inserted ({types} event types, 2 legs)"
        )

    if args.events3.exists():
        unassisted = _read_jsonl(args.events3)
        wire3 = {"source": "cognitive-overlay", "events": unassisted}
        u = _call("POST", f"{args.server}/ingest/events", wire3)
        print(
            f"unassisted session {unassisted[0]['sessionId']}: "
            f"{u['inserted']} inserted (both conditions now render)"
        )

    rows = _read_jsonl(args.metrics)
    m = _call("POST", f"{args.server}/ingest/metrics", rows)
    print(f"metrics: {m['inserted']} inserted, {m['duplicates']} duplicates")

    for filename, content in DESIGN_ARTIFACTS.items():
        res = _upload(args.server, filename, content)
        dup = " (already present)" if res.get("duplicate") else ""
        print(f"artifact: {filename} uploaded{dup}")
    try:
        lifecycle = _call("GET", f"{args.server}/studies/{study_id}/lifecycle")
        print(
            f"lifecycle: current phase {lifecycle['currentPhase']!r} "
            "(computed from artifacts)"
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            print("lifecycle: skipped (401 - no service credential for this auth mode)")
        else:
            pass  # no protocol loaded - lifecycle endpoints are protocol-scoped

    try:
        gaps = _call("GET", f"{args.server}/sessions/{session_id}/gaps")
        print(
            f"\ngap report for {session_id}: received {gaps['received']}/"
            f"{gaps['expected']} (seq {gaps['firstSeq']}..{gaps['lastSeq']})"
        )
        for g in gaps["gaps"]:
            print(
                f"  missing {g['missing']} event(s) between seq "
                f"{g['afterSeq']} and {g['beforeSeq']}"
            )
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise
        print(f"\ngap report for {session_id}: skipped (401 - no service credential)")

    try:
        dataset = _call("GET", f"{args.server}/studies/{study_id}/dataset")
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            raise
        print("\ndataset summary: skipped (401 - no service credential for this auth "
              "mode; data was still ingested - MIDDLEWARE_AUTH never gates /ingest/*)")
        return 0
    rows = dataset["rows"]
    by_source: dict[str, int] = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    print(
        f"\ndataset: {len(rows)} rows on one timeline "
        f"({', '.join(f'{k}: {v}' for k, v in sorted(by_source.items()))})"
    )
    print(f"  first: {rows[0]['ts']}  {rows[0]['source']}/{rows[0]['type']}")
    print(f"  last:  {rows[-1]['ts']}  {rows[-1]['source']}/{rows[-1]['type']}")
    print(f"  csv:   {args.server}/studies/{study_id}/dataset?format=csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
