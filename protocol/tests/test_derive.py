import json

import pytest
from protocol.derive import derive_agent_hooks, derive_overlay_settings
from protocol.errors import ProtocolError


def test_join_keys_are_set(pilot):
    settings = derive_overlay_settings(pilot, "P01", "ai-assisted")
    assert settings["cognitiveOverlay.participantId"] == "P01"
    assert settings["cognitiveOverlay.condition"] == "ai-assisted"


def test_every_derived_key_is_a_real_extension_setting(pilot, repo_root):
    """Acceptance criterion: the output can be pasted into VS Code settings
    and accepted by the Cognitive Overlay unchanged."""
    package_json = json.loads(
        (repo_root / "extension" / "package.json").read_text("utf-8")
    )
    real_settings = set(package_json["contributes"]["configuration"]["properties"])
    derived = set(derive_overlay_settings(pilot, "P01", "unassisted"))
    assert derived <= real_settings, derived - real_settings


def test_instrument_config_flows_through(pilot):
    settings = derive_overlay_settings(pilot, "P02", "unassisted")
    assert settings["cognitiveOverlay.fatigue.intervalMinutes"] == 15
    assert settings["cognitiveOverlay.stuck.languages"] == ["python"]
    # 45-minute sessions per the frozen pilot protocol (MP-08 deliverable 1).
    assert settings["cognitiveOverlay.session.durationMinutes"] == 45
    assert (
        settings["cognitiveOverlay.output.httpEndpoint"]
        == "http://127.0.0.1:8000/ingest/events"
    )


def test_unknown_condition_is_rejected(pilot):
    with pytest.raises(ProtocolError, match="ai-assisted, unassisted"):
        derive_overlay_settings(pilot, "P01", "with-ai")


# --- agent-leg hook pack (FR-AGENT-2, FR-PROT-4) ---------------------------


def test_agent_hooks_bake_the_protocol_content_policy(pilot):
    """The consent-matched content policy comes from the protocol, not a
    side channel (FR-AGENT-5): the pilot declares metadata-only."""
    hooks = derive_agent_hooks(pilot)["hooks"]
    # Every capture trigger runs the one idempotent hook command.
    assert set(hooks) == {"SessionStart", "PostToolUse", "Stop", "SessionEnd"}
    for groups in hooks.values():
        command = groups[0]["hooks"][0]["command"]
        assert "--content-policy metadata-only" in command
        # Fire-and-forget: a short timeout so a down middleware never stalls
        # the agent (NFR-1).
        assert groups[0]["hooks"][0]["timeout"] <= 10


def test_agent_hooks_command_is_overridable(pilot):
    hooks = derive_agent_hooks(pilot, command="uv run agent-capture-hook")["hooks"]
    assert hooks["Stop"][0]["hooks"][0]["command"].startswith(
        "uv run agent-capture-hook"
    )


def test_agent_hooks_reject_unknown_adapter(pilot_doc, write_protocol):
    from protocol.loader import load_protocol

    pilot_doc["instruments"]["agentCapture"]["adapter"] = "copilot-chat"
    proto = load_protocol(write_protocol(pilot_doc))
    with pytest.raises(ProtocolError, match="FR-AGENT-4"):
        derive_agent_hooks(proto)
