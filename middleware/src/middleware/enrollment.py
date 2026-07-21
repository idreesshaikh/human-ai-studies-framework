"""Pure helpers for the live capture link (FR-INST-20/21, FR-ING-7).

No FastAPI/DB state here — the routes in ``app.py`` call these and own the
session. Keeping the token/config/consent logic pure makes it table-testable
(the FR-ETH-4 / authz pattern).
"""

import json
from hashlib import sha256

from protocol.derive import derive_overlay_settings


def connection_string(base_url: str, token: str) -> str:
    """The copy-safe string a participant pastes: ``serverUrl#token``.

    The base URL never contains ``#`` and the token is URL-safe base64, so a
    single ``#`` split reverses this unambiguously on the extension side.
    """
    return f"{base_url.rstrip('/')}#{token}"


def capture_config_version(protocol: dict) -> str:
    """A 12-char content hash of the protocol's instruments block.

    Changes iff the derived capture config changes (wall #5). Stateless, so
    the redeem and capture-config routes compute the same value.
    """
    blob = json.dumps(
        protocol.get("instruments", {}), sort_keys=True, separators=(",", ":")
    )
    return sha256(blob.encode()).hexdigest()[:12]


def build_capture_config(
    protocol: dict, participant_id: str, condition: str, producer: str = "overlay"
) -> dict:
    """The versioned, protocol-derived capture config for one producer.

    ``overlay`` returns the flat ``tern.*`` settings the extension
    applies. Other producers (e.g. ``agent``) can be added behind the same
    envelope later; this phase serves ``overlay``.
    """
    if producer != "overlay":
        raise ValueError(f"unknown capture-config producer {producer!r}")
    settings = derive_overlay_settings(protocol, participant_id, condition)
    return {
        "captureConfigVersion": capture_config_version(protocol),
        "producer": producer,
        "settings": settings,
    }


def enabled_instruments(settings: dict) -> list[dict]:
    """The `{name, enabled}` summary of every sub-instrument this capture
    config declares an explicit on/off switch for (keys ending ``.enabled``
    in the flat ``derive_overlay_settings`` output). Used by the enrollment
    surface's pre-flight visibility (FR-DASH-10) so a researcher can catch a
    forgotten toggle before a session begins, without hand-deriving a second
    summary that could drift from what the IDE actually applies.
    """
    out = []
    for key, value in settings.items():
        if key.endswith(".enabled") and "." in key[: -len(".enabled")]:
            name = key.split(".", 1)[1][: -len(".enabled")]
            out.append({"name": name, "enabled": bool(value)})
    return sorted(out, key=lambda e: e["name"])


#: Plain-language description of each agent content policy (FR-AGENT-5),
#: stated verbatim in the consent statement.
_POLICY_DESCRIPTIONS = {
    "metadata-only": (
        "only sizes, counts, and timings of the conversation — never its text"
    ),
    "redacted": (
        "the conversation text with string literals and long identifiers masked"
    ),
    "full": "the full conversation text",
}


def content_policy(protocol: dict) -> str:
    """The study's agent content policy (default metadata-only, the safest)."""
    agent = protocol.get("instruments", {}).get("agentCapture", {})
    return agent.get("contentPolicy", "metadata-only")


#: Grounding table for togglable metric paths (FR-DASH-11, FR-CONV-2).
#: Maps known instrument+path combinations to corpus refs or marks them
#: unsourced. Only cites sources already in the corpus — never invents one.
_TOGGLE_CATALOG: list[dict] = [
    {
        "instrument": "tern",
        "path": ["stuck", "enabled"],
        "label": "Stuck detection",
        "description": (
            "Detects when a participant dwells on code without editing or "
            "scroll-thrashes, and prompts with an inline reflection question."
        ),
        "grounding": {"ref": "FR-INST-2", "source": "srs"},
    },
    {
        "instrument": "tern",
        "path": ["fatigue", "intervalMinutes"],
        "label": "Fatigue probe cadence",
        "description": (
            "How often the Likert-scale fatigue micro-probes appear during pauses."
        ),
        "grounding": {"ref": "FR-INST-1", "source": "srs"},
    },
    {
        "instrument": "tern",
        "path": ["stuck", "thresholdSeconds"],
        "label": "Stuck detection threshold",
        "description": "Seconds of unedited dwell before the stuck heuristic fires.",
        "grounding": {"ref": "FR-INST-2", "source": "srs"},
    },
    {
        "instrument": "tern",
        "path": ["ideHealth", "enabled"],
        "label": "IDE health stream",
        "description": (
            "Captures aggregate diagnostic counts (errors, warnings) and "
            "build/test invocations — a content-free struggle proxy."
        ),
        "grounding": {"ref": "FR-INST-18", "source": "srs"},
    },
    {
        "instrument": "tern",
        "path": ["ideHealth", "debounceSeconds"],
        "label": "IDE health debounce window",
        "description": (
            "Debounce window in seconds before flushing diagnostic counts "
            "as an event."
        ),
        "grounding": {"unsourced": True},
    },
    {
        "instrument": "agentCapture",
        "path": ["contentPolicy"],
        "label": "Agent conversation content policy",
        "description": (
            "Level of agent-conversation text capture: metadata-only, "
            "redacted, or full."
        ),
        "grounding": {"ref": "FR-AGENT-5", "source": "srs"},
    },
    {
        "instrument": "tern",
        "path": ["session", "durationMinutes"],
        "label": "Session duration",
        "description": (
            "Maximum session length in minutes. Affects scheduling, not "
            "capture scope."
        ),
        "grounding": {"unsourced": True},
    },
]


def toggle_catalog(protocol: dict) -> list[dict]:
    """Return the list of togglable metrics for a protocol's instrument shape.

    Filters ``_TOGGLE_CATALOG`` to only include metrics whose instrument
    exists in the protocol, and resolves the current value from the protocol's
    nested ``instruments`` dict. Never emits a citation absent from the
    corpus/SRS (FR-CONV-2).
    """
    instruments = protocol.get("instruments") or {}
    out = []
    for entry in _TOGGLE_CATALOG:
        instr = entry["instrument"]
        if instr not in instruments:
            continue
        node = instruments[instr]
        if not isinstance(node, dict):
            continue
        current_value = node
        for key in entry["path"]:
            if isinstance(current_value, dict):
                current_value = current_value.get(key)
            else:
                current_value = None
                break
        out.append({
            "instrument": entry["instrument"],
            "path": entry["path"],
            "label": entry["label"],
            "description": entry["description"],
            "grounding": entry["grounding"],
            "currentValue": current_value,
        })
    return out


def consent_statement(protocol: dict, condition: str) -> str:
    """A deterministic, protocol-derived consent paragraph (wall #1, FR-AGENT-5).

    States what the study is, the condition, the active content policy verbatim,
    and the privacy-by-construction promise every instrument keeps.
    """
    title = protocol.get("study", {}).get("title", "this study")
    policy = content_policy(protocol)
    policy_desc = _POLICY_DESCRIPTIONS.get(policy, policy)
    instruments = ", ".join(sorted(protocol.get("instruments", {}).keys())) or "none"
    return (
        f'You are joining "{title}" in the {condition} condition. '
        f"While you work, this study captures aggregate signals from these "
        f"instruments: {instruments}. It never records raw code content, "
        f"keystrokes, or clipboard text — only sizes, shapes, timings, and "
        f'salted hashes. Agent-conversation capture is set to "{policy}": '
        f"{policy_desc}. You appear in all data only as an anonymized ID. "
        f"You can stop the session at any time."
    )
