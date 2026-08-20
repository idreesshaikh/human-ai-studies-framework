"""The ethics package: what a committee reads, generated from the protocol."""

from __future__ import annotations

from middleware.enrollment import consent_statement
from middleware.ethics_package import build_ethics_package


def _protocol(**over) -> dict:
    base = {
        "study": {
            "id": "eth-1",
            "title": "Review care under AI",
            "researchers": ["A. Researcher"],
            "ethicsRef": "ETH-2026-9",
        },
        "researchQuestions": [
            {"id": "RQ-1", "text": "Does an AI assistant change review care?"}
        ],
        "conditions": ["ai-assisted", "unassisted"],
        "participants": {
            "planned": 12,
            "design": "within-subjects",
            "counterbalanced": True,
        },
        "session": {"durationMinutes": 45, "taskDescription": "maintenance work"},
        "tasks": [
            {
                "id": "fix-billing-defect",
                "title": "Fix billing defect",
                "description": "Fix a reported defect in the billing module.",
                "minutes": 20,
                "materials": "github.com/acme/core",
            },
            {
                "id": "refactor-parser",
                "title": "Refactor parser",
                "minutes": 20,
            },
        ],
        "instruments": {
            "tern": {
                "session": {"durationMinutes": 45},
                "fatigue": {"intervalMinutes": 15, "waitForPauseSeconds": 4},
                "stuck": {"enabled": True, "thresholdSeconds": 90},
                "output": {"httpEndpoint": "http://127.0.0.1:8000/ingest/events"},
            },
            "agentCapture": {
                "adapter": "claude-code",
                "contentPolicy": "metadata-only",
            },
        },
    }
    base.update(over)
    return base


def test_the_package_is_a_pure_function_of_the_protocol():
    proto = _protocol()
    assert build_ethics_package(proto) == build_ethics_package(proto)


def test_consent_text_is_identical_to_what_the_participant_is_shown():
    """
    The acceptance bar: not paraphrased, not re-derived — the exact sentence a
    participant reads at pairing, quoted verbatim.
    """
    proto = _protocol()
    package = build_ethics_package(proto)
    for condition in proto["conditions"]:
        assert consent_statement(proto, condition) in package


def test_every_declared_instrument_appears_in_the_capture_section():
    """
    1:1 mapping: a leg the protocol enables must be named, and named as active rather
    than merely mentioned.
    """
    package = build_ethics_package(_protocol())
    assert "Cognitive" in package
    assert "Agent interaction" in package
    assert "(active)" in package


def test_a_leg_the_protocol_never_mentions_is_still_shown_as_absent():
    """
    A participant can only check the promise against the whole catalogue, not just the
    parts the researcher happened to configure.
    """
    proto = _protocol()
    del proto["instruments"]["agentCapture"]
    package = build_ethics_package(proto)
    assert "Agent interaction" in package
    assert "not part of this study" in package


def test_every_declared_task_appears_with_its_materials():
    package = build_ethics_package(_protocol())
    assert "Fix billing defect" in package
    assert "github.com/acme/core" in package
    assert "Refactor parser" in package


def test_a_study_without_declared_tasks_still_describes_its_work():
    proto = _protocol()
    del proto["tasks"]
    package = build_ethics_package(proto)
    assert "maintenance work" in package


def test_a_missing_field_is_named_not_papered_over():
    """
    The same honesty the protocol slots use: absent stays absent, and says so in words a
    committee can act on — never a silent gap, never an invented value standing in for
    one.
    """
    proto = _protocol()
    del proto["study"]["ethicsRef"]
    package = build_ethics_package(proto)
    assert "not yet specified: ethics approval reference" in package


def test_the_withdrawal_policy_is_always_present():
    package = build_ethics_package(_protocol())
    assert "## Withdrawal" in package
    assert "stop a session at any time" in package


def test_between_subjects_omits_the_condition_order_line():
    """
    Order only matters when a participant meets more than one condition; asserting a
    counterbalancing claim for a design with none would be a fabricated methodological
    detail.
    """
    proto = _protocol(
        participants={"planned": 12, "design": "between-subjects"}
    )
    package = build_ethics_package(proto)
    assert "Condition order" not in package


def test_the_consent_text_never_carries_a_doubled_full_stop():
    """
    Regression: agent_capture.redact's POLICY_DESCRIPTIONS are already complete
    sentences, and the f-string appended a second period after them - visible as ".." in
    every consent statement and every ethics package generated for an agent-capture
    study, including the one an IRB actually reads.
    """
    from middleware.enrollment import consent_statement

    proto = _protocol()
    for condition in proto["conditions"]:
        assert ".." not in consent_statement(proto, condition)
