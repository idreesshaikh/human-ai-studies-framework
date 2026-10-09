import json

import pytest
from protocol.derive import derive_agent_hooks, derive_overlay_settings
from protocol.errors import ProtocolError


def test_tern_configuration_carries_identity_and_declared_probes(pilot):
    settings = derive_overlay_settings(pilot, "P01", "ai-assisted")
    assert settings["tern.participantId"] == "P01"
    assert settings["tern.condition"] == "ai-assisted"
    assert settings["tern.fatigue.intervalMinutes"] == 15
    assert settings["tern.stuck.languages"] == ["python"]
    assert settings["tern.session.durationMinutes"] == 45
    assert settings["tern.output.httpEndpoint"] == "http://127.0.0.1:8000/ingest/events"
    assert settings["tern.ideHealth.enabled"] is False
    assert settings["tern.ideHealth.debounceSeconds"] == 10
    assert settings["tern.comprehensionProbe.enabled"] is True
    assert settings["tern.comprehensionProbe.cadence"] == "every-chunk"
    assert settings["tern.comprehensionProbe.sampleRate"] == 1
    assert settings["tern.comprehensionProbe.probeTypes"] == [
        "predict-output",
        "locate-change",
    ]


def test_every_derived_key_is_a_real_extension_setting(pilot, repo_root):
    """
    Acceptance criterion: the output can be pasted into VS Code settings and accepted by
    the Cognitive Overlay unchanged.
    """
    package_json = json.loads(
        (repo_root / "extension" / "package.json").read_text("utf-8")
    )
    real_settings = set(package_json["contributes"]["configuration"]["properties"])
    derived = set(derive_overlay_settings(pilot, "P01", "unassisted"))
    assert derived <= real_settings, derived - real_settings


def test_ide_health_omitted_when_not_declared(pilot_doc, write_protocol):
    """
    FR-INST-18 safety: ideHealth must not appear in derived settings when the protocol
    doesn't declare it  -  no default-on surprise.
    """
    from protocol.loader import load_protocol

    del pilot_doc["instruments"]["tern"]["ideHealth"]
    del pilot_doc["instruments"]["tern"]["comprehensionProbe"]
    proto = load_protocol(write_protocol(pilot_doc))
    settings = derive_overlay_settings(proto, "P01", "unassisted")
    assert "tern.ideHealth.enabled" not in settings
    assert "tern.ideHealth.debounceSeconds" not in settings
    assert "tern.comprehensionProbe.enabled" not in settings


def test_unknown_condition_is_rejected(pilot):
    with pytest.raises(ProtocolError, match="ai-assisted, unassisted"):
        derive_overlay_settings(pilot, "P01", "with-ai")


def test_agent_hooks_bake_the_protocol_content_policy(pilot):
    """
    The consent-matched content policy comes from the protocol, not a side channel
    (FR-AGENT-5): the pilot declares metadata-only.
    """
    hooks = derive_agent_hooks(pilot, command="uv run agent-capture-hook")["hooks"]
    assert set(hooks) == {"SessionStart", "PostToolUse", "Stop", "SessionEnd"}
    for groups in hooks.values():
        command = groups[0]["hooks"][0]["command"]
        assert "--content-policy metadata-only" in command
        assert command.startswith("uv run agent-capture-hook")
        # Fire-and-forget: a short timeout so a down middleware never stalls the agent
        # (NFR-1).
        assert groups[0]["hooks"][0]["timeout"] <= 10


def test_agent_hooks_reject_unknown_adapter(pilot_doc, write_protocol):
    from protocol.loader import load_protocol

    pilot_doc["instruments"]["agentCapture"]["adapter"] = "copilot-chat"
    proto = load_protocol(write_protocol(pilot_doc))
    with pytest.raises(ProtocolError, match="FR-AGENT-4"):
        derive_agent_hooks(proto)
