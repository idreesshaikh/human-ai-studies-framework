"""Curated-dataset leg (FR-CUR): mine external sources into the same
one-timeline event shape live instruments produce, so every downstream
recipe/report/paper mechanism works on mined data unchanged.

Public surface:

- :mod:`curated.contract` - the normalized-event shape + adapter protocol.
- :mod:`curated.frame` - parse the protocol ``curated:`` section.
- :mod:`curated.registry` - source -> adapter lookup.
- :mod:`curated.github_adapter` - the GitHub adapter.
- :mod:`curated.heuristics` - versioned agent-authorship registry.
- :mod:`curated.threats` - the validity-threats record.
- :mod:`curated.pseudonymize` - salted-hash actor pseudonyms.
- :mod:`curated.cassette` - offline record/replay of API responses.
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
