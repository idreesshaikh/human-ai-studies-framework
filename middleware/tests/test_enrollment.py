from middleware.db import EnrollmentToken, make_session_factory

from middleware import enrollment

PROTOCOL = {
    "study": {"id": "pilot", "title": "Pilot"},
    "conditions": ["ai-assisted", "unassisted"],
    "participants": {"planned": 8},
    "session": {"durationMinutes": 60},
    "instruments": {
        "cognitiveOverlay": {
            "stuck": {"enabled": True, "thresholdSeconds": 90},
            "output": {"httpEndpoint": "http://x/ingest/events"},
        }
    },
}


def test_enrollment_token_round_trips(tmp_path):
    factory = make_session_factory(str(tmp_path / "t.sqlite3"))
    with factory() as s:
        s.add(
            EnrollmentToken(
                id="e1",
                study_id="pilot",
                participant_id="P01",
                condition="ai-assisted",
                grain="participant",
                token="tok-abc",
                expires_at="2099-01-01T00:00:00Z",
                created_at="2026-07-19T00:00:00Z",
            )
        )
        s.commit()
    with factory() as s:
        row = s.query(EnrollmentToken).filter_by(token="tok-abc").one()
        assert row.participant_id == "P01"
        assert row.grain == "participant"
        assert row.credential is None
        assert row.redeemed_at is None


def test_connection_string_format():
    assert (
        enrollment.connection_string("https://s.example/", "tok-1")
        == "https://s.example#tok-1"
    )


def test_capture_config_version_is_stable_and_content_sensitive():
    v1 = enrollment.capture_config_version(PROTOCOL)
    assert len(v1) == 12
    assert enrollment.capture_config_version(PROTOCOL) == v1  # deterministic
    changed = {
        **PROTOCOL,
        "instruments": {"cognitiveOverlay": {"stuck": {"enabled": False}}},
    }
    assert enrollment.capture_config_version(changed) != v1


def test_build_capture_config_carries_derived_overlay_settings():
    cfg = enrollment.build_capture_config(PROTOCOL, "P03", "ai-assisted")
    assert cfg["producer"] == "overlay"
    assert cfg["captureConfigVersion"] == enrollment.capture_config_version(PROTOCOL)
    assert cfg["settings"]["cognitiveOverlay.participantId"] == "P03"
    assert cfg["settings"]["cognitiveOverlay.stuck.enabled"] is True


def test_enabled_instruments_summarizes_explicit_toggles():
    cfg = enrollment.build_capture_config(PROTOCOL, "P03", "ai-assisted")
    summary = enrollment.enabled_instruments(cfg["settings"])
    assert summary == [{"name": "stuck", "enabled": True}]


def test_enabled_instruments_reflects_a_disabled_toggle():
    settings = {
        "cognitiveOverlay.participantId": "P03",
        "cognitiveOverlay.stuck.enabled": False,
        "cognitiveOverlay.output.httpEndpoint": "http://x",
    }
    assert enrollment.enabled_instruments(settings) == [
        {"name": "stuck", "enabled": False}
    ]


def test_content_policy_defaults_to_metadata_only():
    assert enrollment.content_policy(PROTOCOL) == "metadata-only"
    p = {
        **PROTOCOL,
        "instruments": {
            **PROTOCOL["instruments"],
            "agentCapture": {"contentPolicy": "redacted"},
        },
    }
    assert enrollment.content_policy(p) == "redacted"


def test_consent_statement_is_derived_and_names_the_policy():
    text = enrollment.consent_statement(PROTOCOL, "ai-assisted")
    assert "Pilot" in text  # study title
    assert "ai-assisted" in text  # condition
    # active content policy stated verbatim (FR-AGENT-5)
    assert "metadata-only" in text
    assert "raw code" in text.lower()  # the never-captured promise
