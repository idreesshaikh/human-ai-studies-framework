"""
The shared Mistral client layer and the protocol's ``literature:`` seed links.
The design conversation and the corpus match ladder are its only callers - this
module holds no conversational surface of its own.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from typing import Protocol

# The platform intentionally uses one sovereign, EU-based model route.
MISTRAL_MODEL = "mistral-large-latest"
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
    ``matching.rerank_with_llm``).
    """

    model: str

    def run(
        self, question: str, history: list[dict], tools: dict[str, Callable]
    ) -> tuple[str, list[dict]]: ...


class _ChatCompletionsProvider:
    """
    Mistral's chat-completions tool-use loop (D32).
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
        post=_post_json,
        stream=_post_stream,
    ):
        super().__init__(
            "https://api.mistral.ai/v1/chat/completions",
            api_key,
            MISTRAL_MODEL,
            post,
            stream,
        )


def configured() -> bool:
    """
    Whether the EU Mistral model route can be built.
    """
    return bool(os.environ.get("MISTRAL_API_KEY"))


def make_client() -> LLMClient | None:
    """
    Resolve the sole configured Mistral Large client, or ``None`` when no key exists.
    """
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        return None
    return MistralProvider(key)


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
