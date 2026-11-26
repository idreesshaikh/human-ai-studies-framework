"""A test double for the language model the design chat needs.

It answers in the JSON shape :mod:`middleware.study_plan` asks for. ``plausible``
behaves like a competent, compliant model: while any part of the plan is open it
drafts the whole plan, and otherwise it answers without proposing anything.
"""

from __future__ import annotations

import json
import urllib.error
from collections.abc import Callable, Iterable

from middleware import assistant

Reply = dict

PLAN = {
    "title": "AI assistance on maintenance tasks",
    "researchQuestions": [
        "Does an AI assistant change how long developers take to finish "
        "maintenance tasks?",
        "Does an AI assistant change developers' perceived workload?",
    ],
    "design": "within-subjects",
    "conditions": ["ai-assisted", "unassisted"],
    "participantDescription": "Professional developers",
    "plannedParticipants": 12,
    "taskDescription": "Complete maintenance tasks in a small Python service.",
    "sessionMinutes": 45,
    "measureIds": ["E1", "S8"],
}

_NOT_A_CHAT_TURN = {"text": "", "moves": []}


def _is_chat_turn(body: dict) -> bool:
    return "<researcher_message>" in body["messages"][-1]["content"]


def _provider(handler: Callable[[dict], Reply], captured: list | None = None):
    def post(url, body, headers):
        if captured is not None:
            captured.append(body)
        reply = handler(body) if _is_chat_turn(body) else _NOT_A_CHAT_TURN
        return {"choices": [{"message": {"content": json.dumps(reply)}}]}

    return assistant.MistralProvider("test-key", post=post)


def draft(
    reply: str = "Here is a plan to react to.",
    *,
    sources: dict | None = None,
    **overrides,
) -> Reply:
    """A reply that proposes the whole plan, with ``overrides`` applied and
    ``sources`` citing retrieved papers by id."""
    return {
        "reply": reply,
        "questions": [],
        "changes": {**PLAN, **overrides},
        "why": {"plannedParticipants": "A crossover needs fewer people."},
        "caution": "Order effects can remain after counterbalancing.",
        "sources": sources or {},
    }


def talk(reply: str, *questions: str, **changes) -> Reply:
    """A reply that talks, asks and proposes only ``changes``."""
    return {
        "reply": reply,
        "questions": [{"ask": q, "options": []} for q in questions],
        "changes": changes,
    }


def always(reply: Reply, captured: list | None = None):
    """A model that gives the same reply to every chat turn."""
    return _provider(lambda _body: reply, captured)


def in_turn(replies: Iterable[Reply], captured: list | None = None):
    """A model that gives each reply once, in order, then repeats the last."""
    queue = list(replies)
    assert queue, "in_turn needs at least one reply"
    state = {"i": 0}

    def handler(_body: dict) -> Reply:
        reply = queue[min(state["i"], len(queue) - 1)]
        state["i"] += 1
        return reply

    return _provider(handler, captured)


def silent(captured: list | None = None):
    """A model that replies with prose and proposes nothing."""
    return always(talk("Noted."), captured)


def plausible(captured: list | None = None, plan: dict | None = None):
    """Drafts the plan while any part of it is open; otherwise just answers."""

    def handler(body: dict) -> Reply:
        prompt = body["messages"][-1]["content"]
        state = prompt.split("</study_state>", 1)[0]
        if "[open]" in state and "chose answers only" not in prompt:
            return draft(**(plan or {}))
        return talk("The plan already covers that.")

    return _provider(handler, captured)


def outage():
    """A configured provider that fails on every call."""

    class _Raises:
        model = "test"
        api_key = "k"
        base_url = "https://example.invalid/chat/completions"

        def post(self, *a, **k):
            raise TimeoutError("simulated provider outage")

    return _Raises()


def rejected_key():
    """A configured provider that refuses the credential, counting its calls."""

    class _Rejects:
        model = "test"
        api_key = "k"
        base_url = "https://example.invalid/chat/completions"
        calls = 0

        def post(self, *a, **k):
            self.calls += 1
            raise urllib.error.HTTPError(self.base_url, 401, "Unauthorized", {}, None)

    return _Rejects()
