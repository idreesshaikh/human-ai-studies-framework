"""
Chat-completions client layer. Provider, endpoint, model, key, timeouts and retries
come from the environment only (see ``.env.example``); nothing here names a vendor
except the legacy ``MISTRAL_*`` aliases and the default endpoint.

Resolution order, per setting: ``LLM_*`` > legacy ``MISTRAL_*`` > built-in default.
Design turns use ``LLM_DESIGN_MODEL`` (alias ``MISTRAL_DESIGN_MODEL``) when set.
The design conversation and the corpus match ladder are the only callers; this module
holds no conversational surface of its own.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.mistral.ai/v1/chat/completions"
DEFAULT_MODEL = "ministral-14b-latest"
# Legacy names other modules and tests import.
MISTRAL_MODEL = DEFAULT_MODEL
MISTRAL_DESIGN_MODEL = DEFAULT_MODEL

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_RETRYABLE = {429, 500, 502, 503, 504}
_MAX_RETRY_AFTER_S = 30.0
_sleep = time.sleep  # tests replace this so retries do not wait


def _env(*names: str) -> str:
    """First non-blank value among the named variables ('' when none is set)."""
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _number_env(name: str, default: float, low: float, high: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        value = float(raw) if raw else default
        if not math.isfinite(value):
            raise ValueError
    except ValueError:
        log.warning("%s is not a finite number; using %s", name, default)
        return default
    return min(max(value, low), high)


def model_name(*, design: bool = False) -> str:
    """Design override > shared override > default; blank settings are unset."""
    shared = _env("LLM_MODEL", "MISTRAL_MODEL") or DEFAULT_MODEL
    if design:
        return _env("LLM_DESIGN_MODEL", "MISTRAL_DESIGN_MODEL") or shared
    return shared


def normalise_chat_url(url: str) -> str:
    """Accept either a full chat-completions URL or an API base such as ``.../v1``."""
    url = url.strip().rstrip("/")
    return url if url.endswith("/chat/completions") else url + "/chat/completions"


def _is_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in _LOCAL_HOSTS


def _resolve() -> tuple[str, str] | None:
    """(api_key, chat URL), or None when the model route is not usable."""
    url = normalise_chat_url(_env("LLM_BASE_URL") or DEFAULT_BASE_URL)
    try:
        parsed = urlparse(url)
        valid = (
            parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not any(
                (parsed.username, parsed.password, parsed.query, parsed.fragment)
            )
        )
        _ = parsed.port  # Validate the port as well as the host.
    except ValueError:
        valid = False
    if not valid:
        log.error("LLM_BASE_URL is not a valid http(s) URL; model route disabled")
        return None
    if parsed.scheme == "http" and not _is_local(url) and _env("LLM_ALLOW_HTTP") != "1":
        log.error(
            "LLM_BASE_URL uses plain http to a remote host; model route disabled "
            "(set LLM_ALLOW_HTTP=1 to override)"
        )
        return None
    key = _env("LLM_API_KEY", "MISTRAL_API_KEY")
    if not key and not _is_local(url):
        return None
    return key, url


def _retry_delay(exc: urllib.error.HTTPError | None, attempt: int) -> float:
    retry_after = None
    if exc is not None and exc.headers is not None:
        retry_after = exc.headers.get("Retry-After")
    if retry_after:
        try:
            value = float(retry_after)
            if math.isfinite(value):
                return min(max(value, 0.0), _MAX_RETRY_AFTER_S)
        except ValueError:
            pass
    return min(0.5 * 2**attempt, 8.0)


def _can_retry(exc: Exception, attempt: int, retries: int) -> bool:
    return attempt < retries and (
        not isinstance(exc, urllib.error.HTTPError) or exc.code in _RETRYABLE
    )


def _wait_to_retry(exc: Exception, attempt: int) -> None:
    delay = _retry_delay(
        exc if isinstance(exc, urllib.error.HTTPError) else None, attempt
    )
    log.warning("model request failed; retrying in %.1fs", delay)
    _sleep(delay)


def _open(req: urllib.request.Request, timeout: float, *, retries: int | None = None):
    """urlopen with bounded retries on 429/5xx and connection errors."""
    if retries is None:
        retries = int(_number_env("LLM_MAX_RETRIES", 2, 0, 5))
    for attempt in range(retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if not _can_retry(exc, attempt, retries):
                raise
            _wait_to_retry(exc, attempt)
    raise AssertionError("unreachable")  # pragma: no cover


def _post_json(url: str, body: dict, headers: dict[str, str]) -> dict:
    """
    POST JSON, return parsed JSON. The one network seam - tests inject a scripted
    ``post`` into the providers instead.
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with _open(req, _number_env("LLM_TIMEOUT_S", 60, 1, 600)) as res:
        return json.loads(res.read())


