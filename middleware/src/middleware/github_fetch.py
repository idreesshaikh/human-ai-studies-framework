"""A live GitHub fetcher for the curated-mining leg (FR-CUR-2).

Stdlib only (``urllib``), consistent with the Semantic Scholar client's
zero-bloat posture (D8): no ``requests``/``httpx`` dependency for a couple of
GET shapes. Token-scoped; honors the GitHub rate-limit headers by raising
:class:`~curated.cassette.RateLimited` so the job runner pauses and backs off
rather than crashing (F2.3). Degrades to a clear error when no token is set -
the offline path is the cassette (:mod:`curated.cassette`), which is what CI
and the demo use.

This module is intentionally thin: the mining *logic* lives in the adapter;
this only turns an adapter request into an HTTPS call and maps GitHub's
rate-limit signalling onto the runner's pause contract.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from curated.cassette import RateLimited

_API_ROOT = "https://api.github.com"


class LiveGitHubFetcher:
    """Satisfies the adapter's ``Fetcher`` protocol against the real API."""

    def __init__(self, token: str | None) -> None:
        self._token = token

    def get(self, method: str, path: str, params: dict | None = None) -> object:
        if not self._token:
            # No token → the live source is unreachable. The caller should
            # have a cassette configured for offline runs; say so plainly.
            raise RuntimeError(
                "no GitHub token configured (MIDDLEWARE_GITHUB_TOKEN); "
                "set one to mine live, or configure a cassette "
                "(MIDDLEWARE_MINING_CASSETTE) to run offline."
            )
        if method.upper() != "GET":
            raise ValueError(f"unsupported method {method!r}")
        url = _API_ROOT + path
        if params:
            url += "?" + urllib.parse.urlencode(sorted(params.items()))
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Accept", "application/vnd.github+json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                # Primary/secondary rate limit. Prefer Retry-After, else the
                # reset window; fall back to a short pause.
                retry_after = exc.headers.get("Retry-After")
                if retry_after is not None:
                    raise RateLimited(float(retry_after)) from exc
                reset = exc.headers.get("X-RateLimit-Reset")
                if reset is not None:
                    wait = max(1.0, float(reset) - time.time())
                    raise RateLimited(wait) from exc
                raise RateLimited(60.0) from exc
            raise
