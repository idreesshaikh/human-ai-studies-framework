"""
Each S2 helper builds the request the official OpenAPI documents describe
(graph/v1 and recommendations/v1 swagger.json), on stubbed transports.
"""

from __future__ import annotations

import urllib.parse

import pytest
from middleware.db import S2Cache, make_session_factory

from middleware import semantic_scholar as s2


def _split(url: str) -> tuple[str, dict]:
    parts = urllib.parse.urlsplit(url)
    return parts.path, {k: v[0] for k, v in urllib.parse.parse_qs(parts.query).items()}


PAPER = {
    "paperId": "abc",
    "title": "A synthetic paper",
    "externalIds": {"ArXiv": "2601.00001"},
    "year": 2026,
}


def test_relevance_search_caps_limit_and_drops_hyphens():
    seen = []

    def fetch(url):
        seen.append(url)
        return {"total": 1, "data": [PAPER, {"title": "no id"}]}

    papers = s2.search("AI-assisted pair-programming", limit=500, fetch=fetch)
    path, params = _split(seen[0])
    assert path == "/graph/v1/paper/search"
    # "Hyphenated query terms yield no matches"; limit "Must be <= 100".
    assert params["query"] == "AI assisted pair programming"
    assert params["limit"] == "100"
    assert "publicationDate" in params["fields"].split(",")
    assert [p["paperId"] for p in papers] == ["abc"]
    assert s2.search("   ", fetch=fetch) == [] and len(seen) == 1


def test_bulk_search_uses_the_documented_parameters_only():
    path, params = _split(
        s2.bulk_search_url("copilot", since="2026-10-01", until="2026-11-01")
    )
    assert path == "/graph/v1/paper/search/bulk"
    assert params == {
        "query": "copilot",
        "publicationDateOrYear": "2026-10-01:2026-11-01",
        "fields": s2.SEARCH_FIELDS,
        "sort": "publicationDate:desc",
    }
    with pytest.raises(s2.SemanticScholarError):
        s2.search_bulk("q", since="a", until="b", fetch=lambda url: [])


def test_batch_sends_ids_in_the_body_and_fields_as_a_query_parameter():
    calls = []

    def post(url, payload):
        calls.append((url, payload))
        return [PAPER, None, {"error": "not found"}]

    out = s2.fetch_batch_raw(["abc", "ARXIV:1", "DOI:x"], fields="title", post=post)
    path, params = _split(calls[0][0])
    assert path == "/graph/v1/paper/batch" and params == {"fields": "title"}
    assert calls[0][1] == {"ids": ["abc", "ARXIV:1", "DOI:x"]}
    assert out == [PAPER, None, None]
    with pytest.raises(ValueError):
        s2.fetch_batch_raw(["x"] * (s2.BATCH_MAX_IDS + 1), fields="title", post=post)


def test_citations_filter_by_publication_window():
    seen = []

    def fetch(url):
        seen.append(url)
        return {"data": [{"citingPaper": PAPER}, {"citingPaper": {"title": "x"}}]}

    papers = s2.fetch_citations(
        "ARXIV:2302.06590", since="2026-10-01", until="2026-11-01", fetch=fetch
    )
    path, params = _split(seen[0])
    assert path == "/graph/v1/paper/ARXIV:2302.06590/citations"
    assert params["publicationDateOrYear"] == "2026-10-01:2026-11-01"
    assert params["limit"] == "100" and [p["paperId"] for p in papers] == ["abc"]


def test_recommendations_post_positive_and_negative_ids():
    calls = []

    def post(url, payload):
        calls.append((url, payload))
        return {"recommendedPapers": [PAPER]}

    out = s2.fetch_recommendations(["a"], ["b"], limit=900, post=post)
    path, params = _split(calls[0][0])
    assert path == "/recommendations/v1/papers/"
    assert params["limit"] == "500"  # "Maximum 500"
    assert calls[0][1] == {"positivePaperIds": ["a"], "negativePaperIds": ["b"]}
    assert out == [PAPER]
    assert s2.fetch_recommendations([], ["b"], post=post) == [] and len(calls) == 1


def test_edges_log_a_failing_kind_and_keep_the_others(caplog):
    def fetch(url):
        if "forpaper" in url:
            raise s2.SemanticScholarError("HTTP 429", status=429)
        if "/references" in url:
            return {"data": [{"citedPaper": PAPER}]}
        return {"data": []}

    edges = s2.fetch_edges("arxiv:2302.06590", fetch=fetch)
    assert [e["paperRef"] for e in edges["references"]] == ["arxiv:2601.00001"]
    assert edges["recommendations"] == [] and "recommendations" in caplog.text


def test_lookup_ids_prefer_s2_then_arxiv_then_doi():
    assert s2.lookup_id("hash", "10.1/x", "2601.1v2") == "hash"
    assert s2.lookup_id("", "10.1/x", "2601.1v2") == "ARXIV:2601.1"
    assert s2.lookup_id(None, "10.1/x", "") == "DOI:10.1/x"
    assert s2.lookup_id("", "", "") == ""


def test_cached_get_reuses_fresh_answers_and_refetches_stale_ones(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        s2, "get_json", lambda url: calls.append(url) or {"n": len(calls)}
    )
    factory = make_session_factory(tmp_path / "cache.sqlite3")
    url = f"{s2.GRAPH_API}/paper/search?query=x"
    with factory() as s:
        assert s2.cached_get(s, url, now="2026-11-01T00:00:00Z") == {"n": 1}
        # Unflushed rows count as cached within the session.
        assert s2.cached_get(s, url, now="2026-11-01T00:00:00Z") == {"n": 1}
        s.commit()
    with factory() as s:
        fresh = s2.cached_get(s, url, now="2026-11-05T00:00:00Z", max_age_days=7)
        stale = s2.cached_get(s, url, now="2026-11-20T00:00:00Z", max_age_days=7)
        forever = s2.cached_get(s, url, now="2027-01-01T00:00:00Z")
        s.commit()
        assert (fresh, stale, forever) == ({"n": 1}, {"n": 2}, {"n": 2})
        assert s.query(S2Cache).count() == 1
    assert len(calls) == 2


def test_stale_search_answers_are_pruned_and_graph_answers_kept(tmp_path):
    from middleware.db import S2Cache, make_session_factory
    from sqlalchemy import select

    factory = make_session_factory(tmp_path / "cache.sqlite3")
    base = "https://api.semanticscholar.org/graph/v1"
    rows = {
        f"{base}/paper/search?query=old": "2026-01-01T00:00:00Z",
        f"{base}/paper/search?query=new": "2026-11-20T00:00:00Z",
        f"{base}/paper/abc?fields=title": "2026-01-01T00:00:00Z",
    }
    with factory() as s:
        for url, at in rows.items():
            s.add(S2Cache(url=url, body={}, fetched_at=at))
        s.commit()
        assert s2.prune_search_cache(s, now="2026-11-25T00:00:00Z") == 1
        s.commit()
        left = set(s.scalars(select(S2Cache.url)))
    assert left == {f"{base}/paper/search?query=new", f"{base}/paper/abc?fields=title"}
