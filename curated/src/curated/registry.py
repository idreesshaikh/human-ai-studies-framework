"""Adapter registry (FR-CUR-1). The job runner names a ``source``, never a
concrete adapter class - new sources register here behind the same contract.
"""

from __future__ import annotations

from collections.abc import Callable

from curated.contract import MiningAdapter
from curated.github_adapter import GitHubAdapter

#: source -> factory(...) -> adapter. The GitHub adapter needs a fetcher
#: (cassette or live); the archive adapter takes a file path and salt.
ADAPTERS: dict[str, Callable[..., MiningAdapter]] = {
    GitHubAdapter.source: GitHubAdapter,
}
try:
    from curated.archive_adapter import ArchiveAdapter

    ADAPTERS[ArchiveAdapter.source] = ArchiveAdapter
except ImportError:
    pass  # archive adapter optional; degrade gracefully


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
