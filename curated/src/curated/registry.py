"""Adapter registry (FR-CUR-1)."""

from __future__ import annotations

from collections.abc import Callable

from curated.archive_adapter import ArchiveAdapter
from curated.contract import MiningAdapter

ADAPTERS: dict[str, Callable[..., MiningAdapter]] = {
    ArchiveAdapter.source: ArchiveAdapter,
}


def get_adapter(source: str, *args, **kwargs) -> MiningAdapter:
    """Build the adapter for ``source``."""
    try:
        factory = ADAPTERS[source]
    except KeyError as exc:
        raise KeyError(
            f"no mining adapter for source {source!r}; known: {sorted(ADAPTERS)}"
        ) from exc
    return factory(*args, **kwargs)
