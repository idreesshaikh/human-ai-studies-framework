"""
Knowledge assistant - grounded Q&A over papers + protocol + dataset *aggregates*
(FR-LIT-4), powered by Mistral with tool use (D32 rev 2, superseding D10/D22).
"""

from __future__ import annotations

import json
import os
import statistics
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from middleware import paper_index
from middleware.db import Event, MetricRow, Paper

MISTRAL_MODEL = "mistral-medium-latest"
MISTRAL_BEST_MODEL = "mistral-large-latest"
MISTRAL_MODELS = (
    "mistral-small-latest",
    "mistral-medium-latest",
    "mistral-large-latest",
)
DEFAULT_OPENAI_COMPATIBLE_MODEL = "gpt-4o-mini"
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


def search_papers_tool(s: Session, query: str, study_id: str | None = None) -> str:
    """Passages from the papers THIS study holds."""
    hits = paper_index.search(s, query)
    if study_id is not None:
        held = {
            ref
            for (ref,) in s.execute(
                select(Paper.paper_ref).where(Paper.study_id == study_id)
            )
        }
        hits = [h for h in hits if h["paperRef"] in held]
    if not hits:
        return "No matching passages in this study's papers."
    return "\n\n".join(
        f"[{h['paperRef']} §{h['chunkIdx']}] {h['snippet']}" for h in hits
    )


def get_protocol_tool(protocol: dict | None) -> str:
    if not protocol:
        return "No protocol is loaded for this deployment."
    view = {
        "studyId": protocol.get("study", {}).get("id"),
        "title": protocol.get("study", {}).get("title"),
        "conditions": protocol.get("conditions"),
        "researchQuestions": protocol.get("researchQuestions"),
        "instruments": protocol.get("instruments"),
        "analysisPlan": protocol.get("analysisPlan"),
        "literature": protocol.get("literature"),
    }
    return json.dumps(view, indent=2, default=str)


def dataset_summary(s: Session) -> dict:
    """Per-condition counts + metric means/medians."""
    conditions: dict[str, dict] = defaultdict(
        lambda: {"sessions": set(), "events": 0, "eventTypes": defaultdict(int)}
    )
    for cond, sid, type_, n in s.execute(
        select(Event.condition, Event.session_id, Event.type, func.count()).group_by(
            Event.condition, Event.session_id, Event.type
        )
    ):
        c = conditions[cond or "(unknown)"]
        c["sessions"].add(sid)
        c["events"] += n
        c["eventTypes"][type_] += n

    values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for cond, row in s.execute(select(MetricRow.condition, MetricRow.row)):
        for key, val in (row or {}).items():
            if key in ("participantId", "sessionId", "timestamp", "condition"):
                continue
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                values[cond or "(unknown)"][key].append(float(val))

    metrics: dict[str, dict] = {}
    for cond, cols in values.items():
        metrics[cond] = {
            key: {
                "n": len(vals),
                "mean": round(statistics.fmean(vals), 4),
                "median": round(statistics.median(vals), 4),
            }
            for key, vals in cols.items()
        }

    return {
        "conditions": {
            cond: {
                "sessions": len(c["sessions"]),
                "events": c["events"],
                "eventTypes": dict(c["eventTypes"]),
            }
            for cond, c in conditions.items()
        },
        "metrics": metrics,
    }


def get_dataset_summary_tool(s: Session) -> str:
    return json.dumps(dataset_summary(s), indent=2)


def build_tools(
    s: Session, protocol: dict | None, study_id: str | None = None
) -> dict[str, Callable[[dict], str]]:
    """The tool name → implementation map."""
    return {
        "search_papers": lambda i: search_papers_tool(
            s, str(i.get("query", "")), study_id
        ),
        "get_protocol": lambda i: get_protocol_tool(protocol),
        "get_dataset_summary": lambda i: get_dataset_summary_tool(s),
    }


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


def configured() -> bool:
    """
    Whether an LLM client can be built - the OpenAI-compatible override or a Mistral key
    (D32 rev 2).
    """
    if os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_API_KEY"):
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
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        return None
    chosen = model if model in MISTRAL_MODELS else MISTRAL_MODEL
    return MistralProvider(key, model=chosen)


def _extract_citations(text: str) -> list[str]:
    """
    Pull the ``[...]`` source tags the system prompt requires, in order, de-duplicated -
    the platform renders them as clickable chips.
    """
    import re

    seen: dict[str, None] = {}
    for m in re.findall(r"\[([^\[\]]+)\]", text):
        seen.setdefault(m.strip(), None)
    return list(seen)


def answer_question(
    question: str,
    history: list[dict],
    *,
    tools: dict[str, Callable[[dict], str]],
    client,
) -> dict:
    """Run the grounded tool-use loop and return ``{answer, citations, toolCalls}``."""
    answer, tool_calls = client.run(question, history, tools)
    return {
        "answer": answer,
        "citations": _extract_citations(answer),
        "toolCalls": tool_calls,
    }


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
