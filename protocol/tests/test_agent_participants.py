"""Schema vNext for agent participants.

The fit criterion *is* the fixture: a v3 agent-participant protocol must
validate under vNext, and older-versioned protocols still validate under
their own rules (the schema change is consumers-branch-on-version, not a
break) — including the v1/v2 -> v4 kite->tern rename (2026-07-21): v1/v2
still require `kite` unchanged (see `protocol/tests/fixtures/broken-*.yaml`,
still on v1), v3 still requires anyOf(kite, agentCapture, taskHarness)
unchanged (see `agent-participant-v3.yaml`), and v4 requires anyOf(tern,
agentCapture, taskHarness) — the live examples (`pilot-study.yaml`,
`cursor-mining-2026.yaml`) were migrated to v4 as part of the rename.
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


def test_v4_still_requires_an_instrument():
    # PILOT is now v4 (post kite->tern rename, 2026-07-21): a study with
    # none of tern/agentCapture/taskHarness still fails, exactly as the
    # pre-rename v1/v2 posture required kite specifically (regression).
    # v4's anyOf is the same shape as v3's (see test_v3_requires_at_least_
    # one_real_instrument above), so the error is the same generic anyOf
    # message, not a literal "tern" mention.
    doc = _load(PILOT)
    assert doc["protocolVersion"] == 4
    doc["instruments"] = {"metrics": {"metricSet": "cognitive-load-9"}}
    errors = validate_protocol(doc)
    assert errors and any("instruments" in e for e in errors)


def test_pilot_still_valid():
    assert validate_protocol(_load(PILOT)) == []


def test_v4_curated_still_requires_an_instrument():
    # cursor-mining-2026.yaml is now v4 too (post kite->tern rename): the
    # curated path still needs a declared instrument (tern here, nominal
    # and unused by the mined path — see the file's own header comment).
    doc = _load(EXAMPLES / "cursor-mining-2026.yaml")
    assert doc["protocolVersion"] == 4
    assert validate_protocol(doc) == []  # it declares the overlay
    doc["instruments"] = {"metrics": {"metricSet": "cognitive-load-9"}}
    errors = validate_protocol(doc)
    assert errors and any("instruments" in e for e in errors)


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
