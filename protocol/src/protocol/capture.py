"""Shared capture manifest and producer capability contract.

The manifest is deliberately small. It carries join keys, public endpoints,
producer state, timing, and privacy policy. It never carries source code,
conversation content, bearer credentials, or provider transcripts.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from protocol.assignment import assign, tasks_of
from protocol.errors import ProtocolError

MANIFEST_VERSION = "1"
PRODUCER_STATES = (
    "enabled",
    "disabled",
    "external-required",
    "unsupported",
    "unavailable",
)

_PRODUCER_SOURCES = {
    "tern": "tern",
    "metrics": "metrics",
    "agent-capture": "agent-capture",
    "workspace-snapshot": "workspace-snapshot",
    "participant-git": "participant-git",
    "task-harness": "task-harness",
    "agent-derived": "agent-derived",
}

def new_session_id() -> str:
    """Create a non-secret, facilitator-friendly session identifier."""
    return f"s-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"


def capture_config_version(protocol: dict) -> str:
    """Hash all capture-relevant protocol configuration, not participant data."""
    import json

    capture = {
        "instruments": protocol.get("instruments", {}),
        "capture": protocol.get("capture", {}),
        "protocolVersion": protocol.get("protocolVersion"),
    }
    blob = json.dumps(capture, sort_keys=True, separators=(",", ":"))
    return sha256(blob.encode()).hexdigest()[:12]


def _status(state: str, reason: str, *, configured: bool = True) -> dict:
    if state not in PRODUCER_STATES:
        raise ValueError(f"unknown producer state {state!r}")
    return {
        "state": state,
        "configured": configured,
        "reason": reason,
    }


def _capability(state: str, reason: str) -> dict:
    return {
        "state": state,
        "available": state in {"enabled", "external-required"},
        "reason": reason,
    }


def _configured_state(config: Any, executor: str) -> str:
    if not isinstance(config, dict):
        return "unavailable"
    if config.get("enabled") is False:
        return "disabled"
    return "enabled" if executor == "tern" else "external-required"


def privacy_policy(protocol: dict) -> dict:
    """Return the effective privacy policy with safe defaults."""
    capture = protocol.get("capture") or {}
    configured = capture.get("privacy") if isinstance(capture, dict) else {}
    configured = configured if isinstance(configured, dict) else {}
    agent = (protocol.get("instruments") or {}).get("agentCapture") or {}
    policy = configured.get("agentContentPolicy") or agent.get(
        "contentPolicy", "metadata-only"
    )
    if policy not in {"metadata-only", "redacted", "full"}:
        policy = "metadata-only"
    return {
        "agentContentPolicy": policy,
        "rawCode": bool(configured.get("rawCode", False)),
        "clipboardText": False,
        "keystrokes": False,
        "conversationContent": policy != "metadata-only",
        "note": (
            "Metadata-only by default. Raw code or conversation content is only "
            "captured when the protocol and consent explicitly enable it."
        ),
    }


def producer_capabilities(protocol: dict) -> dict[str, dict]:
    """Describe every producer and capability without claiming unverified work."""
    instruments = protocol.get("instruments") or {}
    capture = protocol.get("capture") or {}
    metrics = instruments.get("metrics", capture.get("metrics"))
    agent = instruments.get("agentCapture")
    harness = instruments.get("taskHarness", capture.get("taskHarness"))
    tern = instruments.get("tern")

    producers: dict[str, dict] = {}
    tern_state = _configured_state(tern, "tern")
    producers["tern"] = {
        "source": "tern",
        **_status(
            tern_state,
            "TERN applies this configuration in the editor",
            configured=tern is not None,
        ),
        "executor": "TERN extension",
        "capabilities": {
            "cognitive": _capability(
                tern_state, "experience sampling and stuck probes"
            ),
            "editor_lifecycle": _capability(
                tern_state, "editor telemetry and inline AI lifecycle"
            ),
        },
    }

    metrics_state = _configured_state(metrics, "external")
    producers["metrics"] = {
        "source": "metrics",
        **_status(
            metrics_state,
            "run by an external metrics command against the assigned workspace",
            configured=metrics is not None,
        ),
        "executor": "metrics runner",
        "cadence": (metrics or {}).get("cadence", "end-of-session")
        if isinstance(metrics, dict)
        else "end-of-session",
        "metricSet": (metrics or {}).get("metricSet", "cognitive-load-9")
        if isinstance(metrics, dict)
        else "cognitive-load-9",
        "capabilities": {
            "post_session_import": _capability(
                metrics_state, "end-of-session metric upload"
            ),
            "live_hooks": _capability(
                "unsupported", "metrics are not executed by TERN"
            ),
        },
    }

    if isinstance(agent, dict):
        adapter = agent.get("adapter", "claude-code")
        if adapter == "claude-code":
            agent_state = (
                "external-required" if agent.get("enabled", True) else "disabled"
            )
            transcript = _capability(
                agent_state, "Claude Code hooks plus transcript import backstop"
            )
            tool_calls = _capability(
                agent_state, "Claude Code tool event normalization"
            )
            reason = "Claude Code adapter has supported live hooks"
        elif adapter == "generic-json":
            agent_state = (
                "external-required" if agent.get("enabled", True) else "disabled"
            )
            transcript = _capability(
                agent_state, "researcher-supplied JSON transcript import"
            )
            tool_calls = _capability(
                agent_state, "tool calls present in the supplied transcript"
            )
            reason = "generic import requires a valid researcher-supplied transcript"
        else:
            agent_state = "unsupported"
            transcript = _capability(
                "unsupported", "no supported public transcript or tool interface"
            )
            tool_calls = _capability(
                "unsupported", "no supported public transcript or tool interface"
            )
            reason = (
                f"{adapter} has editor-level fallback only; "
                "agent-transcript-unavailable"
            )
        producers["agent-capture"] = {
            "source": "agent-capture",
            **_status(agent_state, reason),
            "executor": f"agent-capture adapter: {adapter}",
            "adapter": adapter,
            "capabilities": {
                "transcript": transcript,
                "tool_calls": tool_calls,
                "model_metadata": _capability(
                    agent_state, "provider metadata when present"
                ),
                "live_hooks": _capability(
                    agent_state, "provider hook or import interface"
                ),
                "post_session_import": _capability(agent_state, "transcript backstop"),
                "editor_lifecycle": _capability(
                    "unsupported", "editor lifecycle belongs to TERN"
                ),
            },
        }
    else:
        producers["agent-capture"] = {
            "source": "agent-capture",
            **_status(
                "unavailable", "no agent provider was selected", configured=False
            ),
            "executor": "external adapter",
            "capabilities": {
                key: _capability("unavailable", "no provider selected")
                for key in (
                    "transcript",
                    "tool_calls",
                    "model_metadata",
                    "live_hooks",
                    "post_session_import",
                    "editor_lifecycle",
                )
            },
        }

    harness_state = _configured_state(harness, "external")
    producers["task-harness"] = {
        "source": "task-harness",
        **_status(
            harness_state,
                "run by an external harness command against task tests",
            configured=harness is not None,
        ),
        "executor": "task harness",
        "capabilities": {
            "post_session_import": _capability(harness_state, "task outcome event")
        },
    }

    snapshot = (
        capture.get("snapshots") if isinstance(capture, dict) else None
    ) or instruments.get("snapshots")
    snapshot_state = _configured_state(snapshot, "external")
    producers["workspace-snapshot"] = {
        "source": "workspace-snapshot",
        **_status(
            snapshot_state,
            "optional snapshot runner; stores code only when explicitly enabled",
            configured=snapshot is not None,
        ),
        "executor": "agent-capture snapshot",
        "capabilities": {
            "post_session_import": _capability(
                snapshot_state, "workspace snapshot events"
            )
        },
    }

    vcs = (
        capture.get("vcs") if isinstance(capture, dict) else None
    ) or instruments.get("vcs")
    vcs_state = _configured_state(vcs, "external")
    producers["participant-git"] = {
        "source": "participant-git",
        **_status(
            vcs_state, "optional commit-summary observer", configured=vcs is not None
        ),
        "executor": "agent-capture snapshot",
        "capabilities": {
            "post_session_import": _capability(
                vcs_state, "commit summaries without messages"
            )
        },
    }
    agent_state = (producers["agent-capture"] or {}).get("state")
    derived_state = (
        "external-required"
        if agent_state in {"enabled", "external-required"}
        else agent_state or "unavailable"
    )
    producers["agent-derived"] = {
        "source": "agent-derived",
        **_status(
            derived_state,
            "cross-leg correlation runs after supported agent streams arrive"
            if derived_state == "external-required"
            else "no supported agent stream is available for correlation",
            configured=isinstance(agent, dict),
        ),
        "executor": "agent-capture correlate",
        "capabilities": {
            "post_session_import": _capability(
                derived_state,
                "derived reliance loops and edit annotations",
            )
        },
    }
    return producers


def required_producers(
    protocol: dict, producers: dict[str, dict] | None = None
) -> list[str]:
    """Resolve required streams from explicit protocol configuration."""
    capture = protocol.get("capture") or {}
    explicit = capture.get("requiredProducers") if isinstance(capture, dict) else None
    if isinstance(explicit, list):
        return [str(p) for p in explicit if str(p) in _PRODUCER_SOURCES]
    producers = producers or producer_capabilities(protocol)
    # TERN is the live participant boundary when it is configured. All other
    # producers remain optional until the researcher marks them required.
    required = ["tern"] if producers["tern"]["configured"] else []
    instruments = protocol.get("instruments") or {}
    for producer, config_key in (
        ("metrics", "metrics"),
        ("agent-capture", "agentCapture"),
        ("task-harness", "taskHarness"),
    ):
        config = instruments.get(config_key)
        if isinstance(config, dict) and config.get("required") is True:
            required.append(producer)
    return required


def session_manifest(
    protocol: dict,
    *,
    study_id: str | None = None,
    participant_id: str,
    condition: str,
    session_id: str | None = None,
    task: dict | None = None,
    task_id: str | None = None,
    endpoints: dict[str, str] | None = None,
    prepared_at: str | None = None,
) -> dict:
    """Derive one versioned, privacy-safe manifest for a participant session."""
    if condition not in protocol.get("conditions", []):
        raise ProtocolError(f"condition {condition!r} is not declared in the protocol")
    participant_index = 0
    raw_number = "".join(c for c in participant_id if c.isdigit())
    if raw_number:
        participant_index = max(0, int(raw_number) - 1)
    blocks = assign(protocol, participant_index)
    chosen = None
    if task_id:
        chosen = next(
            (b for b in blocks if b.task_id == task_id and b.condition == condition),
            None,
        )
        if chosen is None:
            raise ProtocolError(
                f"task {task_id!r} is not assigned to participant {participant_id!r} "
                f"under condition {condition!r}"
            )
    if chosen is None:
        chosen = next(
            (b for b in blocks if b.condition == condition),
            blocks[0] if blocks else None,
        )
    if task is None and chosen is not None:
        task = next(
            (t for t in tasks_of(protocol) if t.get("id") == chosen.task_id), None
        )
    task = task or {}
    task_id = task.get("id") or (chosen.task_id if chosen else "")
    producers = producer_capabilities(protocol)
    required = required_producers(protocol, producers)
    optional = [
        name
        for name in producers
        if name not in required and producers[name]["configured"]
    ]
    endpoints = endpoints or {}
    manifest = {
        "manifestVersion": MANIFEST_VERSION,
        "studyId": study_id or protocol.get("study", {}).get("id", ""),
        "protocolVersion": protocol.get("protocolVersion"),
        "participantId": participant_id,
        "condition": condition,
        "taskId": task_id,
        "sessionId": session_id or new_session_id(),
        "captureConfigVersion": capture_config_version(protocol),
        "endpoints": {
            "events": endpoints.get("events", ""),
            "metrics": endpoints.get("metrics", ""),
        },
        "producers": producers,
        "privacyPolicy": privacy_policy(protocol),
        "requiredProducers": required,
        "optionalProducers": optional,
        "timing": {
            "durationMinutes": protocol.get("session", {}).get("durationMinutes", 0),
            "taskMinutes": task.get("minutes"),
            "preparedAt": prepared_at
            or datetime.now(UTC).isoformat(timespec="milliseconds"),
        },
    }
    if chosen is not None:
        manifest["assignment"] = {
            "index": chosen.index,
            "of": len(blocks),
            "taskId": chosen.task_id,
            "condition": chosen.condition,
        }
    return manifest


def validate_manifest(
    manifest: dict,
    protocol: dict | None = None,
    *,
    study_id: str | None = None,
) -> list[str]:
    """Return all manifest contract errors without inspecting any content."""
    errors: list[str] = []
    required = (
        "manifestVersion",
        "studyId",
        "protocolVersion",
        "participantId",
        "condition",
        "taskId",
        "sessionId",
        "captureConfigVersion",
        "endpoints",
        "producers",
        "privacyPolicy",
        "requiredProducers",
        "optionalProducers",
        "timing",
    )
    for key in required:
        if key not in manifest:
            errors.append(f"missing {key}")
    if manifest.get("manifestVersion") != MANIFEST_VERSION:
        errors.append(f"manifestVersion must be {MANIFEST_VERSION}")
    if protocol:
        expected_study_id = study_id or protocol.get("study", {}).get("id")
        if manifest.get("studyId") != expected_study_id:
            errors.append("studyId does not match protocol")
        if manifest.get("protocolVersion") != protocol.get("protocolVersion"):
            errors.append("protocolVersion does not match protocol")
        if manifest.get("condition") not in protocol.get("conditions", []):
            errors.append("condition is not declared by the protocol")
        if manifest.get("captureConfigVersion") != capture_config_version(protocol):
            errors.append("captureConfigVersion does not match protocol")
    if manifest.get("sessionId") == "":
        errors.append("sessionId must not be empty")
    producers = (
        manifest.get("producers") if isinstance(manifest.get("producers"), dict) else {}
    )
    for producer in (
        manifest.get("requiredProducers", [])
        if isinstance(manifest.get("requiredProducers"), list)
        else []
    ):
        state = (producers.get(producer) or {}).get("state")
        if state in {"unavailable", "unsupported", "disabled"}:
            errors.append(f"required producer {producer!r} is {state}")
    forbidden = {
        "rawCode",
        "sourceCode",
        "conversation",
        "transcript",
        "secret",
        "token",
        "clipboardText",
    }

    def walk(value: Any, path: str = "manifest") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                metadata_key = path == "manifest.privacyPolicy" and key in {
                    "rawCode",
                    "clipboardText",
                }
                metadata_key = metadata_key or (
                    path.startswith("manifest.producers.") and key == "transcript"
                )
                if key in forbidden and not metadata_key:
                    errors.append(f"{path}.{key} is not allowed in a session manifest")
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")

    walk(manifest)
    return errors
