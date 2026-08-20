"""Per-host pacing (D8): the Graph API and the Recommendations API are
separate S2 services with their own quotas, so a call to one must not wait
behind unrelated traffic to the other."""

from __future__ import annotations

import pytest

from middleware import semantic_scholar as s2


def test_pace_is_independent_per_host(monkeypatch):
    # A monotonic clock never actually starts at 0.0 (it's process/system
    # uptime), so seed it well clear of `_last_request`'s 0.0 "never called"
    # sentinel — a real first call is always effectively infinitely stale.
    clock = {"t": 100.0}
    slept: list[float] = []

    monkeypatch.setattr(s2.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(s2.time, "sleep", lambda secs: slept.append(secs))
    # Fresh per-test state — module-level dicts persist across tests otherwise.
    monkeypatch.setattr(s2, "_last_request", {})
    monkeypatch.setattr(s2, "_pace_locks", {})

    s2._pace(f"{s2.GRAPH_API}/paper/x")
    assert slept == []  # first call to a host never waits

    s2._pace(f"{s2.REC_API}/papers/forpaper/x")
    assert slept == []  # a different host is not behind the Graph API's clock

    s2._pace(f"{s2.GRAPH_API}/paper/x/citations")
    assert slept == [1.0]  # same host again, no time elapsed -> full wait


def test_pace_advances_independently_per_host(monkeypatch):
    # A monotonic clock never actually starts at 0.0 (it's process/system
    # uptime), so seed it well clear of `_last_request`'s 0.0 "never called"
    # sentinel — a real first call is always effectively infinitely stale.
    clock = {"t": 100.0}
    slept: list[float] = []

    monkeypatch.setattr(s2.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(s2.time, "sleep", lambda secs: slept.append(secs))
    monkeypatch.setattr(s2, "_last_request", {})
    monkeypatch.setattr(s2, "_pace_locks", {})

    s2._pace(f"{s2.GRAPH_API}/paper/x")
    clock["t"] = 101.0
    s2._pace(f"{s2.GRAPH_API}/paper/x/references")  # 1s elapsed, no wait needed
    assert slept == []

    clock["t"] = 101.4
    s2._pace(f"{s2.GRAPH_API}/paper/x/citations")  # only 0.4s elapsed on this host
    assert slept == pytest.approx([0.6])
