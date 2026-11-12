from analysis.recipes.control_arm_audit import audit_sessions, calibration_report


def event(kind, seq, payload=None, session="real", condition="control"):
    return {
        "sessionId": session,
        "participantId": "P1",
        "condition": condition,
        "type": kind,
        "seq": seq,
        "source": "tern",
        "payload": payload or {},
    }


def complete(session="real"):
    return [
        event("session_start", 0, session=session),
        event(
            "environment_snapshot",
            1,
            {
                "auditCapture": {
                    "aiLifecycle": True,
                    "editBursts": True,
                    "clipboard": True,
                }
            },
            session=session,
        ),
        event("session_end", 2, session=session),
    ]


def test_missing_capture_abstains_and_paste_does_not_prove_ai():
    rows = [event("clipboard_paste", 0, {"chars": 400})]
    result = audit_sessions(rows, ["control"])
    assert result["sessions"][0]["status"] == "cannot-assess"
    assert result["sessions"][0]["counts"]["clipboard_paste"] == 1
    assert "never proof" in result["blindSpots"][-1]


def test_complete_capture_without_ai_reports_no_evidence_not_no_ai():
    result = audit_sessions(
        complete(), ["control"], {"real": {"decision": "include", "reason": "Reviewed"}}
    )
    assert result["sessions"][0]["status"] == "no-evidence"
    assert result["sessions"][0]["decision"]["decision"] == "include"
    assert "Not measured" in result["accuracy"]


def test_direct_positive_signals_and_heuristics_are_not_conflated():
    for kind, payload in [
        ("ai_suggestion", {"action": "accepted"}),
        ("agent_turn", {}),
        ("tool_call", {}),
    ]:
        result = audit_sessions([event(kind, 0, payload)], ["control"])
        assert result["sessions"][0]["status"] == "evidence-of-ai-use"
    heuristic = audit_sessions([event("edit_burst", 0, {"origin": "ai"})], ["control"])[
        "sessions"
    ][0]
    assert heuristic["counts"]["possible_bulk_edit"] == 1
    assert heuristic["status"] == "cannot-assess"
    assert not audit_sessions(
        [event("agent_turn", 0, {"synthetic": True})], ["control"]
    )["sessions"]
    assert not audit_sessions(
        [event("agent_turn", 0, condition="treatment")], ["control"]
    )["sessions"]


def test_sequence_gaps_abstain_and_independent_calibration_reports_intervals():
    rows = [
        *complete("negative"),
        event("ai_suggestion", 0, {"action": "accepted"}, session="positive"),
        event("session_end", 2, session="unknown"),
    ]
    result = audit_sessions(rows, ["control"])
    report = calibration_report(
        result, {"negative": False, "positive": True, "unknown": False}
    )
    assert report["abstained"] == 1
    assert report["signals"]["combined"]["sensitivity"]["value"] == 1
    assert report["signals"]["combined"]["specificity"]["value"] == 1
    assert report["signals"]["combined"]["specificity"]["ci"][0] < 1


def accepted(session, seq):
    return event("ai_suggestion", seq, {"action": "accepted"}, session=session)


def test_calibration_by_scenario_reports_fired_rate():
    rows = [*complete("hit"), accepted("hit", 3), *complete("miss")]
    scenarios = {"hit": "copilot-inline", "miss": "copilot-inline"}
    result = audit_sessions(rows, ["control"])
    report = calibration_report(result, {"hit": True, "miss": True}, scenarios)
    scenario = report["byScenario"]["copilot-inline"]
    signals = scenario["signals"]["accepted_inline_suggestion"]
    assert (scenario["labelled"], scenario["assessed"], scenario["abstained"]) == (
        2,
        2,
        0,
    )
    assert scenario["incompleteCaptureExcluded"] == 0
    assert signals["fired"]["value"] == 0.5
    assert signals["fired"]["n"] == 2
    assert signals["sensitivity"]["value"] == 0.5
    assert signals["specificity"] == {"value": None, "ci": None, "n": 0}
    assert "byScenario" not in calibration_report(result, {"hit": True, "miss": True})


def test_calibration_scenario_with_only_abstentions_is_null():
    result = audit_sessions([event("clipboard_paste", 0, session="gap")], ["control"])
    report = calibration_report(result, {"gap": True}, {"gap": "retype"})
    scenario = report["byScenario"]["retype"]
    assert (scenario["labelled"], scenario["assessed"], scenario["abstained"]) == (
        1,
        0,
        1,
    )
    assert scenario["incompleteCaptureExcluded"] == 1
    for signal in scenario["signals"].values():
        for rate in signal.values():
            assert rate == {"value": None, "ci": None, "n": 0}


def test_calibration_incomplete_capture_abstains_never_counts_as_negative():
    rows = [
        *complete("clean"),
        *complete("no-end")[:2],
        event("session_start", 0, session="gap"),
        event("session_end", 2, session="gap"),
    ]
    labels = {"clean": False, "no-end": False, "gap": False}
    result = audit_sessions(rows, ["control"])
    report = calibration_report(result, labels, dict.fromkeys(labels, "retype"))
    scenario = report["byScenario"]["retype"]
    assert (scenario["assessed"], scenario["abstained"]) == (1, 2)
    assert scenario["signals"]["combined"]["specificity"]["n"] == 1
    assert report["abstained"] == 2
    assert report["incompleteCaptureExcluded"] == 2
    assert scenario["incompleteCaptureExcluded"] == 2


def test_incomplete_positive_counts_for_combined_but_not_per_signal_rates():
    rows = [
        *complete("clean"),
        *complete("full"),
        accepted("full", 3),
        event("agent_turn", 0, session="partial"),
    ]
    labels = {"clean": False, "full": True, "partial": True}
    result = audit_sessions(rows, ["control"])
    assert result["sessions"][1]["status"] == "evidence-of-ai-use"
    report = calibration_report(result, labels, dict.fromkeys(labels, "mixed"))
    scenario = report["byScenario"]["mixed"]
    for scope in (report, scenario):
        assert (scope["labelled"], scope["assessed"], scope["abstained"]) == (3, 3, 0)
        assert scope["incompleteCaptureExcluded"] == 1
        combined = scope["signals"]["combined"]
        assert combined["sensitivity"]["value"] == 1
        assert combined["sensitivity"]["n"] == 2
        assert combined["specificity"]["n"] == 1
        # The partial session's capture may have missed these channels, so it
        # supplies neither a hit nor a miss to them.
        agent = scope["signals"]["agent_turn"]
        assert agent["sensitivity"]["value"] == 0
        assert agent["sensitivity"]["n"] == 1
        assert agent["specificity"]["n"] == 1
        inline = scope["signals"]["accepted_inline_suggestion"]
        assert inline["sensitivity"]["value"] == 1
        assert inline["sensitivity"]["n"] == 1
    agent_fired = scenario["signals"]["agent_turn"]["fired"]
    assert (agent_fired["value"], agent_fired["n"]) == (0, 2)
    combined_fired = scenario["signals"]["combined"]["fired"]
    assert combined_fired["n"] == 3
    assert combined_fired["value"] == 2 / 3
