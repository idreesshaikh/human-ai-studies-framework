import urllib.parse

from middleware import corpus_fetchers as f


def _params(url):
    return {
        k: v[0]
        for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()
    }


def test_arxiv_url_matches_the_shape_that_worked_live():
    url = f.arxiv_url(
        '(cat:cs.SE) AND (all:"copilot")', "2026-09-08", "2026-10-08", 0, 50
    )
    assert url.startswith("https://export.arxiv.org/api/query?")
    p = _params(url)
    assert p["search_query"] == (
        '(cat:cs.SE) AND (all:"copilot") AND submittedDate:'
        "[202609080000 TO 202610082359]"
    )
    assert (p["start"], p["max_results"], p["sortBy"], p["sortOrder"]) == (
        "0",
        "50",
        "submittedDate",
        "descending",
    )


def test_s2_url_carries_the_date_window_fields_and_optional_token():
    p = _params(
        f.s2_bulk_url("AI coding assistant", "2026-09-08", "2026-10-08", None, 100)
    )
    assert p["publicationDateOrYear"] == "2026-09-08:2026-10-08" and p["limit"] == "100"
    assert (
        "abstract" in p["fields"] and "externalIds" in p["fields"] and "token" not in p
    )
    assert _params(f.s2_bulk_url("q", "a", "b", "TOK", 5))["token"] == "TOK"


def test_arxiv_requests_are_spaced_by_three_seconds(monkeypatch):
    slept, now = [], [100.0]

    class _R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"<feed/>"

    monkeypatch.setattr(
        f, "_sleep", lambda s: (slept.append(s), now.__setitem__(0, now[0] + s))
    )
    monkeypatch.setattr(f, "_clock", lambda: now[0])
    monkeypatch.setattr(f, "_arxiv_last", 0.0)
    monkeypatch.setattr(f.urllib.request, "urlopen", lambda req, timeout: _R())
    f.fetch_arxiv("q", "2026-01-01", "2026-01-02", 0, 10)
    now[0] += 1.0
    f.fetch_arxiv("q", "2026-01-01", "2026-01-02", 10, 10)
    assert len(slept) == 1 and abs(slept[0] - 2.0) < 1e-9


def test_user_agent_includes_the_contact_when_configured(monkeypatch):
    monkeypatch.delenv("MIDDLEWARE_CONTACT_EMAIL", raising=False)
    assert f._user_agent() == "StudyLoop-corpus-refresh"
    monkeypatch.setenv("MIDDLEWARE_CONTACT_EMAIL", "a@b.org")
    assert f._user_agent().endswith("(mailto:a@b.org)")
