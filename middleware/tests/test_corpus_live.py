"""Live Semantic Scholar search behind ``match_papers(live=True)`` (stubbed S2)."""

from __future__ import annotations

import threading
import time

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.db import (
    CORPUS_STUDY_ID,
    CorpusCandidate,
    Paper,
    S2Cache,
    make_session_factory,
)
from middleware.settings import Settings

from middleware import corpus_live, matching, paper_index, semantic_scholar

ABSTRACT = (
    "We observed novice programmers debugging with an AI assistant during "
    "think-aloud sessions and report how eye tracking revealed their attention."
)


def _s2_paper(pid: str, title: str, arxiv: str | None = None, **extra) -> dict:
    return {
        "paperId": pid,
        "title": title,
        "abstract": ABSTRACT,
        "year": 2026,
        "publicationDate": "2026-10-01",
        "venue": "CHI",
        "externalIds": {"ArXiv": arxiv} if arxiv else {"DOI": f"10.1/{pid}"},
        "authors": [{"name": "A. Author"}],
        "citationCount": 3,
        **extra,
    }


LIVE = [
    _s2_paper("p1", "Eye tracking novice programmers debugging with AI", "2610.00001"),
    _s2_paper("p2", "Think-aloud study of debugging with assistants", "2610.00002"),
    {**_s2_paper("p3", "Unrelated photosynthesis work"), "abstract": "Leaves."},
]


