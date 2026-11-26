"""Refresh scheduling configuration and app lifespan."""

from threading import Event

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

from middleware import corpus_refresh


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("6", 6.0),
        ("abc", None),
        ("0", None),
        ("nan", None),
        ("0.01", 1.0),  # a refresh at most hourly, whatever is configured
    ],
)
def test_scheduler_configuration(tmp_path, monkeypatch, caplog, value, expected):
    calls = []
    monkeypatch.setattr(
        corpus_refresh, "start_scheduler", lambda **kw: calls.append(kw) or (None, None)
    )
    if value is None:
        monkeypatch.delenv("MIDDLEWARE_REFRESH_INTERVAL_H", raising=False)
    else:
        monkeypatch.setenv("MIDDLEWARE_REFRESH_INTERVAL_H", value)
    settings = Settings(
        db_path=tmp_path / "scheduler.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
    )
    with TestClient(create_app(settings)):
        pass
    assert [call["interval_hours"] for call in calls] == (
        [expected] if expected else []
    )
    if value is not None and expected in (None, 1.0):
        assert "MIDDLEWARE_REFRESH_INTERVAL_H" in caplog.text


def test_scheduled_refresh_does_not_curate_existing_papers(tmp_path, monkeypatch):
    calls = []
    refreshed = []
    monkeypatch.setenv("MIDDLEWARE_REFRESH_INTERVAL_H", "6")
    monkeypatch.setattr(
        corpus_refresh, "start_scheduler", lambda **kw: calls.append(kw) or (None, None)
    )
    monkeypatch.setattr(
        corpus_refresh, "run_once", lambda *args, **kw: refreshed.append(True)
    )
    settings = Settings(
        db_path=tmp_path / "scheduler.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
    )
    with TestClient(create_app(settings)):
        calls[0]["run"]()
    assert refreshed == [True]


@pytest.mark.parametrize(
    "value,expected",
    [(None, 24.0), ("", 24.0), ("12", 12.0), ("off", None), ("0", None)],
)
def test_a_bootstrapping_server_refreshes_daily_unless_turned_off(
    tmp_path, monkeypatch, value, expected
):
    from middleware import corpus_importer

    calls = []
    monkeypatch.setattr(
        corpus_refresh, "start_scheduler", lambda **kw: calls.append(kw) or (None, None)
    )
    monkeypatch.setattr(
        corpus_importer, "start_background_import", lambda *a, **k: None
    )
    monkeypatch.setenv("MIDDLEWARE_CORPUS_BOOTSTRAP", "1")
    if value is None:
        monkeypatch.delenv("MIDDLEWARE_REFRESH_INTERVAL_H", raising=False)
    else:
        monkeypatch.setenv("MIDDLEWARE_REFRESH_INTERVAL_H", value)
    settings = Settings(
        db_path=tmp_path / "scheduler.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
    )
    with TestClient(create_app(settings)):
        pass
    assert [c["interval_hours"] for c in calls] == ([expected] if expected else [])
    if calls:
        # The cadence is read from the run history, so a restart does not refresh.
        assert calls[0]["due_in"]() == 0.0  # no run recorded yet: due now


def test_the_scheduled_job_screens_new_candidates(tmp_path, monkeypatch):
    from middleware import corpus_screen

    calls, jobs = [], []
    monkeypatch.setenv("MIDDLEWARE_REFRESH_INTERVAL_H", "6")
    monkeypatch.setattr(
        corpus_refresh, "start_scheduler", lambda **kw: calls.append(kw) or (None, None)
    )
    monkeypatch.setattr(
        corpus_screen, "scheduled_refresh", lambda *a, **kw: jobs.append(kw) or {}
    )
    settings = Settings(
        db_path=tmp_path / "scheduler.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
    )
    with TestClient(create_app(settings)):
        calls[0]["run"]()
    assert jobs == [{"config_path": None}]


def test_scheduler_runs_only_during_its_own_app_lifespan(tmp_path, monkeypatch):
    stops = []

    def start_scheduler(**_kwargs):
        stop = Event()
        stops.append(stop)
        return None, stop

    monkeypatch.setattr(corpus_refresh, "start_scheduler", start_scheduler)
    monkeypatch.setenv("MIDDLEWARE_CORPUS_BOOTSTRAP", "0")

    def app(name):
        return create_app(
            Settings(
                db_path=tmp_path / f"{name}.sqlite3",
                data_dir=tmp_path / name,
                spa_dist=tmp_path / "no-dist",
            )
        )

    monkeypatch.setenv("MIDDLEWARE_REFRESH_INTERVAL_H", "6")
    enabled_app = app("enabled")
    monkeypatch.setenv("MIDDLEWARE_REFRESH_INTERVAL_H", "off")
    disabled_app = app("disabled")
    assert stops == []

    with TestClient(enabled_app) as enabled, TestClient(disabled_app) as disabled:
        (stop,) = stops
        assert not stop.is_set()
        assert enabled.get("/corpus/status").json()["scheduler"]["intervalHours"] == 6
        assert disabled.get("/corpus/status").json()["scheduler"]["enabled"] is False
    assert stop.is_set()


def test_the_first_refresh_waits_for_the_bootstrap_import(tmp_path, monkeypatch):
    from middleware import corpus_importer

    calls = []
    monkeypatch.setattr(
        corpus_refresh, "start_scheduler", lambda **kw: calls.append(kw) or (None, None)
    )
    monkeypatch.setattr(
        corpus_importer, "start_background_import", lambda *a, **k: None
    )
    monkeypatch.setenv("MIDDLEWARE_CORPUS_BOOTSTRAP", "1")
    monkeypatch.delenv("MIDDLEWARE_REFRESH_INTERVAL_H", raising=False)
    settings = Settings(
        db_path=tmp_path / "scheduler.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
    )
    with TestClient(create_app(settings)):
        due_in = calls[0]["due_in"]
        # Until the shipped corpus has landed, a refresh would take its papers
        # for new ones; the scheduler checks again shortly instead of running.
        monkeypatch.setitem(corpus_importer._BOOTSTRAP_STATE, "state", "loading")
        assert due_in() > 0
        monkeypatch.setitem(corpus_importer._BOOTSTRAP_STATE, "state", "partial")
        assert due_in() == 0.0
