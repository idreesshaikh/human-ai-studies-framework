"""Parse and validate the protocol's ``curated:`` section into a
:class:`SamplingFrame` (FR-CUR-1/2).

The protocol YAML gains a ``curated:`` section (schema addition, additive =>
``protocolVersion`` bump). This module turns that section into the typed
frame the adapter consumes, and raises a plain-language error when the frame
is missing or malformed - the adapter refuses to run without a frame (F2.2),
and this is where that refusal is decided.
"""

from __future__ import annotations

from curated.contract import SamplingFrame

CONTENT_POLICIES = frozenset({"metadata-only", "redacted", "full"})
ACTOR_UNITS = frozenset({"developer", "repo", "agent"})


class FrameError(ValueError):
    """A missing or malformed sampling frame."""


def frame_from_protocol(protocol: dict) -> SamplingFrame:
    """Extract the sampling frame from a loaded protocol dict.

    Raises :class:`FrameError` (plain language) when ``curated:`` is absent
    or incomplete - the mined equivalent of running without an approved
    protocol.
    """
    curated = protocol.get("curated")
    if not isinstance(curated, dict):
        raise FrameError(
            "this study has no `curated:` section, so there is no sampling "
            "frame to mine against. Declare the frame in the protocol first "
            "(query, window, actor unit) — mining never improvises its scope."
        )
    frame = curated.get("samplingFrame")
    if not isinstance(frame, dict):
        raise FrameError(
            "the `curated:` section is missing its `samplingFrame` (query, "
            "window, inclusion rules, target n)."
        )

    query = str(frame.get("query", "")).strip()
    if not query:
        raise FrameError("the sampling frame needs a non-empty `query`.")
    window = frame.get("window") or {}
    start = str(window.get("start", "")).strip()
    end = str(window.get("end", "")).strip()
    if not start or not end:
        raise FrameError(
            "the sampling frame needs a `window` with `start` and `end` "
            "dates — an open-ended mine is not a reproducible frame."
        )

    actor_unit = str(curated.get("actorUnit", "developer")).strip()
    if actor_unit not in ACTOR_UNITS:
        raise FrameError(
            f"actorUnit {actor_unit!r} is not one of {sorted(ACTOR_UNITS)}."
        )
    policy = str(curated.get("contentPolicy", "metadata-only")).strip()
    if policy not in CONTENT_POLICIES:
        raise FrameError(
            f"contentPolicy {policy!r} is not one of {sorted(CONTENT_POLICIES)}."
        )

    conditions = [str(c) for c in (curated.get("conditions") or [])]
    if not conditions:
        # Fall back to the study's declared conditions so a frame need not
        # restate them; the adapter still needs at least one arm to label.
        conditions = [
            str(c.get("name", c)) if isinstance(c, dict) else str(c)
            for c in (protocol.get("conditions") or [])
        ]

    return SamplingFrame(
        query=query,
        window_start=start,
        window_end=end,
        inclusion_rules=[str(r) for r in (frame.get("inclusionRules") or [])],
        exclusions=[str(r) for r in (frame.get("exclusions") or [])],
        target_n=int(frame.get("targetN", 0) or 0),
        actor_unit=actor_unit,
        conditions=conditions,
        content_policy=policy,
    )
