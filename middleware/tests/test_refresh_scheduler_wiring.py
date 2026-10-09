"""Refresh scheduling is opt-in and rejects unusable intervals."""

import pytest
from middleware.app import create_app
from middleware.settings import Settings

from middleware import corpus_refresh


@pytest.mark.parametrize(
    "value,expected",
    [(None, None), ("6", 6.0), ("abc", None), ("0", None), ("nan", None)],
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
    create_app(settings)
    assert [call["interval_hours"] for call in calls] == (
        [expected] if expected else []
    )
    if value is not None and expected is None:
        assert "MIDDLEWARE_REFRESH_INTERVAL_H" in caplog.text
