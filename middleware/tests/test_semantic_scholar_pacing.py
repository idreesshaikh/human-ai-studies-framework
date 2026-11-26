"""The Semantic Scholar client's pacing, retries and budgets, on a stubbed transport.

S2's API tutorial gives a key "a 1 request per second rate across all endpoints",
so the Graph and Recommendations services share one clock.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from middleware import semantic_scholar as s2


class Clock:
    """A fake monotonic clock that sleeping advances."""

    def __init__(self, start: float = 100.0):
        self.t = start
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, secs: float) -> None:
        self.slept.append(round(secs, 6))
        self.t += secs


class Transport:
    """Scripted responses: dicts are JSON bodies, ints are HTTP errors."""

    def __init__(self, clock: Clock, script: list, headers: dict | None = None):
        self.clock = clock
        self.script = list(script)
        self.headers = headers or {}
        self.calls: list[tuple[str, str, float]] = []

    def __call__(self, req, timeout):
        self.calls.append((req.get_method(), req.full_url, timeout))
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        if isinstance(step, int):
            raise urllib.error.HTTPError(
                req.full_url, step, "error", self.headers, io.BytesIO(b"{}")
            )
        return _Response(step)


class _Response:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(s2, "_clock", c.now)
    monkeypatch.setattr(s2, "_sleep", c.sleep)
    monkeypatch.setattr(s2, "_next_slot", 0.0)
    monkeypatch.delenv("MIDDLEWARE_S2_API_KEY", raising=False)
    return c


def _transport(monkeypatch, clock, script, headers=None):
    t = Transport(clock, script, headers)
    monkeypatch.setattr(s2, "_urlopen", t)
    return t


def test_one_clock_paces_every_endpoint(monkeypatch, clock):
    t = _transport(monkeypatch, clock, [{"a": 1}, {"b": 2}, {"c": 3}])
    s2.get_json(f"{s2.GRAPH_API}/paper/x")
    s2.post_json(f"{s2.REC_API}/papers/", {"positivePaperIds": ["x"]})
    clock.t += 0.4
    s2.get_json(f"{s2.GRAPH_API}/paper/y")
    # Second call waits a full second; the third only what is left of its second.
    assert clock.slept == [1.0, 0.6]
    assert [m for m, _, _ in t.calls] == ["GET", "POST", "GET"]


def test_429_is_retried_honouring_retry_after(monkeypatch, clock):
    t = _transport(monkeypatch, clock, [429, {"ok": True}], {"Retry-After": "7"})
    assert s2.get_json(f"{s2.GRAPH_API}/paper/x") == {"ok": True}
    assert 7.0 in clock.slept and len(t.calls) == 2


def test_5xx_and_dropped_connections_back_off_exponentially(monkeypatch, clock):
    script = [503, urllib.error.URLError("reset"), {"ok": True}]
    t = _transport(monkeypatch, clock, script)
    assert s2.get_json(f"{s2.GRAPH_API}/paper/x") == {"ok": True}
    assert len(t.calls) == 3
    assert [d for d in clock.slept if d >= 1.0][:2] == [1.0, 2.0]


def test_client_errors_are_not_retried(monkeypatch, clock):
    t = _transport(monkeypatch, clock, [404])
    with pytest.raises(s2.SemanticScholarError) as err:
        s2.get_json(f"{s2.GRAPH_API}/paper/missing")
    assert err.value.status == 404 and len(t.calls) == 1


def test_retries_give_up_with_the_status(monkeypatch, clock):
    t = _transport(monkeypatch, clock, [429] * (s2.RETRIES + 1))
    with pytest.raises(s2.SemanticScholarError) as err:
        s2.get_json(f"{s2.GRAPH_API}/paper/x")
    assert err.value.status == 429 and len(t.calls) == s2.RETRIES + 1


def test_a_budget_fails_fast_instead_of_retrying_past_it(monkeypatch, clock):
    t = _transport(monkeypatch, clock, [429], {"Retry-After": "30"})
    with s2.budget(2.5), pytest.raises(s2.SemanticScholarError) as err:
        s2.get_json(f"{s2.GRAPH_API}/paper/search?query=x")
    assert err.value.status == 429 and err.value.retry_after == 30.0
    assert len(t.calls) == 1 and all(d < 30 for d in clock.slept)
    assert t.calls[0][2] <= 2.5  # the socket timeout never exceeds the budget


def test_a_budget_refuses_a_slot_it_cannot_reach(monkeypatch, clock):
    t = _transport(monkeypatch, clock, [])
    monkeypatch.setattr(s2, "_next_slot", clock.t + 5.0)  # background traffic queued
    with s2.budget(2.5), pytest.raises(s2.SemanticScholarError):
        s2.get_json(f"{s2.GRAPH_API}/paper/search?query=x")
    assert t.calls == [] and clock.slept == []


def test_the_api_key_header_is_sent_when_set(monkeypatch, clock):
    seen = []

    def opener(req, timeout):
        seen.append(req.get_header("X-api-key"))
        return _Response({})

    monkeypatch.setattr(s2, "_urlopen", opener)
    monkeypatch.setenv("MIDDLEWARE_S2_API_KEY", "k")
    s2.get_json(f"{s2.GRAPH_API}/paper/x")
    assert seen == ["k"]


def test_retry_after_accepts_seconds_and_http_dates():
    assert s2.retry_after_seconds({"Retry-After": "12"}) == 12.0
    assert s2.retry_after_seconds({"Retry-After": "soon"}) is None
    assert s2.retry_after_seconds({}) is None
    past = s2.retry_after_seconds({"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})
    assert past == 0.0


def test_adding_a_paper_while_s2_hangs_fails_within_the_interactive_budget(
    monkeypatch, clock, tmp_path
):
    from fastapi.testclient import TestClient
    from middleware.app import create_app
    from middleware.settings import Settings

    timeouts = []

    def hang(req, timeout):
        timeouts.append(timeout)
        clock.t += timeout  # the socket waits its whole timeout, then gives up
        raise TimeoutError("timed out")

    monkeypatch.setattr(s2, "_urlopen", hang)
    client = TestClient(
        create_app(
            Settings(
                db_path=tmp_path / "hang.sqlite3",
                data_dir=tmp_path / "data",
                spa_dist=tmp_path / "no-dist",
            )
        )
    )
    study = client.post("/projects/implicit/studies", json={"name": "Hang"}).json()
    started = clock.t
    res = client.post(f"/studies/{study['id']}/papers", json={"doi": "10.1/x"})
    assert res.status_code == 502
    # Without the budget: five 20 s timeouts plus 15 s of backoff.
    assert clock.t - started <= s2.INTERACTIVE_BUDGET_S
    assert len(timeouts) < s2.RETRIES + 1
