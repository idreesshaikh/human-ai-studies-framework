"""Experimental external-data mining contracts.

The package reads local archive fixtures and is deliberately outside the live
PHOENIX runtime. It is retained as a bounded research artifact, not another
product surface.
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
