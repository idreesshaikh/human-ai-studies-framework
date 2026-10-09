"""Config, the shared run entry point, promotion, and the readiness count."""

import json
from datetime import date
from pathlib import Path

import pytest
from middleware.db import CORPUS_STUDY_ID, CorpusCandidate, Paper, make_session_factory

from middleware import corpus_fetchers, corpus_importer, matching, paper_index
from middleware import corpus_refresh as cr

FIX = Path(__file__).parent / "fixtures" / "refresh"
NOW = lambda: "2026-10-08T12:00:00Z"  # noqa: E731
GOOD_CONFIG = {
    "arxiv": [{"terms": ["coding assistant"], "categories": ["cs.SE"]}],
    "semanticScholar": ["AI coding assistant developer"],
    "maxPerQuery": 50,
}


@pytest.fixture
def sf(tmp_path):
    return make_session_factory(tmp_path / "flow.sqlite3")


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "queries.json"
    path.write_text(json.dumps(GOOD_CONFIG))
    return path


@pytest.fixture
def live_stubs(monkeypatch):
    calls = {"arxiv": 0, "s2": 0}

    def arxiv(q, since, until, start, n):
        calls["arxiv"] += 1
        return (
            (FIX / "arxiv_real.xml").read_bytes()
            if start == 0
            else b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
        )

    def s2(q, since, until, token, n):
        calls["s2"] += 1
        return json.loads((FIX / "s2_real.json").read_text())

    monkeypatch.setattr(corpus_fetchers, "fetch_arxiv", arxiv)
    monkeypatch.setattr(corpus_fetchers, "fetch_s2", s2)
    return calls


# --- config


def test_the_shipped_default_queries_file_is_valid():
    config = cr.load_config(cr.DEFAULT_QUERIES)
    assert (
        config["arxiv"]
        and config["semanticScholar"]
        and 1 <= config["maxPerQuery"] <= 1000
    )


@pytest.mark.parametrize(
    "bad",
    [
        "not json",
        "[]",
        json.dumps({}),
        json.dumps({"arxiv": [{"terms": [], "categories": ["cs.SE"]}]}),
        json.dumps({"arxiv": [{"terms": ["x"], "categories": []}]}),
        json.dumps({"semanticScholar": ["  "]}),
        json.dumps({"semanticScholar": ["q"], "maxPerQuery": 0}),
        json.dumps({"semanticScholar": ["q"], "maxPerQuery": 100000}),
    ],
)
def test_bad_config_is_refused_with_a_reason(tmp_path, bad):
    path = tmp_path / "q.json"
    path.write_text(bad)
    with pytest.raises(ValueError):
        cr.load_config(path)


def test_missing_config_file_is_a_value_error(tmp_path):
    with pytest.raises(ValueError):
        cr.load_config(tmp_path / "nope.json")


# --- run_once


def test_run_once_stores_candidates_and_resumes_from_the_last_run(
    sf, config_file, live_stubs
):
    first = cr.run_once(sf, config_path=config_file, today=date(2026, 10, 8), now=NOW)
    assert first["status"] == "ok" and first["newCandidates"] == 4
    assert (first["since"], first["until"]) == ("2026-09-08", "2026-10-08")
    second = cr.run_once(
        sf,
        config_path=config_file,
        today=date(2026, 10, 20),
        now=lambda: "2026-10-20T12:00:00Z",
    )
    assert second["since"] == "2026-10-07" and second["newCandidates"] == 0
    with sf() as s:
        scores = [c.score for c in s.query(CorpusCandidate).all()]
        assert all(score is not None and score > 0 for score in scores)


def test_run_once_refuses_to_overlap_a_running_refresh(sf, config_file, live_stubs):
    with sf() as s:
        s.add(
            cr.CorpusRefreshRun(
                started_at="2026-10-08T11:30:00Z",
                status="running",
                since="a",
                until="b",
            )
        )
        s.commit()
    with pytest.raises(cr.RefreshInProgress):
        cr.run_once(sf, config_path=config_file, today=date(2026, 10, 8), now=NOW)
    assert live_stubs == {"arxiv": 0, "s2": 0}


def test_dry_run_ignores_the_lock_and_writes_nothing(sf, config_file, live_stubs):
    with sf() as s:
        s.add(
            cr.CorpusRefreshRun(
                started_at="2026-10-08T11:30:00Z",
                status="running",
                since="a",
                until="b",
            )
        )
        s.commit()
    out = cr.run_once(
        sf, config_path=config_file, dry_run=True, today=date(2026, 10, 8), now=NOW
    )
    assert out["status"] == "dry-run" and out["newCandidates"] == 4
    with sf() as s:
        assert s.query(CorpusCandidate).count() == 0


def test_last_run_summary_reports_age_in_days(sf, config_file, live_stubs):
    with sf() as s:
        assert cr.last_run_summary(s, today=date(2026, 10, 8)) is None
    cr.run_once(sf, config_path=config_file, today=date(2026, 10, 8), now=NOW)
    with sf() as s:
        summary = cr.last_run_summary(s, today=date(2026, 10, 15))
        assert (
            summary["ageDays"] == 7
            and summary["status"] == "ok"
            and summary["newCandidates"] == 4
        )


