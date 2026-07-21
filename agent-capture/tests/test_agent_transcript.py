"""Transcript import + hook normalization + reconciliation (FR-AGENT-2)."""

import json
from pathlib import Path

from agent_capture.events import SOURCE_AGENT, Keys
from agent_capture.hook import run as hook_run
from agent_capture.transcript import normalize_transcript

_FIXTURES = Path(__file__).parent / "fixtures"


def test_normalizes_turns_tools_and_meta(transcript_path, keys):
    events = normalize_transcript(transcript_path, keys, "metadata-only")
    types = [e["type"] for e in events]

    # Leading session meta, then turns and tool calls interleaved.
    assert types[0] == "agent_session_meta"
    assert events[0]["payload"]["agentTool"] == "claude-code"
    assert events[0]["payload"]["modelId"] == "claude-opus-4-8"
    # cwd is stored only as a content-free hash (FR-ETH-2).
    assert (
        events[0]["payload"]["cwdHash"]
        and "/work" not in events[0]["payload"]["cwdHash"]
    )

    assert types.count("agent_turn") == 4  # 1 user + 3 assistant
    assert types.count("tool_call") == 2  # Read + Edit

    # Every row carries the join keys and the agent-leg schema version.
    for e in events:
        assert e["sessionId"] == "S1"
        assert e["participantId"] == "P01"
        assert e["condition"] == "ai-assisted"
        assert e["source"] == SOURCE_AGENT
        assert e["v"] == 4


def test_seq_is_the_transcript_position_and_dense(transcript_path, keys):
    events = normalize_transcript(transcript_path, keys, "metadata-only")
    assert [e["seq"] for e in events] == list(range(len(events)))


def test_token_usage_is_lifted_as_metadata(transcript_path, keys):
    events = normalize_transcript(transcript_path, keys, "metadata-only")
    assistant = [
        e
        for e in events
        if e["type"] == "agent_turn" and e["payload"]["role"] == "assistant"
    ]
    assert assistant[0]["payload"]["inputTokens"] == 1200
    assert assistant[0]["payload"]["outputTokens"] == 45
    # Code blocks captured as shapes, not code.
    fix_turn = assistant[1]["payload"]
    assert fix_turn["codeBlocks"][0]["language"] == "python"
    assert fix_turn["codeBlocks"][0]["lines"] >= 1


def test_tool_calls_carry_success_and_target_hash(transcript_path, keys):
    events = normalize_transcript(transcript_path, keys, "metadata-only")
    tools = [e for e in events if e["type"] == "tool_call"]
    assert {t["payload"]["tool"] for t in tools} == {"Read", "Edit"}
    for t in tools:
        assert t["payload"]["success"] is True
        # A file target is recorded as a hash, never the path.
        assert t["payload"]["targetHash"]
        assert "detect.py" not in json.dumps(t["payload"])


def test_metadata_only_stores_zero_conversation_text(transcript_path, keys):
    """Acceptance: metadata-only ⇒ no conversation content anywhere
    (grep-the-output, same discipline as FR-ETH-4)."""
    events = normalize_transcript(transcript_path, keys, "metadata-only")
    blob = json.dumps(events)
    for leaked in ("ValueError", "detect", "inverted", "negative amount", "content"):
        assert leaked not in blob
    assert all("content" not in e["payload"] for e in events)


def test_redacted_keeps_shape_masks_content(transcript_path, keys):
    events = normalize_transcript(transcript_path, keys, "redacted")
    turns = [e for e in events if e["type"] == "agent_turn"]
    assert any("content" in t["payload"] for t in turns)
    blob = json.dumps(events)
    assert "ValueError" not in blob  # long identifiers masked
    assert "*" in blob


def test_import_and_reimport_reconcile_via_client(transcript_path, keys, middleware):
    """Hooks + importer of the same session reconcile, not duplicate
    (FR-ING-2): identical (session, source, seq) keys."""
    events = normalize_transcript(transcript_path, keys, "metadata-only")
    wire = {"source": SOURCE_AGENT, "events": events}

    first = middleware.post("/ingest/events", json=wire).json()
    assert first["inserted"] == len(events)
    second = middleware.post("/ingest/events", json=wire).json()
    assert second["inserted"] == 0
    assert second["duplicates"] == len(events)

    stored = middleware.get("/sessions/S1/events?type=agent_turn").json()
    assert len(stored) == 4


def test_hook_run_posts_normalized_events(hook_payload, monkeypatch):
    """The hook core reads stdin JSON + env, normalizes, and returns the POST
    summary - all fire-and-forget."""
    posted = {}

    def fake_post(events, *, source, endpoint, timeout=3.0):
        posted["events"] = events
        posted["source"] = source
        return {"posted": len(events), "inserted": len(events)}

    monkeypatch.setattr("agent_capture.hook.post_events", fake_post)
    env = {
        "STUDY_PARTICIPANT": "P01",
        "STUDY_CONDITION": "ai-assisted",
        "STUDY_SESSION": "S1",
        "STUDY_CONTENT_POLICY": "metadata-only",
    }
    result = hook_run(hook_payload, [], env)
    assert result["posted"] > 0
    assert posted["source"] == SOURCE_AGENT
    assert posted["events"][0]["type"] == "agent_session_meta"


