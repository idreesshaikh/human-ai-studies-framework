"""
The shared Mistral client layer and the protocol's ``literature:`` seed links.
The design conversation and the corpus match ladder are its only callers - this
module holds no conversational surface of its own.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import ClassVar

MISTRAL_MODEL = "mistral-large-latest"
MISTRAL_DESIGN_MODEL = os.environ.get("MISTRAL_DESIGN_MODEL", "mistral-medium-latest")


def _post_json(url: str, body: dict, headers: dict[str, str]) -> dict:
    """
    POST JSON, return parsed JSON. The one network seam - tests inject a scripted
    ``post`` into the providers instead.
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "phoenix/0.1",
            **headers,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as res:
        return json.loads(res.read())


def _post_stream(url: str, body: dict, headers: dict[str, str]):
    """POST JSON, yield content deltas from an SSE chat-completions stream."""
    req = urllib.request.Request(
        url,
        data=json.dumps({**body, "stream": True}).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "phoenix/0.1",
            **headers,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as res:
        for raw in res:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if payload == "[DONE]":
                return
            try:
                frame = json.loads(payload)
                delta = (frame.get("choices") or [{}])[0].get("delta", {})
            except (json.JSONDecodeError, IndexError, AttributeError):
                continue
            piece = delta.get("content")
            if piece:
                yield piece


class MistralProvider:
    """Transport and model settings shared by design and corpus matching."""

    name = "mistral"
    design_options: ClassVar[dict] = {"max_tokens": 4096}

    def __init__(self, api_key: str, post=None, stream=None):
        self.base_url = "https://api.mistral.ai/v1/chat/completions"
        self.api_key = api_key
        self.model = MISTRAL_MODEL
        self.post = post if post is not None else _post_json
        self.stream = stream if stream is not None else _post_stream


class GLMProvider(MistralProvider):
    name = "glm"
    design_options: ClassVar[dict] = {"max_tokens": 16384, "reasoning_effort": "high"}

    def __init__(self, api_key: str, post=None, stream=None):
        super().__init__(api_key, post=post, stream=stream)
        plan = os.environ.get("GLM_PLAN", "go").strip().lower()
        if plan not in {"zen", "go"}:
            raise ValueError("GLM_PLAN must be zen or go")
        route = "zen/go" if plan == "go" else "zen"
        self.base_url = f"https://opencode.ai/{route}/v1/chat/completions"
        self.model = os.environ.get("GLM_MODEL", "glm-5.3-flash")


def configured() -> bool:
    """
    Whether the EU Mistral model route can be built.
    """
    return bool(os.environ.get("MISTRAL_API_KEY"))


def make_client() -> MistralProvider | None:
    """
    Resolve the corpus matching client, or ``None`` when no
    key exists.
    """
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        return None
    return MistralProvider(key)


def make_design_client() -> MistralProvider | None:
    """Return the low-latency client used for short protocol-shaping turns.

    This delegates to ``make_client`` first so tests and local providers keep the same
    injection seam. Only the model name changes for the real Mistral provider.
    """
    provider = os.environ.get("DESIGN_PROVIDER", "auto").strip().lower()
    if provider not in {"auto", "glm", "mistral"}:
        raise ValueError("DESIGN_PROVIDER must be auto, glm or mistral")
    key = os.environ.get("GLM_API_KEY")
    if provider == "glm" or (provider == "auto" and key):
        return GLMProvider(key) if key else None
    client = make_client()
    if client is None:
        return None
    if hasattr(client, "model"):
        client.model = MISTRAL_DESIGN_MODEL
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
