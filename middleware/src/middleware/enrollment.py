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

    ``overlay`` returns the flat ``cognitiveOverlay.*`` settings the extension
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
