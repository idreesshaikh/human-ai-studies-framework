"""Schema vNext for agent participants."""

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
    doc = _load(FIXTURE)
    assert doc["protocolVersion"] == 3
    assert validate_protocol(doc) == []


def test_v3_requires_at_least_one_real_instrument():
    doc = _load(FIXTURE)
    doc["instruments"] = {"metrics": {"metricSet": "cognitive-load-9"}}
    errors = validate_protocol(doc)
    assert errors and any("instruments" in e for e in errors)


def test_v4_still_requires_an_instrument():
    doc = _load(PILOT)
    assert doc["protocolVersion"] == 4
    doc["instruments"] = {"metrics": {"metricSet": "cognitive-load-9"}}
    errors = validate_protocol(doc)
    assert errors and any("instruments" in e for e in errors)


def test_pilot_still_valid():
    assert validate_protocol(_load(PILOT)) == []


def test_v4_curated_still_requires_an_instrument():
    doc = _load(EXAMPLES / "cursor-mining-2026.yaml")
    assert doc["protocolVersion"] == 4
    assert validate_protocol(doc) == []
    doc["instruments"] = {"metrics": {"metricSet": "cognitive-load-9"}}
    errors = validate_protocol(doc)
    assert errors and any("instruments" in e for e in errors)


def test_optional_agent_config_list_validates():
    doc = _load(FIXTURE)
    doc["participants"]["agents"] = [
        {"id": "A01", "tool": "claude-code", "model": "claude-sonnet-5"},
        {"id": "A02", "tool": "claude-code", "model": "claude-opus-4-8"},
    ]
    assert validate_protocol(doc) == []
    doc["participants"]["agents"].append({"id": "A03", "tool": "x"})
    assert validate_protocol(doc)


def test_overlay_derive_fails_cleanly_for_agent_study():
    doc = _load(FIXTURE)
    try:
        derive_overlay_settings(doc, "A01", "no-context")
        raise AssertionError("expected a ProtocolError")
    except ProtocolError as exc:
        assert "agent-hooks" in str(exc)


def test_agent_hooks_derive_works_for_agent_study():
    doc = _load(FIXTURE)
    hooks = derive_agent_hooks(doc)
    blob = str(hooks)
    assert "agent-capture-hook" in blob
    assert "metadata-only" in blob
