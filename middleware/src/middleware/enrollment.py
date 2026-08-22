"""Pure helpers for the live capture link (FR-INST-20/21, FR-ING-7)."""

import json
from hashlib import sha256

from agent_capture.redact import POLICY_DESCRIPTIONS as _POLICY_DESCRIPTIONS
from protocol.derive import derive_overlay_settings


def connection_string(base_url: str, token: str) -> str:
    """The copy-safe string a participant pastes: ``serverUrl#token``."""
    return f"{base_url.rstrip('/')}#{token}"


def capture_config_version(protocol: dict) -> str:
    """A 12-char content hash of the protocol's instruments block."""
    blob = json.dumps(
        protocol.get("instruments", {}), sort_keys=True, separators=(",", ":")
    )
    return sha256(blob.encode()).hexdigest()[:12]


def build_capture_config(
    protocol: dict,
    participant_id: str,
    condition: str,
    producer: str = "overlay",
    task: dict | None = None,
    block: dict | None = None,
    overrides: dict | None = None,
) -> dict:
    """The versioned, protocol-derived capture config for one producer."""
    if producer != "overlay":
        raise ValueError(f"unknown capture-config producer {producer!r}")
    settings = derive_overlay_settings(protocol, participant_id, condition, task)
    if overrides:
        settings = apply_capture_overrides(settings, overrides)
    config = {
        "captureConfigVersion": capture_config_version(protocol),
        "producer": producer,
        "settings": settings,
        "legs": leg_summary(protocol),
    }
    if block is not None:
        config["block"] = block
    return config


def apply_capture_overrides(settings: dict, overrides: dict) -> dict:
    """
    Layer mint-time toggle overrides on top of the derived ``tern.*`` settings.

    ``overrides`` is ``{"toggles": [{"instrument", "path", "value"}, ...]}``  -  the same
    ``{instrument, path, value}`` triples ``TogglePopover`` sends. Each triple addresses
    one flat setting key ``{instrument}.{path[0]}.{path[1]}...``, so ``tern`` overrides
    land exactly where ``derive_overlay_settings`` put them. Condition assignment stays
    untouched: overrides only tune what an already-assigned condition captures.
    """
    if not overrides:
        return settings
    out = dict(settings)
    for toggle in overrides.get("toggles") or []:
        instrument = toggle.get("instrument")
        path = toggle.get("path")
        if not instrument or not isinstance(path, list) or not path:
            continue
        key = f"{instrument}.{'.'.join(str(p) for p in path)}"
        out[key] = toggle.get("value")
    return out


def clean_capture_overrides(overrides: dict | None) -> dict | None:
    """
    Reduce a client-supplied overrides blob to the well-formed toggles only, so a stray
    key or a non-list path can never be persisted and later read back as a toggle.
    Returns ``None`` for an empty or malformed override set.
    """
    if not isinstance(overrides, dict):
        return None
    toggles = []
    for entry in overrides.get("toggles") or []:
        if not isinstance(entry, dict):
            continue
        instrument = entry.get("instrument")
        path = entry.get("path")
        if (
            isinstance(instrument, str)
            and instrument
            and isinstance(path, list)
            and path
            and all(isinstance(p, str) and p for p in path)
            and "value" in entry
        ):
            toggles.append(
                {"instrument": instrument, "path": list(path), "value": entry["value"]}
            )
    return {"toggles": toggles} if toggles else None


def enabled_instruments(settings: dict) -> list[dict]:
    """
    The `{name, enabled}` summary of every sub-instrument this capture config declares
    an explicit on/off switch for (keys ending ``.enabled`` in the flat
    ``derive_overlay_settings`` output).
    """
    out = []
    for key, value in settings.items():
        if key.endswith(".enabled") and "." in key[: -len(".enabled")]:
            name = key.split(".", 1)[1][: -len(".enabled")]
            out.append({"name": name, "enabled": bool(value)})
    return sorted(out, key=lambda e: e["name"])


def content_policy(protocol: dict) -> str:
    """The study's agent content policy (default metadata-only, the safest)."""
    agent = protocol.get("instruments", {}).get("agentCapture", {})
    return agent.get("contentPolicy", "metadata-only")


LEG_METRICS = "metrics"
LEG_BEHAVIORAL = "behavioral"
LEG_COGNITIVE = "cognitive"
LEG_AGENT = "agent"

