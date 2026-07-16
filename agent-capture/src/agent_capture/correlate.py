"""Cross-leg correlation (FR-AGENT-3) - the agent leg meeting the editor leg.

Two derivations, run post-ingest over one session's events:

1. **Burst annotation.** An assistant ``agent_turn`` carrying code blocks,
   followed within a window by an ``edit_burst`` (origin ``ai``/``paste``)
   or ``clipboard_paste`` of matching size, is ground truth that the burst
   came from the agent: we emit a derived ``edit_burst_annotation`` linking
   the burst to the turn (``agentTurnRef``), strengthening FR-INST-10's
   heuristic origin classification.

2. **Reliance loop.** The error->agent->paste-back dynamic RQ-P5 is about:
   a ``clipboard_paste`` (error/context pasted to the agent), then a user
   ``agent_turn``, then an assistant ``agent_turn`` with code, then an
   AI-origin ``edit_burst`` back in the editor - all within windows - is
   emitted as a derived ``reliance_loop`` span.

Derived events are marked ``derived: true`` and written under their own
producer stream (``agent-derived``); they never overwrite raw data. The job
is deterministic (ordinal ``seq``), so re-running reconciles.
"""

from __future__ import annotations

from datetime import datetime

from agent_capture.events import (
    EVENT_BURST_ANNOTATION,
    EVENT_RELIANCE_LOOP,
    SOURCE_DERIVED,
    Keys,
    study_event,
)

DEFAULT_WINDOW_S = 120.0
DEFAULT_SIZE_TOL_FRAC = 0.5
DEFAULT_SIZE_TOL_ABS = 20


def _ts(event: dict) -> datetime | None:
    raw = event.get("ts", "")
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _seconds(a: dict, b: dict) -> float | None:
    ta, tb = _ts(a), _ts(b)
    if ta is None or tb is None:
        return None
    return (tb - ta).total_seconds()


def _turn_code_chars(turn: dict) -> int:
    p = turn.get("payload", {})
    blocks = p.get("codeBlocks") or []
    if blocks:
        return sum(int(b.get("chars", 0)) for b in blocks)
    return int(p.get("responseChars", 0) or 0)


def _of(events: list[dict], type_: str) -> list[dict]:
    return [e for e in events if e.get("type") == type_]


def find_burst_annotations(
    events: list[dict],
    *,
    window_s: float = DEFAULT_WINDOW_S,
    size_tol_frac: float = DEFAULT_SIZE_TOL_FRAC,
    size_tol_abs: int = DEFAULT_SIZE_TOL_ABS,
) -> list[dict]:
    """Payloads linking AI/paste ``edit_burst`` rows to the assistant turn
    that most plausibly produced them (nearest preceding turn within the
    window and size tolerance)."""
    turns = [
        e
        for e in _of(events, "agent_turn")
        if e.get("payload", {}).get("role") == "assistant"
        and _turn_code_chars(e) > 0
    ]
    out = []
    for burst in _of(events, "edit_burst"):
        if burst.get("payload", {}).get("origin") not in ("ai", "paste"):
            continue
        added = int(burst.get("payload", {}).get("charsAdded", 0) or 0)
        best = None
        for turn in turns:
            gap = _seconds(turn, burst)
            if gap is None or not (0 <= gap <= window_s):
                continue
            code = _turn_code_chars(turn)
            tol = max(size_tol_abs, size_tol_frac * code)
            if abs(added - code) <= tol:
                best = turn  # keep latest matching preceding turn
        if best is not None:
            out.append(
                {
                    "burstRef": best_ref(burst),
                    "agentTurnRef": best_ref(best),
                    "burstCharsAdded": added,
                    "turnCodeChars": _turn_code_chars(best),
                    "derived": True,
                }
            )
    return out


def best_ref(event: dict) -> dict:
    """A content-free reference to a raw event: its (source, seq)."""
    return {"source": event.get("source", ""), "seq": event.get("seq")}


def find_reliance_loops(
    events: list[dict], *, window_s: float = DEFAULT_WINDOW_S
) -> list[dict]:
    """Payloads for error->agent->paste-back spans (see module docstring)."""
    ordered = sorted(events, key=lambda e: (e.get("ts", ""), e.get("seq") or 0))
    pastes = _of(ordered, "clipboard_paste")
    loops = []
    for paste in pastes:
        user_turn = _next_after(
            ordered, paste, "agent_turn", window_s, role="user"
        )
        if user_turn is None:
            continue
        asst_turn = _next_after(
            ordered, user_turn, "agent_turn", window_s, role="assistant",
            require_code=True,
        )
        if asst_turn is None:
            continue
        burst = _next_after(
            ordered, asst_turn, "edit_burst", window_s, origin=("ai", "paste")
        )
        if burst is None:
            continue
        span_s = _seconds(paste, burst) or 0.0
        loops.append(
            {
                "startRef": best_ref(paste),
                "endRef": best_ref(burst),
                "userTurnRef": best_ref(user_turn),
                "assistantTurnRef": best_ref(asst_turn),
                "durationMs": int(span_s * 1000),
                "derived": True,
            }
        )
    return loops


def _next_after(
    ordered: list[dict],
    anchor: dict,
    type_: str,
    window_s: float,
    *,
    role: str | None = None,
    require_code: bool = False,
    origin: tuple[str, ...] | None = None,
) -> dict | None:
    for e in ordered:
        if e.get("type") != type_:
            continue
        gap = _seconds(anchor, e)
        if gap is None or gap <= 0 or gap > window_s:
            continue
        p = e.get("payload", {})
        if role is not None and p.get("role") != role:
            continue
        if require_code and _turn_code_chars(e) <= 0:
            continue
        if origin is not None and p.get("origin") not in origin:
            continue
        return e
    return None


def correlate_session(
    events: list[dict], keys: Keys, *, window_s: float = DEFAULT_WINDOW_S
) -> list[dict]:
    """All derived StudyEvents for one session (deterministic ``seq``)."""
    annotations = find_burst_annotations(events, window_s=window_s)
    loops = find_reliance_loops(events, window_s=window_s)
    derived: list[dict] = []
    seq = 0
    for payload in annotations:
        derived.append(
            study_event(
                keys, source=SOURCE_DERIVED, seq=seq,
                type=EVENT_BURST_ANNOTATION, payload=payload,
            )
        )
        seq += 1
    for payload in loops:
        derived.append(
            study_event(
                keys, source=SOURCE_DERIVED, seq=seq,
                type=EVENT_RELIANCE_LOOP, payload=payload,
            )
        )
        seq += 1
    return derived
