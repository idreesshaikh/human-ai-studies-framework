"""Schema vNext for agent participants.

The fit criterion *is* the fixture: a v3 agent-participant protocol must
validate under vNext, and every v1 protocol must still validate under v1
rules (the schema change is consumers-branch-on-version, not a break).
"""

from pathlib import Path

import yaml
from protocol.derive import derive_agent_hooks, derive_overlay_settings
from protocol.errors import ProtocolError
from protocol.loader import validate_protocol

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "protocol" / "examples"
FIXTURE = Path(__file__).parent / "fixtures" / "agent-participant-v3.yaml"
PILOT = EXAMPLES / "pilot-study.yaml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def test_agent_fixture_validates_under_v3():
    # The FR-PROT-9 fit criterion: the fixture validates unmodified (its only
    # change from the failing draft was the protocolVersion bump).
    doc = _load(FIXTURE)
    assert doc["protocolVersion"] == 3
    assert validate_protocol(doc) == []


def test_v3_requires_at_least_one_real_instrument():
    # A v3 study with only `metrics` (no overlay, no agentCapture, no harness)
    # is refused — an agent study must declare how it captures the agent.
    doc = _load(FIXTURE)
    doc["instruments"] = {"metrics": {"metricSet": "cognitive-load-9"}}
    errors = validate_protocol(doc)
    assert errors and any("instruments" in e for e in errors)


def test_v1_still_requires_cognitive_overlay():
    # v1 behavior is untouched: a v1 study without cognitiveOverlay fails
    # exactly as before the schema change (regression).
    doc = _load(PILOT)
    doc["instruments"] = {"metrics": {"metricSet": "cognitive-load-9"}}
    errors = validate_protocol(doc)
    assert any("cognitiveOverlay" in e for e in errors)


def test_v1_pilot_still_valid():
    assert validate_protocol(_load(PILOT)) == []


def test_v2_curated_still_requires_overlay():
    # v2 (curated) keeps the overlay requirement — only v3 relaxes it.
    doc = _load(EXAMPLES / "cursor-mining-2026.yaml")
    assert doc["protocolVersion"] == 2
    assert validate_protocol(doc) == []  # it declares the overlay
    doc["instruments"] = {"metrics": {"metricSet": "cognitive-load-9"}}
    assert any("cognitiveOverlay" in e for e in validate_protocol(doc))


def test_optional_agent_config_list_validates():
    # The optional participants.agents list (tool+model per agent config) is
    # accepted when present, and its entries are shape-checked.
    doc = _load(FIXTURE)
    doc["participants"]["agents"] = [
        {"id": "A01", "tool": "claude-code", "model": "claude-sonnet-5"},
        {"id": "A02", "tool": "claude-code", "model": "claude-opus-4-8"},
    ]
    assert validate_protocol(doc) == []
    # A malformed agent entry (missing model) is caught.
    doc["participants"]["agents"].append({"id": "A03", "tool": "x"})
    assert validate_protocol(doc)


def test_overlay_derive_fails_cleanly_for_agent_study():
    # An agent study has no overlay to derive — a clean ProtocolError, not a
    # crash (downstream sanity, slice C.3).
    doc = _load(FIXTURE)
    try:
        derive_overlay_settings(doc, "A01", "no-context")
        raise AssertionError("expected a ProtocolError")
    except ProtocolError as exc:
        assert "agent-hooks" in str(exc)


def test_agent_hooks_derive_works_for_agent_study():
    # The harness-oriented derive produces the agent-capture hook config with
    # the content policy baked from the protocol.
    doc = _load(FIXTURE)
    hooks = derive_agent_hooks(doc)
    blob = str(hooks)
    assert "agent-capture-hook" in blob
    assert "metadata-only" in blob  # the fixture's declared content policy
