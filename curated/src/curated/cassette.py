"""A fixture cassette: recorded, sanitized API responses replayed offline
(FR-CUR-2, Slice D).

Mining jobs hit a rate-limited external API; CI and the demo must not. A
cassette is a committed JSON file mapping a *request shape* (method + path +
sorted query) to a recorded response. Responses are sanitized at record time
(pseudonymized logins, stripped message bodies) so nothing raw is ever
committed. The cassette is deterministic: the same request shape always
returns the same response, so a mining run over a cassette is reproducible.

The cassette also carries scripted **fault** entries so tests can exercise
the rate-limit pause (403/429) and mid-job interruption without a live API:
a request shape can be marked to return a rate-limit response, optionally
only on the first N calls.

Format (``cassettes/*.json``)::

    {
      "meta": {"recordedAt": "...", "sanitized": true, "source": "github"},
      "entries": [
        {"key": "GET /search/issues?q=...", "status": 200, "body": {...}},
        {"key": "GET /rate/limited", "status": 429,
         "rateLimited": true, "onlyFirst": 1,
         "headers": {"retry-after": "1"}}
      ]
    }
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode


class RateLimited(Exception):
    """Raised by the cassette when a request hits a scripted rate-limit
    entry. Carries the retry-after seconds so the runner can back off."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"rate limited; retry after {retry_after}s")
        self.retry_after = retry_after


class CassetteMiss(KeyError):
    """A request shape not present in the cassette (a recording gap)."""


def request_key(method: str, path: str, params: dict | None = None) -> str:
    """The canonical request shape used as a cassette key: method + path +
    query sorted so ordering never causes a miss."""
    query = ""
    if params:
        query = "?" + urlencode(sorted((k, str(v)) for k, v in params.items()))
    return f"{method.upper()} {path}{query}"


@dataclass
class _Entry:
    status: int
    body: object
    rate_limited: bool
    only_first: int  # 0 = always; N = only the first N calls
    retry_after: float


class Cassette:
    """Replays recorded responses by request shape. Counts calls per key so
    ``onlyFirst`` faults (rate-limit on the first attempt, success on retry)
    can be scripted for the resume/backoff tests."""

    def __init__(self, entries: dict[str, _Entry]) -> None:
        self._entries = entries
        self._calls: dict[str, int] = defaultdict(int)

    @classmethod
    def load(cls, path: str | Path) -> Cassette:
        doc = json.loads(Path(path).read_text("utf-8"))
        entries: dict[str, _Entry] = {}
        for e in doc.get("entries", []):
            entries[e["key"]] = _Entry(
                status=int(e.get("status", 200)),
                body=e.get("body"),
                rate_limited=bool(e.get("rateLimited", False)),
                only_first=int(e.get("onlyFirst", 0)),
                retry_after=float(e.get("headers", {}).get("retry-after", 1)),
            )
        return cls(entries)

    def get(self, method: str, path: str, params: dict | None = None) -> object:
        key = request_key(method, path, params)
        entry = self._entries.get(key)
        if entry is None:
            raise CassetteMiss(key)
        self._calls[key] += 1
        n = self._calls[key]
        if entry.rate_limited and (entry.only_first == 0 or n <= entry.only_first):
            raise RateLimited(entry.retry_after)
        return entry.body

    def call_count(self, method: str, path: str, params: dict | None = None) -> int:
        return self._calls[request_key(method, path, params)]
