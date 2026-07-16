"""Knowledge assistant - grounded Q&A over papers + protocol + dataset
*aggregates* (FR-LIT-4), powered by the Claude API with tool use (D10/D22).

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
no source must say so. Without ``ANTHROPIC_API_KEY`` the endpoint degrades
gracefully — every other feature works offline.

Model + API usage verified against the ``claude-api`` skill at build time
(2026-07-12): ``claude-sonnet-5`` (the current Sonnet-class model, D10), no
``temperature``/``top_p`` (rejected with a 400 on current models — steer by
prompting instead), a hand-rolled tool-use loop (no beta dependency, and the
tool boundary is the whole point).
"""

from __future__ import annotations

import json
import os
import statistics
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from middleware import paper_index
from middleware.db import Event, MetricRow

MODEL = "claude-sonnet-5"
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


# ---------------------------------------------------------------- the loop


def make_client():
    """The Anthropic client, or ``None`` when no key is configured (the
    endpoint then degrades gracefully). Never raises."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
    except ImportError:
        return None
    return anthropic.Anthropic()


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
    model: str = MODEL,
) -> dict:
    """Run the grounded tool-use loop and return ``{answer, citations,
    toolCalls}``. ``client`` and ``tools`` are injected so tests drive a
    mocked Claude and in-memory tool impls."""
    messages: list[dict] = [*history, {"role": "user", "content": question}]
    tool_calls: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            impl = tools.get(block.name)
            output = impl(dict(block.input)) if impl else f"Unknown tool {block.name}"
            tool_calls.append({"tool": block.name, "input": dict(block.input)})
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output,
                }
            )
        messages.append({"role": "user", "content": results})

    answer = "".join(
        getattr(b, "text", "")
        for b in messages[-1]["content"]
        if getattr(b, "type", None) == "text"
    ) if isinstance(messages[-1]["content"], list) else ""
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
