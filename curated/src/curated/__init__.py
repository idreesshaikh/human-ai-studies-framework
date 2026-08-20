"""
Curated-dataset leg (FR-CUR): mine external sources into the same one-timeline event
shape live instruments produce, so every downstream recipe/report/paper mechanism works
on mined data unchanged.
"""

from curated.contract import (
    CURATED_EVENT_TYPES,
    CURATED_SCHEMA_VERSION,
    CoverageEstimate,
    Cursor,
    CursorCheckpoint,
    MiningAdapter,
    NormalizedEvent,
    SamplingFrame,
)

__all__ = [
    "CURATED_EVENT_TYPES",
    "CURATED_SCHEMA_VERSION",
    "CoverageEstimate",
    "Cursor",
    "CursorCheckpoint",
    "MiningAdapter",
    "NormalizedEvent",
    "SamplingFrame",
]