def test_hook_no_transcript_is_a_silent_noop():
    result = hook_run(json.dumps({"session_id": "x"}), [], {})
    assert result == {"posted": 0, "error": "no transcript"}


def test_missing_join_keys_default_empty(transcript_path):
    events = normalize_transcript(transcript_path, Keys(), "metadata-only")
    assert events[0]["participantId"] == ""


# ---------------------------------------------------------------------------
# Slice A — Generic / Copilot transcript adapter (FR-AGENT-4)
# ---------------------------------------------------------------------------


def test_generic_json_format_produces_same_event_contract(keys):
    path = _FIXTURES / "generic-transcript.jsonl"
    events = normalize_transcript(path, keys, "metadata-only", format="generic-json")
    assert len(events) >= 3
    assert events[0]["type"] == "agent_session_meta"
    assert events[0]["payload"]["agentTool"] == "generic"
    types = [e["type"] for e in events]
    assert "agent_turn" in types
    assert "tool_call" in types
    for e in events:
        assert e["sessionId"] == "S1"
        assert e["participantId"] == "P01"
        assert e["source"] == SOURCE_AGENT
        assert e["v"] == 4
    assert [e["seq"] for e in events] == list(range(len(events)))


def test_generic_json_metadata_only_strips_content(keys):
    path = _FIXTURES / "generic-transcript.jsonl"
    events = normalize_transcript(path, keys, "metadata-only", format="generic-json")
    blob = json.dumps(events)
    assert "fibonacci" not in blob
    assert all("content" not in e["payload"] for e in events)


def test_generic_json_redacted_keeps_shape(keys):
    path = _FIXTURES / "generic-transcript.jsonl"
    events = normalize_transcript(path, keys, "redacted", format="generic-json")
    turns = [e for e in events if e["type"] == "agent_turn"]
    assert any("content" in t["payload"] for t in turns)
    blob = json.dumps(events)
    assert "*" in blob


def test_generic_json_produces_dense_seq(keys):
    path = _FIXTURES / "generic-transcript.jsonl"
    events = normalize_transcript(path, keys, "metadata-only", format="generic-json")
    assert [e["seq"] for e in events] == list(range(len(events)))


def test_format_auto_detect_generic_json(keys):
    path = _FIXTURES / "generic-transcript.jsonl"
    events = normalize_transcript(path, keys, "metadata-only", format=None)
    assert events[0]["payload"]["agentTool"] == "generic"


def test_format_auto_detect_claude_code(transcript_path, keys):
    events = normalize_transcript(transcript_path, keys, "metadata-only", format=None)
    assert events[0]["payload"]["agentTool"] == "claude-code"


def test_generic_json_tool_call_has_target_hash(keys):
    path = _FIXTURES / "generic-transcript.jsonl"
    events = normalize_transcript(path, keys, "metadata-only", format="generic-json")
    tools = [e for e in events if e["type"] == "tool_call"]
    assert len(tools) >= 1
    for t in tools:
        assert "targetHash" in t["payload"]
        assert "fib.py" not in json.dumps(t["payload"])


def test_generic_json_unknown_format_falls_back_to_claude_code(keys):
    path = _FIXTURES / "generic-transcript.jsonl"
    events = normalize_transcript(path, keys, "metadata-only", format="bogus")
    # bogus format should be treated as claude-code by the dispatch
    assert len(events) > 0


def test_generic_json_code_blocks_captured_as_shapes(keys):
    path = _FIXTURES / "generic-transcript.jsonl"
    events = normalize_transcript(path, keys, "redacted", format="generic-json")
    assistant = [
        e
        for e in events
        if e["type"] == "agent_turn" and e["payload"].get("role") == "assistant"
    ]
    assert len(assistant) >= 1
    blocks = assistant[0]["payload"].get("codeBlocks", [])
    assert len(blocks) >= 1
    assert blocks[0]["language"] == "python"
    assert blocks[0]["lines"] >= 1


def test_generic_json_and_claude_code_both_respect_policy_table_driven(
    transcript_path, keys
):
    """Table-driven test: every format × policy combination produces the same
    event contract (FR-AGENT-4)."""
    generic_path = _FIXTURES / "generic-transcript.jsonl"
    for fmt, path in (("claude-code", transcript_path), ("generic-json", generic_path)):
        for policy in ("metadata-only", "redacted", "full"):
            events = normalize_transcript(path, keys, policy, format=fmt)
            assert events[0]["type"] == "agent_session_meta"
            assert events[0]["v"] == 4
            assert all(e["source"] == SOURCE_AGENT for e in events)
            assert [e["seq"] for e in events] == list(range(len(events)))


def test_middleware_down_then_import_recovers(transcript_path, keys, middleware):
    """NFR-2: a live POST to a down middleware fails silently (best-effort
    mirror), and the post-session importer recovers the whole session."""
    from agent_capture.ingest import post_events

    events = normalize_transcript(transcript_path, keys, "metadata-only")
    # Middleware "down": an unreachable endpoint - never raises.
    down = post_events(events, source=SOURCE_AGENT, endpoint="http://127.0.0.1:1")
    assert down["posted"] == 0 and down["error"]

    # Importer against the live middleware recovers everything.
    recovered = middleware.post(
        "/ingest/events", json={"source": SOURCE_AGENT, "events": events}
    ).json()
    assert recovered["inserted"] == len(events)