def _post_stream(url: str, body: dict, headers: dict[str, str]):
    """POST JSON, yield content deltas from an SSE chat-completions stream."""
    req = urllib.request.Request(
        url,
        data=json.dumps({**body, "stream": True}).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            **headers,
        },
        method="POST",
    )
    timeout = _number_env("LLM_STREAM_TIMEOUT_S", 120, 1, 1800)
    retries = int(_number_env("LLM_MAX_RETRIES", 2, 0, 5))
    for attempt in range(retries + 1):
        started = False
        try:
            with _open(req, timeout, retries=0) as res:
                for raw in res:
                    started = True
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:") :].strip()
                    if payload == "[DONE]":
                        return
                    try:
                        frame = json.loads(payload)
                        delta = (frame.get("choices") or [{}])[0].get("delta", {})
                        piece = delta.get("content")
                    except (json.JSONDecodeError, IndexError, AttributeError):
                        continue
                    if piece:
                        yield piece
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if started or not _can_retry(exc, attempt, retries):
                raise
            _wait_to_retry(exc, attempt)


class ChatProvider:
    """Transport and model settings shared by every model-backed route."""

    name = "chat-completions"

    def __init__(self, api_key: str, post=None, stream=None, *, base_url=None):
        self.base_url = base_url or normalise_chat_url(
            _env("LLM_BASE_URL") or DEFAULT_BASE_URL
        )
        self.api_key = api_key
        self.model = model_name()
        self.post = post if post is not None else _post_json
        self.stream = stream if stream is not None else _post_stream

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}


MistralProvider = ChatProvider  # legacy name, still constructed by tests and scripts


def client_headers(client) -> dict[str, str]:
    """Keep providers injected through the original api_key seam working."""
    headers = getattr(client, "headers", None)
    if headers is not None:
        return headers
    key = getattr(client, "api_key", "")
    return {"Authorization": f"Bearer {key}"} if key else {}


def configured() -> bool:
    """Whether a model route can be built from the current environment."""
    return _resolve() is not None


def make_client() -> ChatProvider | None:
    """The corpus-matching client, or ``None`` when no usable route exists."""
    resolved = _resolve()
    if resolved is None:
        return None
    key, url = resolved
    return ChatProvider(key, base_url=url)


def make_design_client() -> ChatProvider | None:
    """The client for short protocol-shaping turns; only the model name differs.

    Delegates to ``make_client`` so tests and local providers keep the same injection
    seam.
    """
    client = make_client()
    if client is None:
        return None
    if hasattr(client, "model"):
        client.model = model_name(design=True)
    return client


def protocol_literature_targets(protocol: dict | None) -> dict[str, list[str]]:
    """
    Seed links from the protocol's ``literature:`` list (FR-LIT-3): ``{paperRef:
    [justifies...]}`` so ingested papers carry their protocol links by construction.
    """
    out: dict[str, list[str]] = {}
    for entry in (protocol or {}).get("literature", []):
        ref = entry.get("paperRef")
        if ref:
            out[ref] = list(entry.get("justifies", []))
    return out
