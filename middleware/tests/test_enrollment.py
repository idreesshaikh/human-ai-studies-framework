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


def test_build_capture_config_carries_derived_overlay_settings():
    cfg = enrollment.build_capture_config(PROTOCOL, "P03", "ai-assisted")
    assert cfg["producer"] == "overlay"
    assert cfg["captureConfigVersion"] == enrollment.capture_config_version(PROTOCOL)
    assert cfg["settings"]["tern.participantId"] == "P03"
    assert cfg["settings"]["tern.stuck.enabled"] is True


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
    text = enrollment.consent_statement(PROTOCOL)
    assert "Pilot" in text
    assert not any(c in text for c in PROTOCOL["conditions"])
    assert "metadata-only" in text
    assert "Workspace content capture is not enabled" in text
    full = {
        **PROTOCOL,
        "instruments": {
            **PROTOCOL["instruments"],
            "agentCapture": {"contentPolicy": "full"},
        },
        "capture": {"privacy": {"rawCode": True, "agentContentPolicy": "full"}},
    }
    full_text = enrollment.consent_statement(full)
    assert "never records raw code" not in full_text
    assert "Workspace content capture is enabled" in full_text
    assert 'set to "full"' in full_text


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


def test_build_capture_config_leg_summary_reflects_mint_overrides():
    overrides = {
        "toggles": [
            {"instrument": "tern", "path": ["behavior", "enabled"], "value": False},
            {"instrument": "tern", "path": ["ideHealth", "enabled"], "value": False},
            {"instrument": "metrics", "path": ["enabled"], "value": False},
            {"instrument": "metrics", "path": ["snapshot", "enabled"], "value": False},
            {
                "instrument": "agentCapture",
                "path": ["contentPolicy"],
                "value": "metadata-only",
            },
        ]
    }
    cfg = enrollment.build_capture_config(
        ALL_FOUR, "P03", "ai-assisted", overrides=overrides
    )
    by_leg = {entry["leg"]: entry for entry in cfg["legs"]}
    assert by_leg[enrollment.LEG_BEHAVIORAL]["state"] == "disabled"
    assert by_leg[enrollment.LEG_METRICS]["state"] == "disabled"
    assert by_leg[enrollment.LEG_COGNITIVE]["state"] == "enabled"
    assert cfg["settings"]["tern.participantId"] == "P03"
    baseline = enrollment.build_capture_config(ALL_FOUR, "P03", "ai-assisted")
    assert cfg["captureConfigVersion"] != baseline["captureConfigVersion"]
    assert cfg["sessionManifest"]["captureConfigVersion"] == cfg["captureConfigVersion"]
    assert cfg["producers"]["metrics"]["state"] == "disabled"
    assert (
        cfg["sessionManifest"]["privacyPolicy"]["agentContentPolicy"] == "metadata-only"
    )
    assert (
        baseline["sessionManifest"]["privacyPolicy"]["agentContentPolicy"] == "redacted"
    )
    effective = enrollment.apply_capture_overrides(ALL_FOUR, overrides)
    assert 'set to "metadata-only"' in enrollment.consent_statement(effective)
    assert cfg["sessionManifest"]["producers"] == cfg["producers"]
    assert baseline["settings"]["tern.behavior.enabled"] is True
    assert (
        next(
            t
            for t in by_leg[enrollment.LEG_BEHAVIORAL]["toggles"]
            if t["path"] == ["behavior", "enabled"]
        )["currentValue"]
        is False
    )


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
