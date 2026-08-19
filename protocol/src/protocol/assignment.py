"""Who does which task, under which condition, in what order.

The protocol has always declared ``participants.design`` and
``participants.counterbalanced``, and nothing ever read them. Enrollment
handed each participant a single condition round-robin — a *between-subjects*
assignment — no matter what the protocol said. For a within-subjects study,
which is what most of the registry's templates prescribe and what small-N
developer research almost always wants, that silently produced the wrong
study: each participant met one condition, so nobody was ever their own
comparison and the paired statistics the template prescribed had no pairs to
work on.

This module is the missing half. It turns a protocol into a concrete,
per-participant sequence of **blocks** — one block being "this task, under
this condition" — and it is a pure function of the protocol plus the
participant's index, so the same study always assigns the same way and a
replication can reproduce an individual participant's schedule exactly.

Two things get counterbalanced, and they are separate problems:

1. **Condition order.** In a within-subjects study everyone meets every
   condition, so the order they meet them in is a confound: whatever comes
   second benefits from practice and suffers from fatigue. Rotating the order
   across participants balances that out.

2. **Which task goes with which condition.** If everyone does the same task
   under the AI condition, task difficulty is perfectly confounded with the
   condition and no amount of condition counterbalancing rescues it. Rotating
   the task-to-condition pairing across participants is what separates them.

A study can also declare fewer tasks than it has conditions. Then a
within-subjects participant must repeat a task, and the second encounter is
contaminated by the first. That is a real design flaw rather than an edge
case to paper over, so :func:`assignment_warnings` names it.
"""

from __future__ import annotations

from dataclasses import dataclass

from protocol.errors import ProtocolError

#: The id used when a protocol declares no ``tasks``. A study still has work in
#: it — ``session.taskDescription`` — it just hasn't been broken into
#: addressable units, so every session is the same single block and its events
#: are all attributed here.
IMPLICIT_TASK_ID = "task"


@dataclass(frozen=True)
class Block:
    """One session's worth of work: a task, under a condition.

    ``index`` is the position in this participant's own sequence, so block 0
    is the first session they run. The extension pairs per session, so one
    block is exactly what one paired session carries.
    """

    index: int
    task_id: str
    condition: str

    @property
    def session_label(self) -> str:
        """How a participant's session is named in the data."""
        return f"{self.index + 1}-{self.task_id}-{self.condition}"


def tasks_of(protocol: dict) -> list[dict]:
    """The protocol's declared tasks, or the single implicit one.

    Keeping the implicit case here means every caller downstream — the
    capture config, the extension, the event stamp — sees the same shape
    whether or not the researcher broke the work into units.
    """
    declared = protocol.get("tasks") or []
    if declared:
        return list(declared)
    session = protocol.get("session") or {}
    return [
        {
            "id": IMPLICIT_TASK_ID,
            "title": "The study task",
            "description": session.get("taskDescription", ""),
        }
    ]


def _eligible(task: dict, condition: str) -> bool:
    """Whether a task may run under a condition. A task that names no
    conditions runs under all of them, which is the usual and safer case."""
    allowed = task.get("conditions")
    return not allowed or condition in allowed


def assign(protocol: dict, participant_index: int) -> list[Block]:
    """The ordered blocks for one participant, 0-based index.

    Pure and deterministic: the same protocol and index always give the same
    sequence, so a participant's schedule is reproducible from the protocol
    alone rather than recoverable only from the database that issued it.
    """
    if participant_index < 0:
        raise ProtocolError("participant_index must be 0 or greater")
    conditions = list(protocol.get("conditions") or [])
    if not conditions:
        raise ProtocolError("protocol declares no conditions")
    tasks = tasks_of(protocol)
    participants = protocol.get("participants") or {}
    within = participants.get("design") == "within-subjects"
    # Counterbalancing is what rotation is *for*; without it every participant
    # gets the identical order, which is a defensible choice only when the
    # researcher made it deliberately.
    rotate = participant_index if participants.get("counterbalanced") else 0

    if not within:
        # Between-subjects: one condition for the whole participant. They
        # still work through every eligible task, rotated so task order is
        # not itself a constant.
        condition = conditions[participant_index % len(conditions)]
        eligible = [t for t in tasks if _eligible(t, condition)] or tasks
        ordered = _rotated(eligible, rotate)
        return [
            Block(i, task["id"], condition) for i, task in enumerate(ordered)
        ]

    # Within-subjects: every condition, in a rotated order, each paired with a
    # different task.
    #
    # The two rotations must be independent. Keying the task off the
    # condition's *position in the rotated order* looks like it varies per
    # participant and does not: the order and the pairing rotate in lockstep,
    # so one task ends up permanently attached to one condition — precisely
    # the confound this is here to prevent. Keying it off the condition's own
    # index in the declared list decouples them, and every condition then
    # meets every task equally often.
    ordered_conditions = _rotated(conditions, rotate)
    blocks: list[Block] = []
    for position, condition in enumerate(ordered_conditions):
        eligible = [t for t in tasks if _eligible(t, condition)] or tasks
        identity = conditions.index(condition)
        task = eligible[(participant_index + identity) % len(eligible)]
        blocks.append(Block(position, task["id"], condition))
    return blocks


def _rotated(items: list, by: int) -> list:
    """``items`` rotated left by ``by`` — the Latin-square row for this
    participant. A plain rotation, not a shuffle: it is reproducible, it
    balances exactly when participants are a multiple of the row count, and
    it degrades predictably when they are not."""
    if not items:
        return []
    offset = by % len(items)
    return items[offset:] + items[:offset]


def assignment_warnings(protocol: dict) -> list[str]:
    """Design problems the assignment can't fix, stated plainly.

    These are not validation errors — each describes a study that is
    internally consistent and still weaker than the researcher probably
    intends, which is exactly the kind of thing that is easy to discover
    only after the data is collected.
    """
    warnings: list[str] = []
    conditions = list(protocol.get("conditions") or [])
    tasks = protocol.get("tasks") or []
    participants = protocol.get("participants") or {}
    within = participants.get("design") == "within-subjects"

    if within and tasks and len(tasks) < len(conditions):
        warnings.append(
            f"{len(tasks)} task(s) across {len(conditions)} conditions in a "
            "within-subjects design: participants must repeat a task, and the "
            "second time they meet it they already know it. Declare one task "
            "per condition to keep the comparison clean."
        )
    if within and not tasks:
        warnings.append(
            "A within-subjects design with no declared tasks means every "
            "participant does the same single task under every condition, so "
            "practice effects sit directly on the comparison. Declaring one "
            "task per condition separates them."
        )
    if within and not participants.get("counterbalanced"):
        warnings.append(
            "Within-subjects without counterbalancing: every participant "
            "meets the conditions in the same order, so practice and fatigue "
            "load onto whichever condition comes last."
        )
    for task in tasks:
        allowed = task.get("conditions")
        if allowed and len(allowed) < len(conditions):
            warnings.append(
                f"Task {task.get('id')!r} runs only under "
                f"{', '.join(allowed)}: task and condition are partly "
                "confounded, so a difference between conditions could be a "
                "difference between tasks."
            )
    return warnings
