"""Settings.port precedence: MIDDLEWARE_PORT > PORT > 8000."""

from middleware.settings import Settings


def test_port_precedence_is_resolved_from_the_current_environment(monkeypatch):
    monkeypatch.delenv("MIDDLEWARE_PORT", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert Settings().port == 8000
    monkeypatch.setenv("PORT", "4123")
    assert Settings().port == 4123
    monkeypatch.setenv("MIDDLEWARE_PORT", "9001")
    assert Settings().port == 9001


def test_spa_resolves_from_repo_root_and_reports_missing_build(tmp_path, monkeypatch):
    from pathlib import Path

    import pytest
    from middleware.app import create_app

    monkeypatch.chdir(tmp_path)
    settings = Settings(spa_dist=Path("platform/dist"))
    assert settings.spa_dist == Path(__file__).resolve().parents[2] / "platform/dist"
    missing = Settings(
        db_path=tmp_path / "missing.sqlite",
        spa_dist=tmp_path / "missing-web",
        spa_required=True,
    )
    with pytest.raises(FileNotFoundError, match=r"missing-web/index\.html"):
        create_app(missing)
    assert not missing.db_path.exists()  # fail before database initialization
