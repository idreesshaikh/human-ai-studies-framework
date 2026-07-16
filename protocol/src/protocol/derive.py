"""Derive Cognitive Overlay VS Code settings from a study protocol.

Proves the protocol drives the instruments: the flat ``cognitiveOverlay.*``
settings a facilitator pastes into VS Code come from the protocol alone -
no side-channel configuration.
"""

from protocol.errors import ProtocolError

_PREFIX = "cognitiveOverlay"

#: Claude Code hook events the agent leg listens on, and why (D13/FR-AGENT-2):
#: SessionStart/Stop/SessionEnd trigger a re-normalize-and-POST of the
#: transcript-so-far (liveness); PostToolUse gives real-time tool ticks. Every
#: trigger runs the same idempotent hook command, so the scheme is
#: self-healing (see agent_capture.hook).
_AGENT_HOOK_EVENTS = ("SessionStart", "PostToolUse", "Stop", "SessionEnd")

#: Hooks are fire-and-forget with a short timeout - a down middleware must
#: never stall the participant's agent (NFR-1 applies to the agent too).
_AGENT_HOOK_TIMEOUT_S = 10

#: Join keys + endpoint the facilitator runbook exports so the hook command
#: inherits them; the *content policy* is baked into the command from the
#: protocol, so there is no hand-maintained side configuration (FR-PROT-4).
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
    protocol: dict, participant_id: str, condition: str
) -> dict:
    """Return the flat ``cognitiveOverlay.*`` settings for one session.

    Everything is derived from the protocol: the instrument config under
    ``instruments.cognitiveOverlay`` plus the given participant and
    condition (the join keys every event carries). Raises
    :class:`ProtocolError` if ``condition`` is not one of the protocol's
    conditions.
    """
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
    _flatten(_PREFIX, protocol["instruments"][_PREFIX], settings)

    # The session plan is authoritative for duration if the instrument
    # config omitted it.
    settings.setdefault(
        f"{_PREFIX}.session.durationMinutes",
        protocol["session"]["durationMinutes"],
    )
    return settings


def derive_agent_hooks(
    protocol: dict, *, command: str = "agent-capture-hook"
) -> dict:
    """Return the ``.claude/settings.json`` hooks section for the task
    workspace, derived from the protocol alone (FR-AGENT-2, extends
    FR-PROT-4's no-side-channel rule).

    The agent content policy (``instruments.agentCapture.contentPolicy``) is
    baked into the hook command so capture matches consent by construction
    (FR-AGENT-5); the join keys come from the runbook's environment. Raises
    :class:`ProtocolError` if the protocol declares no ``agentCapture``
    instrument or a non-``claude-code`` adapter (the only adapter with
    lossless machine-readable capture, D13; others live behind FR-AGENT-4).
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
