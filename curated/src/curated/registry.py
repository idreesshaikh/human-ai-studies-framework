"""Adapter registry (FR-CUR-1). The job runner names a ``source``, never a
concrete adapter class - new sources register here behind the same contract.
"""

from __future__ import annotations

from collections.abc import Callable

from curated.archive_adapter import ArchiveAdapter
from curated.contract import MiningAdapter

#: source -> factory(...) -> adapter. The archive adapter takes a file path
#: and salt.
ADAPTERS: dict[str, Callable[..., MiningAdapter]] = {
    ArchiveAdapter.source: ArchiveAdapter,
}


def get_adapter(source: str, *args, **kwargs) -> MiningAdapter:
    """Build the adapter for ``source``. Raises ``KeyError`` naming the known
    sources when ``source`` is unregistered."""
    try:
        factory = ADAPTERS[source]
    except KeyError as exc:
        raise KeyError(
            f"no mining adapter for source {source!r}; known: {sorted(ADAPTERS)}"
        ) from exc
    return factory(*args, **kwargs)
