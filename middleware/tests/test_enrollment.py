from middleware.db import EnrollmentToken, make_session_factory

from middleware import enrollment

PROTOCOL = {
    "study": {"id": "pilot", "title": "Pilot"},
    "conditions": ["ai-assisted", "unassisted"],
    "participants": {"planned": 8},
    "session": {"durationMinutes": 60},
    "instruments": {
        "tern": {
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
    assert enrollment.capture_config_version(PROTOCOL) == v1
    changed = {
        **PROTOCOL,
        "instruments": {"tern": {"stuck": {"enabled": False}}},
    }
    assert enrollment.capture_config_version(changed) != v1


def test_build_capture_config_carries_derived_overlay_settings():
    cfg = enrollment.build_capture_config(PROTOCOL, "P03", "ai-assisted")
    assert cfg["producer"] == "overlay"
    assert cfg["captureConfigVersion"] == enrollment.capture_config_version(PROTOCOL)
    assert cfg["settings"]["tern.participantId"] == "P03"
    assert cfg["settings"]["tern.stuck.enabled"] is True


def test_enabled_instruments_summarizes_explicit_toggles():
    cfg = enrollment.build_capture_config(PROTOCOL, "P03", "ai-assisted")
    summary = enrollment.enabled_instruments(cfg["settings"])
    assert summary == [{"name": "stuck", "enabled": True}]


def test_enabled_instruments_reflects_a_disabled_toggle():
    settings = {
        "tern.participantId": "P03",
        "tern.stuck.enabled": False,
        "tern.output.httpEndpoint": "http://x",
    }
    assert enrollment.enabled_instruments(settings) == [
        {"name": "stuck", "enabled": False}
    ]


def test_apply_capture_overrides_layers_on_derived_settings():
    settings = {
        "tern.participantId": "P03",
        "tern.stuck.enabled": True,
        "tern.behavior.captureAiLifecycle": True,
    }
    overrides = {
        "toggles": [
            {
                "instrument": "tern",
                "path": ["behavior", "captureAiLifecycle"],
                "value": False,
            }
        ]
    }
    out = enrollment.apply_capture_overrides(settings, overrides)
    assert out["tern.behavior.captureAiLifecycle"] is False
    # The non-overridden setting is untouched.
    assert out["tern.stuck.enabled"] is True


def test_apply_capture_overrides_is_a_no_op_without_overrides():
    settings = {"tern.stuck.enabled": True}
    assert enrollment.apply_capture_overrides(settings, None) == settings
    assert enrollment.apply_capture_overrides(settings, {"toggles": []}) == settings


def test_build_capture_config_applies_overrides():
    cfg = enrollment.build_capture_config(
        PROTOCOL,
        "P03",
        "ai-assisted",
        overrides={
            "toggles": [
                {"instrument": "tern", "path": ["stuck", "enabled"], "value": False}
            ]
        },
    )
    assert cfg["settings"]["tern.stuck.enabled"] is False


def test_clean_capture_overrides_drops_malformed_entries():
    raw = {
        "toggles": [
            {"instrument": "tern", "path": ["stuck", "enabled"], "value": False},
            {"instrument": "", "path": [], "value": True},  # empty instrument
            {"instrument": "tern", "path": "not-a-list", "value": True},
            {"instrument": "tern", "path": ["ok"], "value": True, "extra": 1},
        ]
    }
    cleaned = enrollment.clean_capture_overrides(raw)
    assert cleaned == {
        "toggles": [
            {"instrument": "tern", "path": ["stuck", "enabled"], "value": False},
            {"instrument": "tern", "path": ["ok"], "value": True},
        ]
    }


def test_clean_capture_overrides_none_for_empty():
    assert enrollment.clean_capture_overrides(None) is None
    assert enrollment.clean_capture_overrides({"toggles": []}) is None


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
    assert "Pilot" in text
    assert "ai-assisted" in text
    assert "metadata-only" in text
    assert "raw code" in text.lower()


ALL_FOUR = {
    **PROTOCOL,
    "instruments": {
        "tern": {
            "stuck": {"enabled": True, "thresholdSeconds": 90},
            "behavior": {"enabled": True, "captureAiLifecycle": True},
            "ideHealth": {"enabled": True},
        },
        "metrics": {"enabled": True, "snapshot": {"enabled": True}},
        "agentCapture": {"enabled": True, "contentPolicy": "redacted"},
    },
}


def test_toggle_catalog_covers_four_legs_when_protocol_enables_them():
    legs = {e["leg"] for e in enrollment.toggle_catalog(ALL_FOUR)}
    assert legs == set(enrollment.LEG_ORDER)


def test_every_catalog_entry_carries_a_leg_and_honest_grounding():
    for entry in enrollment.toggle_catalog(ALL_FOUR):
        assert entry["leg"] in enrollment.LEG_ORDER
        assert entry["label"] and entry["description"]
        grounding = entry["grounding"]
        # Either a real ref into the SRS/corpus, or honestly marked unsourced
        # (FR-CONV-2)  -  never a bare, unlabelled absence.
        assert grounding.get("unsourced") is True or grounding.get("ref")


def test_leg_summary_always_returns_all_four_in_order():
    summary = enrollment.leg_summary(ALL_FOUR)
    assert [s["leg"] for s in summary] == list(enrollment.LEG_ORDER)


def test_a_leg_the_protocol_omits_is_unavailable_not_disabled():
    by_leg = {s["leg"]: s for s in enrollment.leg_summary(PROTOCOL)}
    assert by_leg[enrollment.LEG_METRICS]["state"] == "unavailable"
    assert by_leg[enrollment.LEG_AGENT]["state"] == "unavailable"
    assert by_leg[enrollment.LEG_COGNITIVE]["state"] == "enabled"


def test_a_leg_switched_off_reads_disabled():
    off = {
        **ALL_FOUR,
        "instruments": {
            **ALL_FOUR["instruments"],
            "metrics": {"enabled": False, "snapshot": {"enabled": False}},
        },
    }
    by_leg = {s["leg"]: s for s in enrollment.leg_summary(off)}
    assert by_leg[enrollment.LEG_METRICS]["state"] == "disabled"


def test_leg_summary_carries_that_legs_toggles_and_nothing_else():
    by_leg = {s["leg"]: s for s in enrollment.leg_summary(ALL_FOUR)}
    metrics = by_leg[enrollment.LEG_METRICS]
    assert metrics["toggles"]
    assert all(t["leg"] == enrollment.LEG_METRICS for t in metrics["toggles"])
    assert all(t["instrument"] == "metrics" for t in metrics["toggles"])


def test_snapshot_toggles_name_the_consent_consequence():
    entries = enrollment.toggle_catalog(ALL_FOUR)
    snapshot = next(e for e in entries if e["path"] == ["snapshot", "enabled"])
    assert "consent" in snapshot["description"].lower()
