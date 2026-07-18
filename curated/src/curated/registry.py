"""Adapter registry (FR-CUR-1). The job runner names a ``source``, never a
concrete adapter class - new sources register here behind the same contract.
"""

from __future__ import annotations

from collections.abc import Callable

from curated.contract import MiningAdapter
from curated.github_adapter import GitHubAdapter

#: source -> factory(fetcher, salt) -> adapter. The GitHub adapter needs a
#: fetcher (cassette or live); other sources register the same way.
ADAPTERS: dict[str, Callable[..., MiningAdapter]] = {
    GitHubAdapter.source: GitHubAdapter,
}


def get_adapter(source: str, *args, **kwargs) -> MiningAdapter:
    """Build the adapter for ``source``. Raises ``KeyError`` naming the known
    sources when ``source`` is unregistered."""
    try:
        factory = ADAPTERS[source]
    except KeyError as exc:
        raise KeyError(
            f"no mining adapter for source {source!r}; "
            f"known: {sorted(ADAPTERS)}"
        ) from exc
    return factory(*args, **kwargs)
