"""Read-only participant journey, derived from the real assignment contract."""

from protocol.assignment import assign, assignment_warnings, tasks_of
from protocol.capture import privacy_policy, producer_capabilities, required_producers
from protocol.errors import ProtocolError


def describe_run(protocol: dict, participant_index: int) -> dict:
    tasks = {task["id"]: task for task in tasks_of(protocol)}
    producers = producer_capabilities(protocol)
    warnings = assignment_warnings(protocol)
    session = protocol.get("session", {})
    tern = protocol.get("instruments", {}).get("tern", {})
    timer = tern.get("session", {}).get("durationMinutes")
    if timer is not None and timer != session.get("durationMinutes"):
        warnings.append(
            f"The study plans {session.get('durationMinutes')} minutes per block, "
            f"but the editor timer is configured for {timer}. Align them in Setup."
        )
    try:
        blocks = [
            {
                "index": block.index,
                "taskId": block.task_id,
                "title": tasks[block.task_id].get("title", block.task_id),
                "description": tasks[block.task_id].get("description", ""),
                "condition": block.condition,
            }
            for block in assign(protocol, participant_index)
        ]
    except ProtocolError as error:
        blocks = []
        warnings.append(str(error))
    return {
        "participants": protocol.get("participants", {}),
        "allocationNote": (
            "Assignments are deterministic by enrollment order. "
            "Counterbalancing is not random allocation; a randomized trial "
            "needs a separately documented allocation procedure."
        ),
        "conditions": protocol.get("conditions", []),
        "durationMinutes": session.get("durationMinutes"),
        "fatigueIntervalMinutes": tern.get("fatigue", {}).get("intervalMinutes"),
        "blocks": blocks,
        "producers": producers,
        "requiredProducers": required_producers(protocol, producers),
        "privacy": privacy_policy(protocol),
        "warnings": warnings,
    }
