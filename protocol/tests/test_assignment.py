"""Counterbalanced assignment: who does which task, under which condition."""

from __future__ import annotations

from collections import Counter

import pytest
from protocol.assignment import (
    IMPLICIT_TASK_ID,
    assign,
    assignment_warnings,
    tasks_of,
)
from protocol.errors import ProtocolError


def _protocol(**over) -> dict:
    base = {
        "conditions": ["ai-assisted", "unassisted"],
        "participants": {
            "planned": 12,
            "design": "within-subjects",
            "counterbalanced": True,
        },
        "tasks": [
            {"id": "refactor", "title": "Refactor"},
            {"id": "bugfix", "title": "Fix a bug"},
        ],
        "session": {"durationMinutes": 45, "taskDescription": "maintenance work"},
    }
    base.update(over)
    return base


def _cohort(protocol: dict, n: int) -> list[list]:
    return [assign(protocol, i) for i in range(n)]


def test_within_subject_schedule_balances_tasks_and_condition_order():
    """The confound this engine exists to prevent."""
    protocol = _protocol()
    cohort = _cohort(protocol, 4)
    blocks = [b for seq in cohort for b in seq]
    pairings = Counter((b.condition, b.task_id) for b in blocks)
    assert len(pairings) == 4, f"some pairing never happens: {pairings}"
    assert len(set(pairings.values())) == 1, f"unbalanced: {pairings}"
    assert Counter(seq[0].condition for seq in cohort) == {
        "ai-assisted": 2,
        "unassisted": 2,
    }
    for index, seq in enumerate(cohort):
        assert {block.condition for block in seq} == {"ai-assisted", "unassisted"}
        assert [block.index for block in seq] == [0, 1]
        assert assign(protocol, index) == seq
    assert assignment_warnings(protocol) == []


def test_between_subjects_participants_meet_exactly_one_condition():
    protocol = _protocol(
        participants={
            "planned": 12,
            "design": "between-subjects",
            "counterbalanced": True,
        }
    )
    for seq in _cohort(protocol, 4):
        assert len({b.condition for b in seq}) == 1
    firsts = Counter(seq[0].condition for seq in _cohort(protocol, 4))
    assert set(firsts.values()) == {2}, firsts


def test_uncounterbalanced_gives_everyone_the_same_order():
    """
    Not a bug: a researcher who declares counterbalanced=false has chosen a fixed order,
    and the engine records that choice rather than overriding it.
    """
    protocol = _protocol(
        participants={
            "planned": 12,
            "design": "within-subjects",
            "counterbalanced": False,
        }
    )
    orders = {tuple(b.condition for b in seq) for seq in _cohort(protocol, 4)}
    assert len(orders) == 1
    assert any("same order" in warning for warning in assignment_warnings(protocol))


def test_a_negative_participant_index_is_refused():
    with pytest.raises(ProtocolError):
        assign(_protocol(), -1)


def test_a_protocol_with_no_conditions_is_refused():
    with pytest.raises(ProtocolError):
        assign(_protocol(conditions=[]), 0)


def test_a_protocol_without_declared_tasks_still_assigns():
    """Tasks are optional (schema v5)."""
    protocol = _protocol()
    del protocol["tasks"]
    assert [t["id"] for t in tasks_of(protocol)] == [IMPLICIT_TASK_ID]
    assert tasks_of(protocol)[0]["description"] == "maintenance work"
    for seq in _cohort(protocol, 2):
        assert {b.task_id for b in seq} == {IMPLICIT_TASK_ID}


def test_a_task_restricted_to_one_condition_is_never_assigned_elsewhere():
    protocol = _protocol(
        tasks=[
            {"id": "pair", "title": "Pair", "conditions": ["ai-assisted"]},
            {"id": "solo", "title": "Solo"},
        ]
    )
    for seq in _cohort(protocol, 4):
        for block in seq:
            if block.task_id == "pair":
                assert block.condition == "ai-assisted"


def test_fewer_tasks_than_conditions_is_called_out():
    """
    Not invalid  -  a study can be internally consistent and still be weakened by a
    choice that is easy to miss until the data is in.
    """
    protocol = _protocol(tasks=[{"id": "only", "title": "Only"}])
    assert any("repeat a task" in w for w in assignment_warnings(protocol))


def test_a_condition_restricted_task_is_called_out_as_partly_confounded():
    protocol = _protocol(
        tasks=[
            {"id": "pair", "title": "Pair", "conditions": ["ai-assisted"]},
            {"id": "solo", "title": "Solo"},
        ]
    )
    assert any("confounded" in w for w in assignment_warnings(protocol))
