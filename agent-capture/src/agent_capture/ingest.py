"""Fire-and-forget POST to the ingestion middleware (NFR-1/2)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "http://localhost:8000/ingest/events"
DEFAULT_TIMEOUT_S = 3.0


def post_events(
    events: list[dict],
    *,
    source: str,
    endpoint: str = DEFAULT_ENDPOINT,
    timeout: float = DEFAULT_TIMEOUT_S,
) -> dict:
    """POST a ``{source, events}`` batch."""
    if not events:
        return {"posted": 0, "error": None}
    body = json.dumps({"source": source, "events": events}).encode()
    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            summary = json.loads(res.read())
        summary["posted"] = len(events)
        return summary
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return {"posted": 0, "error": str(exc)}
