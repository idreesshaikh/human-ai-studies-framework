"""
Fitting a design conversation into the model's context budget.

A long study-design conversation cannot be sent whole. Cutting it by turn count
drops the researcher's opening framing first  -  the one part that says what the
study is  -  and drops it silently, so the model reasons as though the
conversation began mid-way.

Selection here keeps the framing, spends what is left on the newest turns, and
says out loud when something was dropped. Nothing decision-bearing rides on this:
every accepted, rejected, and proposed move is carried separately and
deterministically by the design state (see ``_load_design_state``). What a cut
loses is prose and rationale, never a decision.
"""

from __future__ import annotations

import re

_CHARS_PER_TOKEN = 4

_MESSAGE_OVERHEAD_TOKENS = 4

ANCHOR_TURNS = 2

ELISION_NOTE = "earlier turns elided to fit the context budget"
TRUNCATION_NOTE = "[turn truncated to fit the context budget]"


def estimate_tokens(turns: list[dict]) -> int:
    """Approximate tokens for a chat history. Deliberately cheap, never exact."""
    return sum(
        _MESSAGE_OVERHEAD_TOKENS + len(turn.get("content") or "") // _CHARS_PER_TOKEN
        for turn in turns
    )


def _elision_turn(dropped: int) -> dict:
    return {
        "role": "system",
        "content": (
            f"[{dropped} {ELISION_NOTE}. Every design decision from them is "
            "carried in the design state below, not lost  -  but their wording "
            "and rationale are not shown. Do not assume the conversation began "
            "at the next turn.]"
        ),
    }


def _truncated(turn: dict, budget_tokens: int) -> dict | None:
    """``turn`` shortened to fit, or ``None`` when not even the marker fits."""
    room = (budget_tokens - _MESSAGE_OVERHEAD_TOKENS) * _CHARS_PER_TOKEN
    keep = room - len(TRUNCATION_NOTE) - 1
    if keep <= 0:
        return None
    return {
        "role": turn.get("role", "user"),
        "content": f"{(turn.get('content') or '')[:keep]} {TRUNCATION_NOTE}",
    }


def select_history(
    turns: list[dict], *, budget_tokens: int, query: str = ""
) -> list[dict]:
    """
    The turns to send, oldest first, within ``budget_tokens``.

    Whole conversation when it fits. Otherwise the researcher's opening anchors,
    an explicit elision note, and as many of the newest turns as the remaining
    budget allows.
    """
    if not turns or estimate_tokens(turns) <= budget_tokens:
        return turns

    anchors: list[dict] = []
    anchor_ids: set[int] = set()
    for turn in turns[:-1]:
        if len(anchors) >= ANCHOR_TURNS:
            break
        if turn.get("role") == "user":
            anchors.append(turn)
            anchor_ids.add(id(turn))

    terms = set(re.findall(r"\b[\w-]{4,}\b", query.lower())) - {
        "what",
        "that",
        "this",
        "with",
        "have",
        "study",
        "please",
        "design",
    }
    if terms:
        candidates = [
            (len(terms & set(re.findall(r"\b[\w-]{4,}\b", t["content"].lower()))), i, t)
            for i, t in enumerate(turns[:-8])
            if t.get("role") == "user" and id(t) not in anchor_ids
        ]
        memory_budget = budget_tokens // 4
        for score, _, turn in sorted(
            candidates, key=lambda item: item[:2], reverse=True
        ):
            cost = estimate_tokens([turn])
            if score >= 2 and cost <= memory_budget:
                anchors.append(turn)
                anchor_ids.add(id(turn))
                memory_budget -= cost
        order = {id(turn): i for i, turn in enumerate(turns)}
        anchors.sort(key=lambda turn: order[id(turn)])

    note = _elision_turn(len(turns) - len(anchors))
    fixed = estimate_tokens([*anchors, note])
    if fixed > budget_tokens:
        newest = _truncated(turns[-1], budget_tokens)
        return [newest] if newest else []

    remaining = budget_tokens - fixed
    recent: list[dict] = []
    for turn in reversed(turns):
        if id(turn) in anchor_ids:
            continue
        cost = estimate_tokens([turn])
        if cost <= remaining:
            recent.append(turn)
            remaining -= cost
            continue
        if not recent:
            shortened = _truncated(turn, remaining)
            if shortened:
                recent.append(shortened)
                remaining -= estimate_tokens([shortened])
        break

    recent.reverse()
    dropped = len(turns) - len(anchors) - len(recent)
    if dropped <= 0:
        return [*anchors, *recent]
    return [*anchors, _elision_turn(dropped), *recent]
