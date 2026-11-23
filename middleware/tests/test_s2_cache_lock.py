"""Citation harvesting must not hold SQLite's write lock across network calls.

Adding a paper starts a background harvest that makes several Semantic Scholar
requests. If the harvest flushes its cache rows before those requests, its session
holds the database's only write lock for as long as the network takes, and any
concurrent writer (approving a protocol, for one) fails with "database is locked".
"""

import sqlite3

from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

from middleware import semantic_scholar

ARXIV_ID = "2302.06590"
PAPER = {  # synthetic response shape; no real metadata is asserted
    "paperId": "synthetic-paper",
    "title": "A synthetic paper",
    "externalIds": {"ArXiv": ARXIV_ID},
    "year": 2023,
    "authors": [],
    "abstract": "",
}


def test_harvest_keeps_the_database_writable_during_network_calls(
    tmp_path, monkeypatch
):
    settings = Settings(
        db_path=tmp_path / "lock.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    client = TestClient(create_app(settings))
    study = client.post("/projects/implicit/studies", json={"name": "Lock"}).json()
    with sqlite3.connect(settings.db_path) as setup:
        setup.execute("CREATE TABLE lock_probe (url TEXT)")
    requested: list[str] = []
    blocked: list[str] = []

    def fake_get_json(url: str) -> dict:
        requested.append(url)
        # Another writer while this request is "in flight". Background tasks run
        # on another thread, so each probe opens its own connection.
        probe = sqlite3.connect(settings.db_path, timeout=0.2)
        try:
            probe.execute("INSERT INTO lock_probe VALUES (?)", (url,))
            probe.commit()
        except sqlite3.OperationalError as exc:
            blocked.append(f"{exc}: {url}")
        finally:
            probe.close()
        if "/recommendations/" in url:
            return {"recommendedPapers": []}
        if "/references" in url or "/citations" in url:
            return {"data": []}
        return PAPER

    monkeypatch.setattr(semantic_scholar, "get_json", fake_get_json)

    response = client.post(f"/studies/{study['id']}/papers", json={"arxivId": ARXIV_ID})

    assert response.status_code == 200, response.text
    assert len(requested) >= 3, requested  # metadata plus the graph harvest
    assert blocked == []


def test_a_repeated_url_in_one_session_is_served_from_the_cache(tmp_path, monkeypatch):
    """Rows not yet flushed still count as cached, so the unique URL never repeats."""
    settings = Settings(
        db_path=tmp_path / "repeat.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    client = TestClient(create_app(settings))
    study = client.post("/projects/implicit/studies", json={"name": "Repeat"}).json()
    calls: list[str] = []

    def fake_get_json(url: str) -> dict:
        calls.append(url)
        if "/recommendations/" in url:
            return {"recommendedPapers": []}
        if "/references" in url or "/citations" in url:
            return {"data": []}
        return PAPER

    monkeypatch.setattr(semantic_scholar, "get_json", fake_get_json)
    first = client.post(f"/studies/{study['id']}/papers", json={"arxivId": ARXIV_ID})
    again = client.post(f"/studies/{study['id']}/papers", json={"arxivId": ARXIV_ID})

    assert first.status_code == 200, first.text
    assert again.status_code == 200, again.text
    assert len(calls) == len(set(calls)), calls
