"""Derive TERN VS Code settings from a study protocol."""

from protocol.errors import ProtocolError

_PREFIX = "tern"

_AGENT_HOOK_EVENTS = ("SessionStart", "PostToolUse", "Stop", "SessionEnd")

# Hooks are fire-and-forget with a short timeout - a down middleware must never stall
# the participant's agent (NFR-1 applies to the agent too).
_AGENT_HOOK_TIMEOUT_S = 10

AGENT_HOOK_ENV_VARS = (
    "STUDY_PARTICIPANT",
    "STUDY_CONDITION",
    "STUDY_SESSION",
    "STUDY_INGEST_ENDPOINT",
)


def _flatten(prefix: str, value: object, out: dict) -> None:
    if isinstance(value, dict):
        for key, sub in value.items():
            _flatten(f"{prefix}.{key}", sub, out)
    else:
        out[prefix] = value


def derive_overlay_settings(
    protocol: dict, participant_id: str, condition: str, task: dict | None = None
) -> dict:
    """Return the flat ``tern.*`` settings for one session."""
    if _PREFIX not in protocol.get("instruments", {}):
        raise ProtocolError(
            "this protocol declares no tern instrument  -  it is an "
            "agent-participant study (FR-PROT-9). Use `derive agent-hooks` for "
            "its harness-oriented config; there is no overlay to derive."
        )
    conditions = protocol["conditions"]
    if condition not in conditions:
        raise ProtocolError(
            f"condition {condition!r} is not declared in the protocol; "
            f"conditions are {', '.join(conditions)}"
        )

    settings: dict = {
        f"{_PREFIX}.participantId": participant_id,
        f"{_PREFIX}.condition": condition,
    }
    # A flat "tern.taskId" here used to look identical at a glance but landed on a
    # different, undeclared VS Code key that nothing ever read - the server picked a
    # task and the setting was sent, but the extension's own environment metadata never
    # saw it.
    if task and task.get("id"):
        settings[f"{_PREFIX}.session.taskId"] = task["id"]
    _flatten(_PREFIX, protocol["instruments"][_PREFIX], settings)

    settings.setdefault(
        f"{_PREFIX}.session.durationMinutes",
        protocol["session"]["durationMinutes"],
    )
    if task and task.get("minutes"):
        settings[f"{_PREFIX}.session.durationMinutes"] = min(
            settings[f"{_PREFIX}.session.durationMinutes"], task["minutes"]
        )
    return settings


def derive_agent_hooks(protocol: dict, *, command: str = "agent-capture-hook") -> dict:
    """
    Return the ``.claude/settings.json`` hooks section for the task workspace, derived
    from the protocol alone (FR-AGENT-2, extends FR-PROT-4's no-side-channel rule).
    """
    instruments = protocol.get("instruments", {})
    agent = instruments.get("agentCapture")
    if agent is None:
        raise ProtocolError(
            "protocol declares no instruments.agentCapture; the agent leg "
            "cannot be derived (add it, or this study runs without it)"
        )
    adapter = agent.get("adapter", "claude-code")
    if adapter != "claude-code":
        raise ProtocolError(
            f"agent adapter {adapter!r} has no hook pack; only 'claude-code' "
            "is supported here (others are behind the FR-AGENT-4 extension "
            "point)"
        )
    policy = agent.get("contentPolicy", "metadata-only")
    hook_command = f"{command} --content-policy {policy}"
    hook_entry = {
        "hooks": [
            {
                "type": "command",
                "command": hook_command,
                "timeout": _AGENT_HOOK_TIMEOUT_S,
            }
        ]
    }
    return {"hooks": {event: [dict(hook_entry)] for event in _AGENT_HOOK_EVENTS}}
