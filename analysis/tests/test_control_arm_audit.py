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


def test_positive_signals_survive_missing_coverage_and_synthetic_rows_are_ignored():
    for kind, payload in [
        ("ai_suggestion", {}),
        ("agent_turn", {}),
        ("tool_call", {}),
        ("edit_burst", {"origin": "ai"}),
    ]:
        result = audit_sessions([event(kind, 0, payload)], ["control"])
        assert result["sessions"][0]["status"] == "evidence-of-ai-use"
    assert not audit_sessions(
        [event("agent_turn", 0, {"synthetic": True})], ["control"]
    )["sessions"]
    assert not audit_sessions(
        [event("agent_turn", 0, condition="treatment")], ["control"]
    )["sessions"]


def test_sequence_gaps_abstain_and_independent_calibration_reports_intervals():
    rows = [
        *complete("negative"),
        event("ai_suggestion", 0, session="positive"),
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
