"""Knowledge assistant - grounded Q&A over papers + protocol + dataset
*aggregates* (FR-LIT-4), powered by Gemini or Mistral with tool use (D28,
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
no source must say so. Provider selection is by key: ``GEMINI_API_KEY``
(Google AI Studio) wins over ``MISTRAL_API_KEY``; with neither set the
endpoint degrades gracefully — every other feature works offline.

Both providers speak plain REST over stdlib ``urllib`` (D28: no vendor SDK
- same zero-bloat call shape as the Semantic Scholar client), each with a
hand-rolled tool-use loop, because the tool boundary is the whole point.
"""

from __future__ import annotations

import json
import os
import statistics
import urllib.request
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from middleware import paper_index
from middleware.db import Event, MetricRow

GEMINI_MODEL = "gemini-flash-latest"
MISTRAL_MODEL = "mistral-small-latest"
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
            "properties": {
                "query": {"type": "string", "description": "search terms"}
            },
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


def build_tools(
    s: Session, protocol: dict | None
) -> dict[str, Callable[[dict], str]]:
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


class GeminiProvider:
    """Google AI Studio (Gemini) tool-use loop over the REST API (D28)."""

    name = "gemini"

    def __init__(self, api_key: str, model: str = GEMINI_MODEL, post=_post_json):
        self.api_key = api_key
        self.model = model
        self.post = post

    @staticmethod
    def _tool_config() -> list[dict]:
        decls = []
        for t in TOOL_SCHEMAS:
            decl = {"name": t["name"], "description": t["description"]}
            # Gemini rejects an empty properties object - omit instead.
            if t["input_schema"].get("properties"):
                decl["parameters"] = t["input_schema"]
            decls.append(decl)
        return [{"functionDeclarations": decls}]

    def run(
        self, question: str, history: list[dict], tools: dict[str, Callable]
    ) -> tuple[str, list[dict]]:
        contents = [
            {
                "role": "model" if m.get("role") == "assistant" else "user",
                "parts": [{"text": str(m.get("content", ""))}],
            }
            for m in history
        ]
        contents.append({"role": "user", "parts": [{"text": question}]})
        tool_calls: list[dict] = []
        for _ in range(MAX_TOOL_ROUNDS):
            res = self.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent",
                {
                    "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                    "contents": contents,
                    "tools": self._tool_config(),
                    "generationConfig": {"maxOutputTokens": MAX_TOKENS},
                },
                {"x-goog-api-key": self.api_key},
            )
            candidates = res.get("candidates") or [{}]
            parts = candidates[0].get("content", {}).get("parts", [])
            calls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not calls:
                return "".join(p.get("text", "") for p in parts), tool_calls
            contents.append({"role": "model", "parts": parts})
            responses = []
            for call in calls:
                name = call.get("name", "")
                args = dict(call.get("args") or {})
                impl = tools.get(name)
                output = impl(args) if impl else f"Unknown tool {name}"
                tool_calls.append({"tool": name, "input": args})
                responses.append(
                    {
                        "functionResponse": {
                            "name": name,
                            "response": {"result": output},
                        }
                    }
                )
            contents.append({"role": "user", "parts": responses})
        return "", tool_calls


class MistralProvider:
    """Mistral chat-completions tool-use loop over the REST API (D28)."""

    name = "mistral"

    def __init__(self, api_key: str, model: str = MISTRAL_MODEL, post=_post_json):
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
                "https://api.mistral.ai/v1/chat/completions",
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


def make_client():
    """The configured provider - ``GEMINI_API_KEY`` wins over
    ``MISTRAL_API_KEY`` (D28) - or ``None`` when neither key is set (the
    endpoint then degrades gracefully). Never raises."""
    if key := os.environ.get("GEMINI_API_KEY"):
        return GeminiProvider(key)
    if key := os.environ.get("MISTRAL_API_KEY"):
        return MistralProvider(key)
    return None


def _extract_citations(text: str) -> list[str]:
    """Pull the ``[...]`` source tags the system prompt requires, in order,
    de-duplicated - the dashboard renders them as clickable chips."""
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
