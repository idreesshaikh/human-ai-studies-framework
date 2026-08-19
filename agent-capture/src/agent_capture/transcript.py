"""Normalize a Claude Code transcript JSONL into agent-leg StudyEvents
(FR-AGENT-1/2).

The transcript at ``~/.claude/projects/<workspace>/<agent-session>.jsonl``
is one JSON object per line. Its exact shape is internal to Claude Code and
documented as version-dependent, so this parser is deliberately *tolerant*:
malformed lines are skipped, missing fields default, and unknown line types
are ignored. Local JSONL is the completeness backstop (NFR-2) - it must
never raise on a session it half-understands.

The same function powers both capture paths, which is what makes them
reconcile (FR-ING-2) instead of duplicate:

- the live hook re-normalizes the transcript-so-far on each trigger and
  POSTs the whole batch (fire-and-forget liveness), and
- the importer normalizes the finished transcript once (completeness).

Because the transcript is append-only, an event's ordinal position is
stable across every re-normalization, so it becomes the producer ``seq``:
the same logical turn/tool-call always lands at the same ``(session,
source, seq)`` key and later POSTs are dropped as duplicates. ``seq`` 0 is
always ``agent_session_meta``.
"""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path

from agent_capture.events import (
    EVENT_SESSION_META,
    EVENT_TOOL_CALL,
    EVENT_TURN,
    SOURCE_AGENT,
    Keys,
    study_event,
)
from agent_capture.redact import DEFAULT_MIN_TOKEN_LEN, apply_policy

_FENCE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)


def read_jsonl(path: str | Path) -> list[dict]:
    """Every parseable JSON object in the file, in order. Tolerant: a
    truncated final line (a session captured mid-write) or a malformed row
    is skipped, never fatal."""
    p = Path(path)
    if not p.is_file():
        return []
    out: list[dict] = []
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _hash(value: str) -> str:
    """Content-free 16-hex token for a path/target (FR-ETH-2): the leg
    stores *which* target was touched as a shape, never the path text."""
    return sha256(value.encode()).hexdigest()[:16]


