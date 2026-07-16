"""MP-12 acceptance walk, end to end against the live middleware.

A scripted session - the participant pastes an error, asks Claude Code to
fix a bug, the fix is applied, tests go green - must produce: live hook
events during the session, a reconciled (no-duplicate) set after transcript
import, >= 1 reliance_loop, an edit_burst annotated with agentTurnRef,
workspace_snapshot commits, and a task_outcome with firstGreenMs - and,
under metadata-only, zero conversation text. Finally the two RQ-P5 recipes
run over the joined dataset, closing the producer->consumer contract with
MP-07.
"""

from datetime import UTC, datetime, timedelta

from agent_capture.correlate import correlate_session
from agent_capture.events import (
    SOURCE_AGENT,
    SOURCE_DERIVED,
    SOURCE_HARNESS,
    SOURCE_SNAPSHOT,
    Keys,
)
from agent_capture.evolution import derive_evolution
from agent_capture.harness import Harness
from agent_capture.snapshot import Snapshotter
from agent_capture.transcript import normalize_transcript

KEYS = Keys("P01", "ai-assisted", "S1")
BASE = datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC)


def _iso(offset_s):
    return (BASE + timedelta(seconds=offset_s)).isoformat(timespec="milliseconds")


def _behavioral_events():
    """The editor leg's side of the scripted session (extension schema v3):
    the participant pastes the error, then an AI-origin burst lands the fix.
    Timed to bracket the transcript's turns so the reliance loop closes."""
    common = {"v": 3, "participantId": "P01", "condition": "ai-assisted"}
    return [
        {**common, "sessionId": "S1", "seq": 0, "ts": _iso(-2),
         "type": "clipboard_paste",
         "payload": {"charCount": 180, "lineCount": 6, "targetFile": "terminal"}},
        {**common, "sessionId": "S1", "seq": 1, "ts": _iso(20),
         "type": "edit_burst",
         "payload": {"origin": "ai", "charsAdded": 52, "charsDeleted": 4,
                     "linesTouched": 2, "file": "detect.py"}},
    ]


def test_scripted_session_end_to_end(middleware, transcript_path, tmp_path):
    client = middleware

    # 1. Editor leg lands live (source cognitive-overlay).
    client.post(
        "/ingest/events",
        json={"source": "cognitive-overlay", "events": _behavioral_events()},
    )

    # 2. Agent leg: live hooks land, then the post-session importer re-posts
    #    the same normalized set - reconciled, not duplicated (FR-ING-2).
    agent_events = normalize_transcript(transcript_path, KEYS, "metadata-only")
    wire = {"source": SOURCE_AGENT, "events": agent_events}
    live = client.post("/ingest/events", json=wire).json()
    assert live["inserted"] == len(agent_events)
    reimport = client.post("/ingest/events", json=wire).json()
    assert reimport["inserted"] == 0 and reimport["duplicates"] == len(agent_events)

    # 3. Workspace snapshot (real shadow git) + participant has no commits yet.
    ws = tmp_path / "task"
    ws.mkdir()
    (ws / "detect.py").write_text("def detect(a):\n    return a\n")
    snap = Snapshotter(KEYS, ws, tmp_path / "shadow.git")
    snap_events = snap.snapshot(trigger="save")
    client.post(
        "/ingest/events",
        json={"source": SOURCE_SNAPSHOT, "events":
              [e for e in snap_events if e["source"] == SOURCE_SNAPSHOT]},
    )

    # 4. Task harness: suite goes green -> task_outcome with firstGreenMs.
    tests = tmp_path / "task-tests"
    tests.mkdir()
    (tests / "test_detect.py").write_text("def test_ok():\n    assert True\n")
    harness = Harness(KEYS, tests, session_start=BASE)
    outcome = harness.run(trigger="session-end")
    assert outcome["payload"]["passed"] is True
    assert outcome["payload"]["firstGreenMs"] >= 0
    client.post(
        "/ingest/events", json={"source": SOURCE_HARNESS, "events": [outcome]}
    )

    # 5. Correlate over the joined dataset -> derived reliance loop + burst
    #    annotation, posted back (never overwriting raw data).
    rows = client.get("/studies/pilot-2026/dataset").json()["rows"]
    derived = correlate_session(rows, KEYS, window_s=120)
    evo = derive_evolution(rows, KEYS)
    if evo:
        derived.append(evo)
    client.post(
        "/ingest/events", json={"source": SOURCE_DERIVED, "events": derived}
    )

    loops = [e for e in derived if e["type"] == "reliance_loop"]
    annotations = [e for e in derived if e["type"] == "edit_burst_annotation"]
    assert len(loops) >= 1
    assert annotations and annotations[0]["payload"]["agentTurnRef"]["seq"] is not None

    # 6. Acceptance invariants on the stored data.
    all_rows = client.get("/studies/pilot-2026/dataset").json()["rows"]
    types = {r["type"] for r in all_rows}
    assert {"agent_turn", "tool_call", "agent_session_meta", "workspace_snapshot",
            "task_outcome", "reliance_loop"} <= types

    # metadata-only: zero conversation text anywhere in the store.
    import json as _json

    blob = _json.dumps(all_rows)
    for leaked in ("ValueError", "negative amount", "inverted", "content"):
        assert leaked not in blob

    # Each producer stream is independently gap-complete (source-namespaced
    # seq, NFR-1/2).
    gaps = client.get("/sessions/S1/gaps").json()
    by_source = {s["source"]: s for s in gaps["sources"]}
    assert by_source[SOURCE_AGENT]["complete"] is True
    assert by_source["cognitive-overlay"]["complete"] is True


def test_recipes_consume_the_agent_contract(middleware, transcript_path, tmp_path):
    """The RQ-P5 recipes run over the emitted events without error and read
    the agent leg - proving the MP-12 producer matches the MP-07 consumer."""
    import analysis.recipes  # noqa: F401 - registers recipes via @recipe
    from analysis.core import REGISTRY
    from analysis.dataset import Dataset

    client = middleware
    client.post(
        "/ingest/events",
        json={"source": "cognitive-overlay", "events": _behavioral_events()},
    )
    agent_events = normalize_transcript(transcript_path, KEYS, "metadata-only")
    client.post(
        "/ingest/events", json={"source": SOURCE_AGENT, "events": agent_events}
    )
    # A real passing suite gives the recipe a definite verdict to work with.
    tests = tmp_path / "t"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    outcome = Harness(KEYS, tests, session_start=BASE).run()
    client.post(
        "/ingest/events", json={"source": SOURCE_HARNESS, "events": [outcome]}
    )
    rows = client.get("/studies/pilot-2026/dataset").json()["rows"]
    client.post(
        "/ingest/events",
        json={"source": SOURCE_DERIVED,
              "events": correlate_session(rows, KEYS, window_s=120)},
    )

    dataset = Dataset(rows=client.get("/studies/pilot-2026/dataset").json()["rows"])
    dyn = REGISTRY["agent-interaction-dynamics"].run(dataset)
    assert "RQ-P5" in dyn.summary or "Agent" in dyn.summary
    assert not dyn.tables["per_session"].empty
    # Reliance loops surfaced to the recipe.
    assert "reliance_loops" in dyn.tables

    out = REGISTRY["task-outcome-by-condition"].run(dataset)
    assert not out.tables["per_session"].empty
