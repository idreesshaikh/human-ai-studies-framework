"""Counterbalanced assignment: who does which task, under which condition.

The property these tests protect is *balance*, not any particular schedule.
A rotation that looks varied per participant can still leave a task welded to
a condition across the cohort — which is how the first version of this engine
behaved, and it is invisible unless you count the pairings.
"""

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


# ------------------------------------------------------------------ balance


def test_every_condition_meets_every_task_equally_often():
    """The confound this engine exists to prevent.

    Rotating the condition order and the task pairing by the same offset
    keeps them in lockstep: one task ends up permanently attached to one
    condition, and a difference between conditions is then indistinguishable
    from a difference between tasks. Only counting the pairings catches it.
    """
    blocks = [b for seq in _cohort(_protocol(), 4) for b in seq]
    pairings = Counter((b.condition, b.task_id) for b in blocks)
    assert len(pairings) == 4, f"some pairing never happens: {pairings}"
    assert len(set(pairings.values())) == 1, f"unbalanced: {pairings}"


def test_condition_order_is_balanced_across_participants():
    """Whatever comes second gains practice and loses freshness, so each
    condition has to come first equally often."""
    firsts = Counter(seq[0].condition for seq in _cohort(_protocol(), 4))
    assert set(firsts.values()) == {2}, firsts


def test_within_subjects_participants_meet_every_condition():
    """The whole point of within-subjects: each person is their own
    comparison. Enrollment used to hand each participant a single condition
    regardless of the declared design, so nobody ever was."""
    for seq in _cohort(_protocol(), 4):
        assert {b.condition for b in seq} == {"ai-assisted", "unassisted"}


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
    # ...and the cohort is split evenly between them.
    firsts = Counter(seq[0].condition for seq in _cohort(protocol, 4))
    assert set(firsts.values()) == {2}, firsts


# ------------------------------------------------------------- determinism


def test_assignment_is_a_pure_function_of_protocol_and_index():
    """A participant's schedule is reproducible from the protocol alone, so a
    replication can rebuild it without the database that issued it."""
    protocol = _protocol()
    assert assign(protocol, 7) == assign(protocol, 7)


def test_uncounterbalanced_gives_everyone_the_same_order():
    """Not a bug: a researcher who declares counterbalanced=false has chosen
    a fixed order, and the engine records that choice rather than overriding
    it. `assignment_warnings` is where the consequence is stated."""
    protocol = _protocol(
        participants={
            "planned": 12,
            "design": "within-subjects",
            "counterbalanced": False,
        }
    )
    orders = {tuple(b.condition for b in seq) for seq in _cohort(protocol, 4)}
    assert len(orders) == 1


def test_a_negative_participant_index_is_refused():
    with pytest.raises(ProtocolError):
        assign(_protocol(), -1)


def test_a_protocol_with_no_conditions_is_refused():
    with pytest.raises(ProtocolError):
        assign(_protocol(conditions=[]), 0)


# ------------------------------------------------------- tasks and eligibility


def test_a_protocol_without_declared_tasks_still_assigns():
    """Tasks are optional (schema v5). A protocol that only describes its work
    in prose still runs; every session is the one implicit task, so downstream
    code sees one shape either way."""
    protocol = _protocol()
    del protocol["tasks"]
    assert [t["id"] for t in tasks_of(protocol)] == [IMPLICIT_TASK_ID]
    for seq in _cohort(protocol, 2):
        assert {b.task_id for b in seq} == {IMPLICIT_TASK_ID}


def test_the_implicit_task_carries_the_prose_description():
    protocol = _protocol()
    del protocol["tasks"]
    assert tasks_of(protocol)[0]["description"] == "maintenance work"


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


def test_blocks_are_numbered_in_the_order_the_participant_runs_them():
    for seq in _cohort(_protocol(), 3):
        assert [b.index for b in seq] == list(range(len(seq)))


def test_a_block_labels_its_session_readably():
    block = assign(_protocol(), 0)[0]
    assert block.session_label == f"1-{block.task_id}-{block.condition}"


# ---------------------------------------------------------------- warnings


def test_fewer_tasks_than_conditions_is_called_out():
    """Not invalid — a study can be internally consistent and still be
    weakened by a choice that is easy to miss until the data is in."""
    protocol = _protocol(tasks=[{"id": "only", "title": "Only"}])
    assert any("repeat a task" in w for w in assignment_warnings(protocol))


def test_within_subjects_without_counterbalancing_is_called_out():
    protocol = _protocol(
        participants={
            "planned": 12,
            "design": "within-subjects",
            "counterbalanced": False,
        }
    )
    assert any("same order" in w for w in assignment_warnings(protocol))


def test_a_condition_restricted_task_is_called_out_as_partly_confounded():
    protocol = _protocol(
        tasks=[
            {"id": "pair", "title": "Pair", "conditions": ["ai-assisted"]},
            {"id": "solo", "title": "Solo"},
        ]
    )
    assert any("confounded" in w for w in assignment_warnings(protocol))


def test_a_sound_design_warns_about_nothing():
    assert assignment_warnings(_protocol()) == []
