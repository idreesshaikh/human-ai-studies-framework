from protocol.capture import (
    capture_config_version,
    producer_capabilities,
    session_manifest,
    validate_manifest,
)


def protocol_doc(**overrides):
    doc = {
        "protocolVersion": 4,
        "study": {"id": "pilot"},
        "conditions": ["ai-assisted", "unassisted"],
        "participants": {"planned": 2, "design": "within-subjects"},
        "session": {"durationMinutes": 45},
        "instruments": {
            "tern": {"session": {"durationMinutes": 45}},
            "metrics": {"metricSet": "cognitive-load-9"},
        },
    }
    doc.update(overrides)
    return doc


def test_manifest_has_shared_join_keys_and_no_content():
    protocol = protocol_doc()
    manifest = session_manifest(
        protocol,
        participant_id="P01",
        condition="ai-assisted",
        session_id="s-test",
        endpoints={"events": "http://localhost/events"},
    )

    assert manifest["sessionId"] == "s-test"
    assert manifest["taskId"]
    assert manifest["producers"]["tern"]["state"] == "enabled"
    assert manifest["producers"]["metrics"]["state"] == "external-required"
    assert "sourceCode" not in str(manifest)
    assert validate_manifest(manifest, protocol) == []


def test_unsupported_agent_is_explicit_and_required_capture_fails_validation():
    protocol = protocol_doc(
        instruments={
            "tern": {},
            "agentCapture": {"adapter": "copilot", "required": True},
        }
    )
    capabilities = producer_capabilities(protocol)
    assert capabilities["agent-capture"]["state"] == "unsupported"
    assert "agent-transcript-unavailable" in capabilities["agent-capture"]["reason"]

    manifest = session_manifest(
        protocol,
        participant_id="P01",
        condition="unassisted",
        session_id="s-unsupported",
    )
    assert any("agent-capture" in error for error in validate_manifest(manifest))


def test_manifest_version_changes_when_capture_configuration_changes():
    first = capture_config_version(protocol_doc())
    second = capture_config_version(
        protocol_doc(capture={"privacy": {"agentContentPolicy": "redacted"}})
    )
    assert first != second