# Only cites sources already in the corpus  -  never invents one.
_TOGGLE_CATALOG: list[dict] = [
    {
        "instrument": "tern",
        "leg": LEG_COGNITIVE,
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
        "leg": LEG_COGNITIVE,
        "path": ["fatigue", "intervalMinutes"],
        "label": "Fatigue probe cadence",
        "description": (
            "How often the Likert-scale fatigue micro-probes appear during pauses."
        ),
        "grounding": {"ref": "FR-INST-1", "source": "srs"},
    },
    {
        "instrument": "tern",
        "leg": LEG_COGNITIVE,
        "path": ["stuck", "thresholdSeconds"],
        "label": "Stuck detection threshold",
        "description": "Seconds of unedited dwell before the stuck heuristic fires.",
        "grounding": {"ref": "FR-INST-2", "source": "srs"},
    },
    {
        "instrument": "tern",
        "leg": LEG_BEHAVIORAL,
        "path": ["ideHealth", "enabled"],
        "label": "IDE health stream",
        "description": (
            "Captures aggregate diagnostic counts (errors, warnings) and "
            "build/test invocations  -  a content-free struggle proxy."
        ),
        "grounding": {"ref": "FR-INST-18", "source": "srs"},
    },
    {
        "instrument": "tern",
        "leg": LEG_BEHAVIORAL,
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
        "leg": LEG_AGENT,
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
        "leg": LEG_COGNITIVE,
        "path": ["session", "durationMinutes"],
        "label": "Session duration",
        "description": (
            "Maximum session length in minutes. Affects scheduling, not "
            "capture scope."
        ),
        "grounding": {"unsourced": True},
    },
    {
        "instrument": "tern",
        "leg": LEG_BEHAVIORAL,
        "path": ["behavior", "enabled"],
        "label": "Behavioral telemetry",
        "description": (
            "Records what you did, never what you wrote: file focus switches, "
            "edit bursts as sizes and timings, saves, and scroll position."
        ),
        "grounding": {"ref": "FR-INST-5", "source": "srs"},
    },
    {
        "instrument": "tern",
        "leg": LEG_BEHAVIORAL,
        "path": ["behavior", "captureAiLifecycle"],
        "label": "AI completion lifecycle",
        "description": (
            "Records when a suggestion appears and whether it was accepted, "
            "rejected, or dismissed, with the review latency before the choice."
        ),
        "grounding": {"ref": "FR-INST-8", "source": "srs"},
    },
    {
        "instrument": "tern",
        "leg": LEG_BEHAVIORAL,
        "path": ["behavior", "captureVisibleRanges"],
        "label": "Scroll coverage",
        "description": (
            "Records which line ranges were on screen, so analysis can tell "
            "read code from unread code. Line numbers only, never their text."
        ),
        "grounding": {"ref": "FR-INST-9", "source": "srs"},
    },
    {
        "instrument": "tern",
        "leg": LEG_BEHAVIORAL,
        "path": ["behavior", "captureClipboard"],
        "label": "Paste shapes",
        "description": (
            "Records the size and timing of pastes so agent-origin code can be "
            "attributed. Clipboard text is never read or stored."
        ),
        "grounding": {"ref": "FR-INST-10", "source": "srs"},
    },
    {
        "instrument": "metrics",
        "leg": LEG_METRICS,
        "path": ["enabled"],
        "label": "Static code metrics",
        "description": (
            "Computes the nine complexity and readability measures over your "
            "workspace. Produces numbers about the code, not copies of it."
        ),
        "grounding": {"ref": "FR-INST-4", "source": "srs"},
    },
    {
        "instrument": "metrics",
        "leg": LEG_METRICS,
        "path": ["snapshot", "enabled"],
        "label": "Workspace snapshots",
        "description": (
            "Keeps a private snapshot history of the task workspace so the "
            "metrics can be computed over time rather than only at the end. "
            "This stores your code, and is governed by the study's consent."
        ),
        "grounding": {"ref": "FR-INST-15", "source": "srs"},
    },
    {
        "instrument": "metrics",
        "leg": LEG_METRICS,
        "path": ["snapshot", "intervalMinutes"],
        "label": "Snapshot interval",
        "description": (
            "Minutes between workspace snapshots, in addition to a snapshot "
            "on every save."
        ),
        "grounding": {"unsourced": True},
    },
    {
        "instrument": "metrics",
        "leg": LEG_METRICS,
        "path": ["sonar", "enabled"],
        "label": "Cognitive complexity (SonarQube)",
        "description": (
            "Adds the SonarQube cognitive-complexity measure. Needs a reachable "
            "SonarQube instance; the other eight metrics run without it."
        ),
        "grounding": {"ref": "FR-INST-4", "source": "srs"},
    },
    {
        "instrument": "metrics",
        "leg": LEG_METRICS,
        "path": ["captureVcsActivity"],
        "label": "Commit activity",
        "description": (
            "Records your commits in the task repo as counts and timings  -  "
            "files changed, insertions, deletions. Never the message text."
        ),
        "grounding": {"ref": "FR-INST-17", "source": "srs"},
    },
    {
        "instrument": "agentCapture",
        "leg": LEG_AGENT,
        "path": ["enabled"],
        "label": "Agent interaction capture",
        "description": (
            "Records your coding-agent turns on the shared timeline: prompts "
            "and responses as counts, sizes, and timings."
        ),
        "grounding": {"ref": "FR-AGENT-1", "source": "srs"},
    },
    {
        "instrument": "agentCapture",
        "leg": LEG_AGENT,
        "path": ["correlateWithEditor"],
        "label": "Agent-to-edit correlation",
        "description": (
            "Links an agent code block to the matching paste that follows it, "
            "so code can be attributed to the agent or to you."
        ),
        "grounding": {"ref": "FR-AGENT-3", "source": "srs"},
    },
    {
        "instrument": "agentCapture",
        "leg": LEG_AGENT,
        "path": ["captureWorkspaceSnapshots"],
        "label": "Agent workspace snapshots",
        "description": (
            "Snapshots the workspace around agent turns. Like the metrics "
            "leg's snapshots, this stores code and is consent-governed."
        ),
        "grounding": {"ref": "FR-ETH-2", "source": "srs"},
    },
]


