"""Settings.port precedence: MIDDLEWARE_PORT > PORT > 8000.

Railway dynamically assigns PORT per-service and routes/healthchecks
against it; the app must bind there or every external probe reads
"service unavailable" even though the app is healthy internally on 8000.
Local/self-hosted use never sets PORT, so the FR-ING-1 default (every
instrument leg's 127.0.0.1:8000 endpoint) must stay unaffected.
"""

from middleware.settings import Settings


def test_defaults_to_8000_when_nothing_is_set(monkeypatch):
    monkeypatch.delenv("MIDDLEWARE_PORT", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert Settings().port == 8000


def test_uses_railway_port_when_set(monkeypatch):
    monkeypatch.delenv("MIDDLEWARE_PORT", raising=False)
    monkeypatch.setenv("PORT", "4123")
    assert Settings().port == 4123


def test_middleware_port_overrides_railway_port(monkeypatch):
    monkeypatch.setenv("MIDDLEWARE_PORT", "9001")
    monkeypatch.setenv("PORT", "4123")
    assert Settings().port == 9001