# --- the live S2 fetcher


def test_fetch_s2_uses_the_semantic_scholar_client_and_checks_the_shape(monkeypatch):
    from middleware import semantic_scholar

    seen = []
    monkeypatch.setattr(
        semantic_scholar,
        "get_json",
        lambda url: seen.append(url) or {"data": [], "token": None},
    )
    assert corpus_fetchers.fetch_s2("q", "2026-09-08", "2026-10-08", None, 5) == {
        "data": [],
        "token": None,
    }
    assert seen[0].startswith(
        "https://api.semanticscholar.org/graph/v1/paper/search/bulk?"
    )
    monkeypatch.setattr(
        semantic_scholar, "get_json", lambda url: ["not", "an", "object"]
    )
    with pytest.raises(ValueError):
        corpus_fetchers.fetch_s2("q", "a", "b", None, 5)


# --- promotion


def _one_candidate(sf, config_file, live_stubs):
    cr.run_once(sf, config_path=config_file, today=date(2026, 10, 8), now=NOW)
    return "arxiv:2610.07639"


def test_a_candidate_is_invisible_to_matching_until_it_is_accepted(
    sf, config_file, live_stubs
):
    ref = _one_candidate(sf, config_file, live_stubs)
    query = "coding agent harnesses security mechanisms"
    with sf() as s:
        before = matching.match_papers(s, query, use_llm=False, expand=False)
        assert ref not in [m["ref"] for m in before]
        assert not paper_index.search(s, "harnesses")
        cr.promote(s, ref, decided_by="idrees", now=NOW(), note="relevant")
        s.commit()
    with sf() as s:
        after = matching.match_papers(s, query, use_llm=False, expand=False)
        assert ref in [m["ref"] for m in after]
        assert ref in [hit["paperRef"] for hit in paper_index.search(s, "harnesses")]
        row = s.query(Paper).filter_by(study_id=CORPUS_STUDY_ID, paper_ref=ref).one()
        assert (
            row.tier == "C"
            and row.added_via == "refresh"
            and row.source.startswith("refresh:")
        )
        cand = s.query(CorpusCandidate).filter_by(ref=ref).one()
        assert (cand.status, cand.decided_by, cand.note) == (
            "accepted",
            "idrees",
            "relevant",
        )


def test_promotion_is_idempotent_and_reject_is_not_silently_reversed(
    sf, config_file, live_stubs
):
    ref = _one_candidate(sf, config_file, live_stubs)
    other = next(r for (r,) in sf().query(CorpusCandidate.ref) if r != ref)
    with sf() as s:
        cr.promote(s, ref, decided_by="a", now=NOW())
        assert cr.promote(s, ref, decided_by="a", now=NOW())["alreadyAccepted"] is True
        cr.reject(s, other, decided_by="a", now=NOW(), note="off topic")
        with pytest.raises(ValueError):
            cr.promote(s, other, decided_by="a", now=NOW())
        with pytest.raises(ValueError):
            cr.reject(s, ref, decided_by="a", now=NOW())
        with pytest.raises(KeyError):
            cr.promote(s, "arxiv:0000.00000", decided_by="a", now=NOW())
        s.commit()
        assert s.query(Paper).filter_by(study_id=CORPUS_STUDY_ID).count() == 1


# --- readiness


def _paper(ref, tier):
    return Paper(
        study_id=CORPUS_STUDY_ID, paper_ref=ref, title=ref, tier=tier, added_at=""
    )


def test_promoted_papers_do_not_count_toward_corpus_readiness(sf, monkeypatch):
    monkeypatch.setattr(corpus_importer, "expected_corpus_rows", lambda: 3)
    with sf() as s:
        s.add(_paper("corpus:a", "A"))
        for i in range(5):
            s.add(_paper(f"arxiv:9999.0000{i}", "C"))
        s.commit()
        assert corpus_importer.core_row_count(s) == 1
        status = corpus_importer.corpus_status_for_session(s)
        assert (
            status["state"] == "partial"
            and status["papers"] == 1
            and status["expected"] == 3
        )


def test_boot_import_still_runs_when_only_promoted_rows_make_up_the_count(
    sf, monkeypatch
):
    monkeypatch.setattr(corpus_importer, "expected_corpus_rows", lambda: 3)
    calls = []
    monkeypatch.setattr(
        corpus_importer, "import_corpus", lambda *a, **k: calls.append(1)
    )
    monkeypatch.setattr(corpus_importer, "_BOOTSTRAP_THREAD", None)
    with sf() as s:
        s.add(_paper("corpus:a", "A"))
        for i in range(5):
            s.add(_paper(f"arxiv:9999.0000{i}", "C"))
        s.commit()
    corpus_importer.start_background_import("unused", sf)
    thread = corpus_importer._BOOTSTRAP_THREAD
    if thread is not None:
        thread.join(5)
    assert calls == [1]
