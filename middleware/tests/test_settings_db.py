"""How ``MIDDLEWARE_DB`` resolves to a database.

The failure this guards against is silent, which is what makes it worth a
test: passing a SQLite *URL* where a path was expected produced
``sqlite:///sqlite:///data.sqlite3`` — a valid relative filename. Nothing
raised. The server started, served, and reported healthy against an empty
database in a directory nobody was looking at, while the real one sat
untouched with the corpus in it.
"""

from __future__ import annotations

import pytest
from middleware.settings import Settings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("MIDDLEWARE_DB", raising=False)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/srv/study.sqlite3", "sqlite:////srv/study.sqlite3"),
        ("relative/study.sqlite3", "sqlite:///relative/study.sqlite3"),
        # The same two, spelled as URLs — the natural thing to try.
        ("sqlite:////srv/study.sqlite3", "sqlite:////srv/study.sqlite3"),
        ("sqlite:///relative/study.sqlite3", "sqlite:///relative/study.sqlite3"),
    ],
)
def test_a_path_and_its_url_spelling_reach_the_same_database(
    monkeypatch, value, expected
):
    monkeypatch.setenv("MIDDLEWARE_DB", value)
    assert Settings().db_url == expected


def test_postgres_urls_win_and_are_normalised_to_the_psycopg_driver(monkeypatch):
    monkeypatch.setenv("MIDDLEWARE_DB", "/ignored.sqlite3")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pw@host/db")
    settings = Settings()
    assert settings.db_url == "postgresql+psycopg://user:pw@host/db"
    assert settings.db_path is None


def test_the_default_is_a_relative_file_under_the_data_directory(monkeypatch):
    assert Settings().db_url == "sqlite:///.study-data/middleware.sqlite3"