@pytest.fixture(autouse=True)
def fresh_breaker(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("network access in a test")

    monkeypatch.setattr(semantic_scholar, "_urlopen", refuse)
    monkeypatch.setenv("MIDDLEWARE_LIVE_SEARCH", "1")
    corpus_live.reset()
    yield
    corpus_live.drain()
    corpus_live.reset()


@pytest.fixture
def factory(tmp_path):
    return make_session_factory(tmp_path / "live.sqlite3")


def _seed(factory, rows):
    with factory() as s:
        for ref, title, abstract in rows:
            s.add(
                Paper(
                    study_id=CORPUS_STUDY_ID,
                    paper_ref=ref,
                    title=title,
                    abstract=abstract,
                    tier="B",
                    score=10.0,
                    added_at="",
                )
            )
            paper_index.index_paper(s, ref, title, abstract)
        s.commit()


def _stub_search(monkeypatch, papers=LIVE, *, delay=0.0, error=None):
    calls = []

    def get_json(url):
        calls.append(url)
        if delay:
            time.sleep(delay)
        if error is not None:
            raise error
        return {"total": len(papers), "data": papers}

    monkeypatch.setattr(semantic_scholar, "get_json", get_json)
    return calls


def _hold_background_stores(monkeypatch) -> threading.Event:
    """Delay the live worker's corpus write (not a request's) until released."""
    release = threading.Event()
    original = corpus_live.store

    def store(*args, **kwargs):
        if threading.current_thread().name.startswith("s2-live"):
            release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(corpus_live, "store", store)
    return release


QUERY = "novice programmers debugging eye tracking think-aloud with an AI assistant"


def test_weak_local_results_are_topped_up_live_and_stored(factory, monkeypatch):
    calls = _stub_search(monkeypatch)
    with factory() as s:
        results = matching.match_papers(s, QUERY, limit=8, live=True)
    corpus_live.drain()
    assert len(calls) == 1 and "/graph/v1/paper/search?" in calls[0]
    refs = [r["ref"] for r in results]
    assert refs[:2] == ["arxiv:2610.00001", "arxiv:2610.00002"]
    assert "doi:10.1/p3" not in refs  # live results must match specifically
    assert all(r["source"] == "semantic-scholar" for r in results)
    assert all(r["matchKind"] == "direct" and r["matchReason"] for r in results)
    with factory() as s:
        row = s.query(Paper).filter_by(paper_ref="arxiv:2610.00001").one()
        assert (row.study_id, row.tier, row.added_via) == (
            CORPUS_STUDY_ID,
            "C",
            "live-search",
        )
        assert s.query(S2Cache).count() == 1
        # Stored papers are searchable locally next time, without S2.
        again = matching.match_papers(s, QUERY, limit=8)
        assert "arxiv:2610.00001" in [r["ref"] for r in again]
        assert all(r["source"] == "corpus" for r in again)


def test_strong_local_results_never_call_s2(factory, monkeypatch):
    _seed(
        factory,
        [
            (f"arxiv:2601.0000{i}", f"Novice programmers debugging study {i}", ABSTRACT)
            for i in range(4)
        ],
    )
    calls = _stub_search(monkeypatch)
    with factory() as s:
        results = matching.match_papers(s, QUERY, limit=8, live=True)
    assert calls == []
    assert len(results) == 4 and all(r["source"] == "corpus" for r in results)


def test_rate_limited_s2_returns_local_results_and_pauses_live_search(
    factory, monkeypatch
):
    _seed(factory, [("arxiv:2601.00009", "Novice debugging", ABSTRACT)])
    calls = _stub_search(
        monkeypatch,
        error=semantic_scholar.SemanticScholarError(
            "HTTP 429", status=429, retry_after=5
        ),
    )
    with factory() as s:
        first = matching.match_papers(s, QUERY, limit=8, live=True)
        started = time.monotonic()
        second = matching.match_papers(s, QUERY, limit=8, live=True)
        elapsed = time.monotonic() - started
    assert (
        [r["ref"] for r in first] == [r["ref"] for r in second] == ["arxiv:2601.00009"]
    )
    assert len(calls) == 1 and elapsed < 0.5  # the breaker skips S2 at once
    assert corpus_live.status()["paused"] is True


def test_the_pause_reason_never_carries_the_search_keywords(factory, monkeypatch):
    url = f"{semantic_scholar.GRAPH_API}/paper/search?query=novice+debugging"
    _stub_search(
        monkeypatch,
        error=semantic_scholar.SemanticScholarError(f"GET {url} failed: timed out"),
    )
    with factory() as s:
        matching.match_papers(s, QUERY, limit=8, live=True)
    # /corpus/status is visible to every user; another study's keywords are not.
    status = corpus_live.status()
    assert status["paused"] is True and status["lastError"] == "no usable answer"


def test_slow_s2_is_abandoned_at_the_budget_but_still_warms_the_corpus(
    factory, monkeypatch
):
    _stub_search(monkeypatch, delay=1.5)
    with factory() as s:
        started = time.monotonic()
        results = corpus_live.search(s.get_bind(), "novice debugging", budget_s=0.2)
        elapsed = time.monotonic() - started
    # Returned well before S2 answered (margin for a loaded test machine).
    assert results == [] and elapsed < 1.0
    corpus_live.drain()
    with factory() as s:
        assert s.query(Paper).filter_by(paper_ref="arxiv:2610.00001").count() == 1


def test_hidden_and_rejected_papers_are_never_brought_back(factory, monkeypatch):
    with factory() as s:
        s.add(
            Paper(
                study_id=CORPUS_STUDY_ID,
                paper_ref="corpus:eye-tracking",
                title=LIVE[0]["title"],
                curation="hidden",
                added_at="",
            )
        )
        s.add(
            CorpusCandidate(
                ref="arxiv:2610.00002",
                title=LIVE[1]["title"],
                source="s2",
                run_id=1,
                first_seen_at="",
                status="rejected",
            )
        )
        s.commit()
    _stub_search(monkeypatch)
    with factory() as s:
        results = matching.match_papers(s, QUERY, limit=8, live=True)
    corpus_live.drain()
    assert results == []
    with factory() as s:
        assert s.query(Paper).filter_by(added_via="live-search").count() == 0


def test_a_known_paper_found_live_keeps_its_corpus_ref(factory, monkeypatch):
    _seed(factory, [("corpus:eye-tracking", LIVE[0]["title"], "")])
    _stub_search(monkeypatch, [LIVE[0]])
    with factory() as s:
        records = corpus_live.search(s.get_bind(), "eye tracking novice")
    corpus_live.drain()
    assert [(r["ref"], r.get("inCorpus")) for r in records] == [
        ("corpus:eye-tracking", True)
    ]
    with factory() as s:
        assert s.query(Paper).count() == 1


def test_grounding_resolves_a_live_paper_before_its_row_lands(factory, monkeypatch):
    release = _hold_background_stores(monkeypatch)
    _stub_search(monkeypatch)
    with factory() as s:
        results = matching.match_papers(s, QUERY, limit=8, live=True)
        ref = results[0]["ref"]
        assert s.query(Paper).filter_by(paper_ref=ref).count() == 0
        meta = matching.get_paper_metadata(s, ref)
        assert meta["title"] == LIVE[0]["title"] and meta["confidence"] is not None
    release.set()


def test_live_query_keeps_the_repeated_specific_terms():
    query = (
        "novice programmers and AI. novice debugging with eye tracking. "
        "eye tracking of novice debugging code"
    )
    assert matching._live_query(query).split()[:3] == ["novice", "debugging", "eye"]
    assert matching._live_query("AI code tools for developers") == ""


def test_the_rail_can_add_a_live_result_straight_away(tmp_path, monkeypatch):
    settings = Settings(
        db_path=tmp_path / "rail.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
    )
    client = TestClient(create_app(settings))
    study = client.post("/projects/implicit/studies", json={"name": "Live"}).json()
    release = _hold_background_stores(monkeypatch)

    def get_json(url):
        if "/paper/search?" in url:
            return {"data": LIVE}
        if "/recommendations/" in url:
            return {"recommendedPapers": []}
        return {"data": []}

    monkeypatch.setattr(semantic_scholar, "get_json", get_json)
    match = client.post(
        f"/studies/{study['id']}/papers/match", json={"query": QUERY, "limit": 5}
    )
    assert match.status_code == 200, match.text
    first = match.json()["recommendations"][0]
    assert first["source"] == "semantic-scholar"
    added = client.post(
        f"/studies/{study['id']}/papers/from-match",
        json={"ref": first["ref"], "matchReason": first["matchReason"]},
    )
    release.set()
    assert added.status_code == 200, added.text
    papers = client.get(f"/studies/{study['id']}/papers").json()
    assert first["ref"] in [p["paperRef"] for p in papers]
    status = client.get("/corpus/status").json()
    assert (
        status["liveSearch"]["added"] >= 1 and status["liveSearch"]["paused"] is False
    )


def test_live_search_can_be_switched_off(factory, monkeypatch):
    calls = _stub_search(monkeypatch)
    monkeypatch.setenv("MIDDLEWARE_LIVE_SEARCH", "0")
    with factory() as s:
        assert corpus_live.search(s.get_bind(), "debugging assistants") == []
    assert calls == []