def toggle_catalog(protocol: dict) -> list[dict]:
    """Return the list of togglable metrics for a protocol's instrument shape."""
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
            "leg": entry["leg"],
            "path": entry["path"],
            "label": entry["label"],
            "description": entry["description"],
            "grounding": entry["grounding"],
            "currentValue": current_value,
        })
    return out


# Written once here so the extension never grows a second, divergent account of what a
# leg does.
_LEG_SUMMARIES = {
    LEG_METRICS: (
        "Static metrics",
        "Measures the shape of the code you produce.",
    ),
    LEG_BEHAVIORAL: (
        "Behavioral",
        "Records what you did in the editor  -  never what you wrote.",
    ),
    LEG_COGNITIVE: (
        "Cognitive",
        "Asks how you're finding the work, in short probes timed into pauses.",
    ),
    LEG_AGENT: (
        "Agent interaction",
        "Records your coding-agent turns on the same timeline.",
    ),
}

LEG_ORDER = (LEG_METRICS, LEG_BEHAVIORAL, LEG_COGNITIVE, LEG_AGENT)


def leg_summary(protocol: dict) -> list[dict]:
    """All four legs with their state under this protocol (FR-INST-22)."""
    entries = toggle_catalog(protocol)
    out = []
    for leg in LEG_ORDER:
        label, description = _LEG_SUMMARIES[leg]
        toggles = [e for e in entries if e["leg"] == leg]
        if not toggles:
            state = "unavailable"
        else:
            switches = [
                t["currentValue"] for t in toggles if t["path"][-1] == "enabled"
            ]
            state = "disabled" if switches and not any(switches) else "enabled"
        out.append({
            "leg": leg,
            "label": label,
            "description": description,
            "state": state,
            "toggles": toggles,
        })
    return out


def consent_statement(protocol: dict, condition: str) -> str:
    """A deterministic, protocol-derived consent paragraph (wall #1, FR-AGENT-5)."""
    title = protocol.get("study", {}).get("title", "this study")
    policy = content_policy(protocol)
    policy_desc = _POLICY_DESCRIPTIONS.get(policy, policy).rstrip(".")
    instruments = ", ".join(sorted(protocol.get("instruments", {}).keys())) or "none"
    return (
        f'You are joining "{title}" in the {condition} condition. '
        f"While you work, this study captures aggregate signals from these "
        f"instruments: {instruments}. It never records raw code content, "
        f"keystrokes, or clipboard text  -  only sizes, shapes, timings, and "
        f'salted hashes. Agent-conversation capture is set to "{policy}": '
        f"{policy_desc}. You appear in all data only as an anonymized ID. "
        f"You can stop the session at any time."
    )
