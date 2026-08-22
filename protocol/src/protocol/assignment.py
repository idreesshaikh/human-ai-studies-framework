"""Who does which task, under which condition, in what order."""

from __future__ import annotations

from dataclasses import dataclass

from protocol.errors import ProtocolError

IMPLICIT_TASK_ID = "task"


@dataclass(frozen=True)
class Block:
    """One session's worth of work: a task, under a condition."""

    index: int
    task_id: str
    condition: str

    @property
    def session_label(self) -> str:
        """How a participant's session is named in the data."""
        return f"{self.index + 1}-{self.task_id}-{self.condition}"


def tasks_of(protocol: dict) -> list[dict]:
    """The protocol's declared tasks, or the single implicit one."""
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
    """Whether a task may run under a condition."""
    allowed = task.get("conditions")
    return not allowed or condition in allowed


def assign(protocol: dict, participant_index: int) -> list[Block]:
    """The ordered blocks for one participant, 0-based index."""
    if participant_index < 0:
        raise ProtocolError("participant_index must be 0 or greater")
    conditions = list(protocol.get("conditions") or [])
    if not conditions:
        raise ProtocolError("protocol declares no conditions")
    tasks = tasks_of(protocol)
    participants = protocol.get("participants") or {}
    within = participants.get("design") == "within-subjects"
    # Counterbalancing is what rotation is *for*; without it every participant gets the
    # identical order, which is a defensible choice only when the researcher made it
    # deliberately.
    rotate = participant_index if participants.get("counterbalanced") else 0

    if not within:
        condition = conditions[participant_index % len(conditions)]
        eligible = [t for t in tasks if _eligible(t, condition)] or tasks
        ordered = _rotated(eligible, rotate)
        return [
            Block(i, task["id"], condition) for i, task in enumerate(ordered)
        ]

    # The two rotations must be independent.
    ordered_conditions = _rotated(conditions, rotate)
    blocks: list[Block] = []
    for position, condition in enumerate(ordered_conditions):
        eligible = [t for t in tasks if _eligible(t, condition)] or tasks
        identity = conditions.index(condition)
        task = eligible[(participant_index + identity) % len(eligible)]
        blocks.append(Block(position, task["id"], condition))
    return blocks


def _rotated(items: list, by: int) -> list:
    """``items`` rotated left by ``by``  -  the Latin-square row for this participant."""
    if not items:
        return []
    offset = by % len(items)
    return items[offset:] + items[:offset]


def assignment_warnings(protocol: dict) -> list[str]:
    """Design problems the assignment can't fix, stated plainly."""
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