def _text_of(content: object) -> str:
    """Assistant/user message text, whether ``content`` is a bare string or
    an Anthropic block array (text blocks concatenated)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _blocks(content: object) -> list[dict]:
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict)]


def _code_blocks(text: str) -> list[dict]:
    """Fenced code blocks in the message text as shapes (FR-ETH-2): language
    tag, char count, line count - never the code."""
    out = []
    for lang, body in _FENCE.findall(text):
        out.append(
            {
                "language": lang.strip() or "text",
                "chars": len(body),
                "lines": body.count("\n") + 1 if body else 0,
            }
        )
    return out


def _usage(message: dict) -> dict:
    """Token-usage metadata lifted from the transcript (metadata, allowed at
    every content policy; `requirements/metric-coverage.md` §4)."""
    usage = message.get("usage") or {}
    out = {}
    if "input_tokens" in usage:
        out["inputTokens"] = usage["input_tokens"]
    if "output_tokens" in usage:
        out["outputTokens"] = usage["output_tokens"]
    return out


def _session_meta_payload(lines: list[dict], transcript_path: str | Path) -> dict:
    """agent_session_meta from the first line that reveals model/session/cwd."""
    model = ""
    agent_session_id = Path(transcript_path).stem
    cwd = ""
    for line in lines:
        agent_session_id = line.get("sessionId") or agent_session_id
        cwd = cwd or line.get("cwd", "")
        msg = line.get("message") or {}
        model = model or msg.get("model", "")
        if model and cwd:
            break
    return {
        "agentTool": "claude-code",
        "modelId": model,
        "agentSessionId": agent_session_id,
        "cwdHash": _hash(cwd) if cwd else "",
    }


def _normalize_copilot_chat(
    lines: list[dict],
    keys: Keys,
    policy: str | None,
    *,
    min_token_len: int = DEFAULT_MIN_TOKEN_LEN,
) -> list[dict]:
    """Normalize a Copilot Chat / generic JSON transcript shape.

    Expected line shape: ``{timestamp, role, content, tool_name?, tool_input?}``
    where ``role`` is ``"user"`` or ``"assistant"`` and ``content`` is a bare
    string. Produces the same event contract as Claude Code transcripts.
    """
    logical: list[tuple[str, str, dict]] = []
    prev_ts: str | None = None
    for turn_index, line in enumerate(lines):
        ts = line.get("timestamp", "")
        role = line.get("role", "")
        content = line.get("content", "") or ""
        tool_name = line.get("tool_name", "")
        tool_input = line.get("tool_input") or {}

        payload: dict = {"role": role, "turnIndex": turn_index, "chars": len(content)}
        if prev_ts and ts:
            payload["latencyMs"] = _delta_ms(prev_ts, ts)
        stored = apply_policy(content, policy, min_token_len=min_token_len)
        if stored is not None:
            payload["content"] = stored
        if content:
            payload["codeBlocks"] = _code_blocks(content)
        logical.append((ts, EVENT_TURN, payload))

        if tool_name:
            logical.append(
                (
                    ts,
                    EVENT_TOOL_CALL,
                    {
                        "tool": tool_name,
                        "success": True,
                        "targetHash": _target_hash(tool_input) if tool_input else "",
                    },
                )
            )
        if ts:
            prev_ts = ts

    meta = {"agentTool": "generic", "modelId": "", "agentSessionId": "", "cwdHash": ""}
    for line in lines:
        if line.get("model"):
            meta["modelId"] = line["model"]
        if line.get("sessionId"):
            meta["agentSessionId"] = line["sessionId"]

    ordered = [("", EVENT_SESSION_META, meta), *logical]
    return [
        study_event(keys, source=SOURCE_AGENT, seq=i, type=t, payload=p, ts=ts or None)
        for i, (ts, t, p) in enumerate(ordered)
    ]


def _detect_format(path: str | Path) -> str:
    """Sniff the transcript format from the first line.

    Returns ``"claude-code"`` (Anthropic-style message blocks) or ``"generic-json"``
    (flat role/content lines). Falls back to ``"claude-code"`` when undetectable.
    """
    lines = read_jsonl(path)
    if not lines:
        return "claude-code"
    first = lines[0]
    msg = first.get("message")
    if msg is not None or first.get("type") in ("assistant", "user"):
        return "claude-code"
    if first.get("role") in ("user", "assistant"):
        return "generic-json"
    return "claude-code"


def normalize_transcript(
    transcript_path: str | Path,
    keys: Keys,
    policy: str | None,
    *,
    format: str | None = None,
    min_token_len: int = DEFAULT_MIN_TOKEN_LEN,
) -> list[dict]:
    """The whole transcript as ordered agent-leg StudyEvents (seq = position).

    ``agent_turn`` (both roles), ``tool_call`` (emitted when its result
    lands, so success/duration are known), and a leading
    ``agent_session_meta``. Conversation text passes through the content
    policy (FR-AGENT-5); at ``metadata-only`` no ``content`` field is
    emitted at all.

    ``format`` is ``"claude-code"`` (default), ``"generic-json"``, or
    ``None`` (auto-detect). FR-AGENT-4: second-format support via the
    same event contract.
    """
    fmt = format or _detect_format(transcript_path)
    lines = read_jsonl(transcript_path)

    if fmt == "generic-json":
        return _normalize_copilot_chat(lines, keys, policy, min_token_len=min_token_len)
    logical: list[tuple[str, str, dict]] = []  # (ts, type, payload)
    turn_index = 0
    pending: dict[str, dict] = {}  # tool_use_id -> {name, ts, targetHash}
    prev_ts: str | None = None

    for line in lines:
        mtype = line.get("type")
        ts = line.get("timestamp", "")
        msg = line.get("message") or {}
        content = msg.get("content")

        if mtype == "assistant":
            text = _text_of(content)
            payload = {
                "role": "assistant",
                "turnIndex": turn_index,
                "chars": len(text),
                "responseChars": len(text),  # what the RQ-P5 recipe reads
                "codeBlocks": _code_blocks(text),
                **_usage(msg),
            }
            if prev_ts and ts:
                payload["latencyMs"] = _delta_ms(prev_ts, ts)
            stored = apply_policy(text, policy, min_token_len=min_token_len)
            if stored is not None:
                payload["content"] = stored
            logical.append((ts, EVENT_TURN, payload))
            turn_index += 1
            for b in _blocks(content):
                if b.get("type") == "tool_use":
                    pending[b.get("id", f"tu-{len(pending)}")] = {
                        "name": b.get("name", ""),
                        "ts": ts,
                        "targetHash": _target_hash(b.get("input") or {}),
                    }

        elif mtype == "user":
            # A user line is either a real prompt or a tool_result carrier.
            for b in _blocks(content):
                if b.get("type") == "tool_result":
                    logical.append(_tool_call_event(b, pending, ts))
            text = _text_of(content)
            has_tool_result = any(
                b.get("type") == "tool_result" for b in _blocks(content)
            )
            if text and not has_tool_result:
                payload = {
                    "role": "user",
                    "turnIndex": turn_index,
                    "chars": len(text),
                }
                stored = apply_policy(text, policy, min_token_len=min_token_len)
                if stored is not None:
                    payload["content"] = stored
                logical.append((ts, EVENT_TURN, payload))
                turn_index += 1

        if ts:
            prev_ts = ts

    # Tool calls whose result never arrived (turn cut off) - success unknown.
    for info in pending.values():
        logical.append(
            (
                info["ts"],
                EVENT_TOOL_CALL,
                {
                    "tool": info["name"],
                    "success": None,
                    "targetHash": info["targetHash"],
                },
            )
        )

    meta = _session_meta_payload(lines, transcript_path)
    ordered = [(meta.get("ts", ""), EVENT_SESSION_META, meta), *logical]
    return [
        study_event(keys, source=SOURCE_AGENT, seq=i, type=t, payload=p, ts=ts or None)
        for i, (ts, t, p) in enumerate(ordered)
    ]


def _tool_call_event(
    result_block: dict, pending: dict, ts: str
) -> tuple[str, str, dict]:
    tid = result_block.get("tool_use_id", "")
    info = pending.pop(tid, {"name": "", "ts": ts, "targetHash": ""})
    payload = {
        "tool": info["name"],
        "success": not bool(result_block.get("is_error", False)),
        "targetHash": info["targetHash"],
    }
    if info["ts"] and ts:
        payload["durationMs"] = _delta_ms(info["ts"], ts)
    return (ts, EVENT_TOOL_CALL, payload)


def _target_hash(tool_input: dict) -> str:
    for key in ("file_path", "path", "notebook_path"):
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            return _hash(val)
    return ""


def _delta_ms(start_iso: str, end_iso: str) -> int | None:
    from datetime import datetime

    try:
        a = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return int((b - a).total_seconds() * 1000)
