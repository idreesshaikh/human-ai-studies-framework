"""
The shared LLM client layer: provider setup, model tiers, and the protocol's
``literature:`` seed links. The design conversation and the corpus match ladder
are its only callers  -  this module holds no conversational surface of its own.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from collections.abc import Callable
from typing import Protocol

log = logging.getLogger(__name__)

MISTRAL_MODEL = "mistral-medium-latest"
MISTRAL_BEST_MODEL = "mistral-large-latest"
MISTRAL_MODELS = (
    "mistral-small-latest",
    "mistral-medium-latest",
    "mistral-large-latest",
)
DEFAULT_OPENAI_COMPATIBLE_MODEL = "gpt-4o-mini"
OPENCODE_BASE_URL = "https://opencode.ai/zen/go/v1/chat/completions"
# DeepSeek V4 Flash is the OpenCode Go default for this app: it uses the
# Chat Completions endpoint already implemented here and has a much larger
# request allowance than Kimi K3. Override with OPENCODE_MODEL when needed.
OPENCODE_MODEL = "deepseek-v4-flash"
MAX_TOKENS = 2048
MAX_TOOL_ROUNDS = 6

SYSTEM_PROMPT = (
    "You are the knowledge assistant for a human-AI developer study. Answer "
    "questions using ONLY the three tools provided: search_papers (the "
    "study's ingested papers), get_protocol (the study-as-code protocol), "
    "and get_dataset_summary (aggregate statistics only - never individual "
    "participants). You have no other source of truth about this study.\n\n"
    "Cite every factual claim with a source tag inline: [<paper-ref> §<chunk>] "
    "for a paper, [protocol:<field>] for the protocol, or [dataset-summary] "
    "for an aggregate. If you cannot support a claim from a tool result, say "
    "so plainly rather than guessing. You will never be given, and must never "
    "ask for, row-level participant data - only aggregates exist."
)

TOOL_SCHEMAS = [
    {
        "name": "search_papers",
        "description": (
            "Full-text search over the study's ingested papers. Returns "
            "matching text chunks with their [paper-ref §chunk] tags to cite."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "search terms"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_protocol",
        "description": (
            "The study's protocol (study-as-code): research questions, "
            "conditions, instruments, analysis plan, and literature links."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_dataset_summary",
        "description": (
            "Aggregate statistics for the study's collected data: per-condition "
            "session/event counts, event-type totals, and metric "
            "means/medians. Aggregates only - never individual participants."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


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
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


def _post_stream(url: str, body: dict, headers: dict[str, str]):
    """POST JSON, yield content deltas from an SSE chat-completions stream."""
    req = urllib.request.Request(
        url,
        data=json.dumps({**body, "stream": True}).encode(),
        headers={"Content-Type": "application/json", "Accept": "text/event-stream",
                 **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as res:
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


class LLMClient(Protocol):
    """
    The shape every LLM-consuming feature in this module calls against (the knowledge
    assistant, the design conversation's ``design_llm.py``, and
    ``matching.rerank_with_llm``) - formalized now that a second provider
    (``OpenAICompatibleProvider``) is real, not just a duck-typed convention.
    """

    model: str

    def run(
        self, question: str, history: list[dict], tools: dict[str, Callable]
    ) -> tuple[str, list[dict]]: ...


class _ChatCompletionsProvider:
    """
    A tool-use loop over any host that speaks the OpenAI chat-completions shape -
    Mistral's REST API already speaks this exact shape (D32), so an OpenAI-compatible
    override is the same loop pointed at a different ``base_url``/``model``, not a
    second implementation.
    """

    name = "chat-completions"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        post=_post_json,
        stream=_post_stream,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.post = post
        self.stream = stream

    @staticmethod
    def _tool_config() -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in TOOL_SCHEMAS
        ]

    def run(
        self, question: str, history: list[dict], tools: dict[str, Callable]
    ) -> tuple[str, list[dict]]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            *history,
            {"role": "user", "content": question},
        ]
        tool_calls: list[dict] = []
        for _ in range(MAX_TOOL_ROUNDS):
            res = self.post(
                self.base_url,
                {
                    "model": self.model,
                    "messages": messages,
                    "tools": self._tool_config(),
                    "max_tokens": MAX_TOKENS,
                },
                {"Authorization": f"Bearer {self.api_key}"},
            )
            msg = (res.get("choices") or [{}])[0].get("message", {})
            messages.append(msg)
            calls = msg.get("tool_calls") or []
            if not calls:
                return str(msg.get("content") or ""), tool_calls
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                impl = tools.get(name)
                output = impl(args) if impl else f"Unknown tool {name}"
                tool_calls.append({"tool": name, "input": args})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "name": name,
                        "content": output,
                    }
                )
        return "", tool_calls


class MistralProvider(_ChatCompletionsProvider):
    """Mistral chat-completions tool-use loop over the REST API (D32)."""

    name = "mistral"

    def __init__(
        self,
        api_key: str,
        model: str = MISTRAL_MODEL,
        post=_post_json,
        stream=_post_stream,
    ):
        super().__init__(
            "https://api.mistral.ai/v1/chat/completions", api_key, model, post, stream
        )


class OpenAICompatibleProvider(_ChatCompletionsProvider):
    """
    Any OpenAI-compatible host (OpenAI itself, or a compatible gateway in front of
    another model), configured entirely via env vars
    (``LLM_BASE_URL``/``LLM_API_KEY``/``LLM_MODEL``) - drop in a better model's API key
    and it works immediately, no code change (FR-CONV-1.4).
    """

    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        post=_post_json,
        stream=_post_stream,
    ):
        root = base_url.rstrip("/")
        endpoint = (
            root if root.endswith("/chat/completions") else f"{root}/chat/completions"
        )
        super().__init__(endpoint, api_key, model, post, stream)


class FailoverProvider:
    """Keep a compatible primary model from making the conversation unavailable.

    OpenCode can reject a request at the edge even while its catalogue endpoint is
    reachable. When a configured Mistral key exists, retry the same request against
    Mistral with its own endpoint and model. The wrapper preserves the small provider
    surface used by both the design conversation and the knowledge assistant.
    """

    name = "failover"

    def __init__(
        self, primary: _ChatCompletionsProvider, fallback: _ChatCompletionsProvider
    ):
        self.primary = primary
        self.fallback = fallback
        self.model = primary.model
        self.base_url = primary.base_url
        self.api_key = primary.api_key

    @staticmethod
    def _payload(provider: _ChatCompletionsProvider, payload: dict) -> dict:
        body = dict(payload)
        body["model"] = provider.model
        return body

    def _fallback_reason(self, exc: Exception) -> None:
        log.warning(
            "primary model unavailable (%s); retrying with %s",
            type(exc).__name__,
            self.fallback.model,
        )

    def post(self, url: str, payload: dict, headers: dict[str, str]) -> dict:
        try:
            return self.primary.post(url, payload, headers)
        except Exception as exc:  # noqa: BLE001 - provider failure is the fallback seam
            self._fallback_reason(exc)
            return self.fallback.post(
                self.fallback.base_url,
                self._payload(self.fallback, payload),
                {"Authorization": f"Bearer {self.fallback.api_key}"},
            )

    def stream(self, url: str, payload: dict, headers: dict[str, str]):
        try:
            yield from self.primary.stream(url, payload, headers)
        except Exception as exc:  # noqa: BLE001 - provider failure is the fallback seam
            self._fallback_reason(exc)
            yield from self.fallback.stream(
                self.fallback.base_url,
                self._payload(self.fallback, payload),
                {"Authorization": f"Bearer {self.fallback.api_key}"},
            )

    def run(
        self, question: str, history: list[dict], tools: dict[str, Callable]
    ) -> tuple[str, list[dict]]:
        try:
            return self.primary.run(question, history, tools)
        except Exception as exc:  # noqa: BLE001 - provider failure is the fallback seam
            self._fallback_reason(exc)
            return self.fallback.run(question, history, tools)


def configured() -> bool:
    """
    Whether an LLM client can be built - an explicit compatible gateway, OpenCode, or
    the Mistral fallback (D32 rev 2).
    """
    if os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_API_KEY"):
        return True
    if os.environ.get("OPENCODE_API_KEY"):
        return True
    return bool(os.environ.get("MISTRAL_API_KEY"))


def make_client(model: str | None = None) -> LLMClient | None:
    """
    Resolve the configured LLM client, or ``None`` when nothing is configured (callers
    then degrade gracefully - never raises).
    """
    base_url = os.environ.get("LLM_BASE_URL")
    override_key = os.environ.get("LLM_API_KEY")
    if base_url and override_key:
        override_model = os.environ.get("LLM_MODEL") or DEFAULT_OPENAI_COMPATIBLE_MODEL
        return OpenAICompatibleProvider(base_url, override_key, override_model)
    opencode_key = os.environ.get("OPENCODE_API_KEY")
    if opencode_key:
        primary = OpenAICompatibleProvider(
            os.environ.get("OPENCODE_BASE_URL", OPENCODE_BASE_URL),
            opencode_key,
            os.environ.get("OPENCODE_MODEL", OPENCODE_MODEL),
        )
        mistral_key = os.environ.get("MISTRAL_API_KEY")
        if mistral_key:
            fallback_model = (
                model if model in MISTRAL_MODELS else MISTRAL_BEST_MODEL
            )
            return FailoverProvider(
                primary,
                MistralProvider(mistral_key, model=fallback_model),
            )
        return primary
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        return None
    chosen = model if model in MISTRAL_MODELS else MISTRAL_MODEL
    return MistralProvider(key, model=chosen)


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
