"""Preview and enrollment must use the same deterministic assignment contract."""

import copy

import pytest
import yaml
from middleware.db import (
    Compilation,
    ConversationTurn,
    DesignMoveRow,
    EnrollmentToken,
    ProtocolDraftRow,
    make_session_factory,
)
from middleware.run_plan import describe_run
from protocol.assignment import assign
from sqlalchemy import func, select


@pytest.fixture
def protocol(client_designed):
    return client_designed.get("/studies/pilot/protocol").json()["document"]


@pytest.mark.parametrize("index", [0, 1, 2, 11])
def test_preview_uses_real_assignment(protocol, index):
    plan = describe_run(protocol, index)
    assert [(b["taskId"], b["condition"]) for b in plan["blocks"]] == [
        (b.task_id, b.condition) for b in assign(protocol, index)
    ]
    assert plan["durationMinutes"] == protocol["session"]["durationMinutes"]
    assert plan["privacy"]["clipboardText"] is False
    assert plan["privacy"]["keystrokes"] is False


def test_missing_conditions_are_explicit(protocol):
    protocol["conditions"] = []
    plan = describe_run(protocol, 0)
    assert plan["blocks"] == []
    assert "protocol declares no conditions" in plan["warnings"]


def test_timing_mismatch_is_not_hidden(protocol):
    protocol["session"]["durationMinutes"] = 30
    protocol["instruments"]["tern"]["session"]["durationMinutes"] = 45
    plan = describe_run(protocol, 0)
    assert any("editor timer" in message for message in plan["warnings"])
    assert "not random allocation" in plan["allocationNote"]


def test_external_capture_is_not_claimed_as_automatic(protocol):
    protocol["instruments"]["metrics"] = {"metricSet": "cognitive-load-9"}
    plan = describe_run(protocol, 0)
    assert plan["producers"]["metrics"]["state"] == "external-required"
    assert (
        plan["producers"]["metrics"]["capabilities"]["live_hooks"]["available"] is False
    )


def test_empty_study_explains_setup(client_no_protocol):
    plan = client_no_protocol.get("/studies/empty/run-plan").json()
    assert not plan["hasProtocol"]
    assert not plan["hasPendingChanges"]
    assert "blocks" not in plan


@pytest.mark.parametrize("index", [-1, 10000, "invalid"])
def test_invalid_participant_index_is_rejected(client_designed, index):
    assert (
        client_designed.get(
            f"/studies/pilot/run-plan?participantIndex={index}"
        ).status_code
        == 422
    )


def test_plan_read_creates_no_compilation_or_link(client_designed):
    factory = make_session_factory(client_designed.db_path)

    def counts():
        with factory() as session:
            return tuple(
                session.scalar(select(func.count()).select_from(table))
                for table in (Compilation, EnrollmentToken)
            )

    before = counts()
    plan = client_designed.get("/studies/pilot/run-plan").json()
    assert plan["source"] == "current-protocol"
    assert plan["hasProtocol"] and not plan["hasPendingChanges"]
    assert counts() == before


def test_changed_decision_previews_without_changing_enrollment(client_designed):
    factory = make_session_factory(client_designed.db_path)
    before = client_designed.get("/studies/pilot/protocol").json()["document"]
    with factory() as session:
        last = session.scalar(
            select(ConversationTurn)
            .where(ConversationTurn.study_id == "pilot")
            .order_by(ConversationTurn.seq.desc())
        )
        session.add(
            DesignMoveRow(
                id="new-duration",
                study_id="pilot",
                turn_id=last.id,
                seq=100,
                kind="set-field",
                target="session.durationMinutes",
                proposal="Use 30-minute blocks.",
                patch={
                    "op": "set-field",
                    "path": ["session", "durationMinutes"],
                    "value": 30,
                },
                status="accepted",
                grounding=[],
            )
        )
        session.commit()
    preview = client_designed.get("/studies/pilot/run-plan").json()
    current = client_designed.get("/studies/pilot/run-plan?preview=false").json()
    assert preview["source"] == "accepted-decisions"
    assert preview["durationMinutes"] == 30
    assert current["durationMinutes"] == before["session"]["durationMinutes"]
    assert current["hasPendingChanges"]
    assert client_designed.get("/studies/pilot/protocol").json()["document"] == before
    with factory() as session:
        draft = session.get(ProtocolDraftRow, "pilot")
        assert yaml.safe_load(draft.yaml) == before


def test_task_repeat_warning_is_visible(protocol):
    protocol = copy.deepcopy(protocol)
    protocol["participants"]["design"] = "within-subjects"
    protocol["tasks"] = [{"id": "only", "title": "Only task"}]
    assert any(
        "repeat a task" in warning for warning in describe_run(protocol, 0)["warnings"]
    )
