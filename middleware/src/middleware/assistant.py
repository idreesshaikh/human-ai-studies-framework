"""Knowledge assistant - grounded Q&A over papers + protocol + dataset
*aggregates* (FR-LIT-4), powered by Mistral with tool use (D32 rev 2,
superseding D10/D22).

**FR-ETH-4 is enforced here, in code, not in the prompt.** The model is
given exactly three tools, and none can return a row-level participant
event:

- ``search_papers(query)`` → chunked full-text search over ingested papers
  (paper text only),
- ``get_protocol()`` → the study protocol (public study-as-code), and
- ``get_dataset_summary()`` → per-condition counts, event-type totals, and
  metric means/medians — **aggregates only**, computed server-side.

The model cannot leak what it cannot see: there is no tool that returns a
``participantId``, a ``sessionId``, a ``seq``, or a raw event payload. The
grep-the-output test asserts exactly this.

The system prompt requires a source tag on every claim (``[paper-ref
§chunk]``, ``[protocol:field]``, or ``[dataset-summary]``); an answer with
no source must say so. Without ``MISTRAL_API_KEY`` the endpoint degrades
gracefully — every other feature works offline. The platform picks the
*model tier* per question (``MISTRAL_MODELS``); requests never carry keys.

Mistral is called over plain REST via stdlib ``urllib`` (D32: no vendor
SDK - same zero-bloat call shape as the Semantic Scholar client), with a
hand-rolled tool-use loop, because the tool boundary is the whole point.

``make_client()`` is the one provider-resolution seam every LLM-consuming
feature in this codebase calls through (this module, ``design_llm.py``,
``matching.rerank_with_llm``): set ``LLM_BASE_URL``/``LLM_API_KEY``
(+ optional ``LLM_MODEL``) to point everything at any OpenAI-compatible
host instead, with no code change (FR-CONV-1.4).
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
from middleware.db import Event, MetricRow

MISTRAL_MODEL = "mistral-small-latest"
#: The design conversation's own default (FR-CONV-1.4) — the best Mistral
#: tier, distinct from the knowledge assistant's own per-question tier
#: picker above, which keeps its existing default unchanged.
MISTRAL_BEST_MODEL = "mistral-large-latest"
#: Model tiers the platform may select per question (validated server-side).
MISTRAL_MODELS = (
    "mistral-small-latest",
    "mistral-medium-latest",
    "mistral-large-latest",
)
#: A generic OpenAI-compatible override (FR-CONV-1.4): set LLM_BASE_URL +
#: LLM_API_KEY (+ optionally LLM_MODEL) to point every LLM-consuming
#: feature in this module at any host that speaks the OpenAI
#: chat-completions shape - OpenAI itself, or a compatible gateway in
#: front of another model - with no code change. Takes priority over
#: MISTRAL_API_KEY when both are set.
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


# --------------------------------------------------------------- tool impls


def search_papers_tool(s: Session, query: str) -> str:
    hits = paper_index.search(s, query)
    if not hits:
        return "No matching passages in the ingested papers."
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
    """Per-condition counts + metric means/medians. **Aggregates only** -
    this function is the FR-ETH-4 boundary; it must never emit a
    participantId, a sessionId, a seq, or a raw payload."""
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

    # Numeric metric columns, mean/median per condition (aggregates).
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


def build_tools(s: Session, protocol: dict | None) -> dict[str, Callable[[dict], str]]:
    """The tool name → implementation map. Each returns a string result; none
    can reach a row-level participant event (FR-ETH-4)."""
    return {
        "search_papers": lambda i: search_papers_tool(s, str(i.get("query", ""))),
        "get_protocol": lambda i: get_protocol_tool(protocol),
        "get_dataset_summary": lambda i: get_dataset_summary_tool(s),
    }


# ------------------------------------------------------------- providers


def _post_json(url: str, body: dict, headers: dict[str, str]) -> dict:
    """POST JSON, return parsed JSON. The one network seam - tests inject a
    scripted ``post`` into the providers instead."""
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


class LLMClient(Protocol):
    """The shape every LLM-consuming feature in this module calls against
    (the knowledge assistant, the design conversation's ``design_llm.py``,
    and ``matching.rerank_with_llm``) - formalized now that a second
    provider (``OpenAICompatibleProvider``) is real, not just a duck-typed
    convention."""

    model: str

    def run(
        self, question: str, history: list[dict], tools: dict[str, Callable]
    ) -> tuple[str, list[dict]]: ...


class _ChatCompletionsProvider:
    """A tool-use loop over any host that speaks the OpenAI
    chat-completions shape - Mistral's REST API already speaks this exact
    shape (D32), so an OpenAI-compatible override is the same loop pointed
    at a different ``base_url``/``model``, not a second implementation."""

    name = "chat-completions"

    def __init__(self, base_url: str, api_key: str, model: str, post=_post_json):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.post = post

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

    def __init__(self, api_key: str, model: str = MISTRAL_MODEL, post=_post_json):
        super().__init__(
            "https://api.mistral.ai/v1/chat/completions", api_key, model, post
        )


class OpenAICompatibleProvider(_ChatCompletionsProvider):
    """Any OpenAI-compatible host (OpenAI itself, or a compatible gateway
    in front of another model), configured entirely via env vars
    (``LLM_BASE_URL``/``LLM_API_KEY``/``LLM_MODEL``) - drop in a better
    model's API key and it works immediately, no code change (FR-CONV-1.4).
    """

    name = "openai-compatible"

    def __init__(self, base_url: str, api_key: str, model: str, post=_post_json):
        root = base_url.rstrip("/")
        endpoint = (
            root if root.endswith("/chat/completions") else f"{root}/chat/completions"
        )
        super().__init__(endpoint, api_key, model, post)


def configured() -> bool:
    """Whether an LLM client can be built - the OpenAI-compatible override
    or a Mistral key (D32 rev 2). Without either, LLM-dependent endpoints
    degrade gracefully - every other feature works offline."""
    if os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_API_KEY"):
        return True
    return bool(os.environ.get("MISTRAL_API_KEY"))


def make_client(model: str | None = None) -> LLMClient | None:
    """Resolve the configured LLM client, or ``None`` when nothing is
    configured (callers then degrade gracefully - never raises).

    Resolution order: an OpenAI-compatible override (``LLM_BASE_URL`` +
    ``LLM_API_KEY``, optionally ``LLM_MODEL``) takes priority when set -
    any OpenAI-compatible host works with no code change. Otherwise, a
    Mistral client on the requested tier (``model``, validated against
    ``MISTRAL_MODELS``; unset/invalid falls back to ``MISTRAL_MODEL``, the
    knowledge assistant's own default - pass ``MISTRAL_BEST_MODEL``
    explicitly for the design conversation's "best tier by default"
    behavior, FR-CONV-1.4).
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
    """Pull the ``[...]`` source tags the system prompt requires, in order,
    de-duplicated - the platform renders them as clickable chips."""
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
    """Run the grounded tool-use loop and return ``{answer, citations,
    toolCalls}``. ``client`` and ``tools`` are injected so tests drive a
    scripted provider and in-memory tool impls."""
    answer, tool_calls = client.run(question, history, tools)
    return {
        "answer": answer,
        "citations": _extract_citations(answer),
        "toolCalls": tool_calls,
    }


def protocol_literature_targets(protocol: dict | None) -> dict[str, list[str]]:
    """Seed links from the protocol's ``literature:`` list (FR-LIT-3):
    ``{paperRef: [justifies...]}`` so ingested papers carry their protocol
    links by construction."""
    out: dict[str, list[str]] = {}
    for entry in (protocol or {}).get("literature", []):
        ref = entry.get("paperRef")
        if ref:
            out[ref] = list(entry.get("justifies", []))
    return out
