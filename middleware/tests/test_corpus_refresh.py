import json
from datetime import date
from pathlib import Path

import pytest
from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory

from middleware import corpus_refresh as rp

FIX = Path(__file__).parent / "fixtures" / "refresh"
CONFIG = {
    "arxiv": [{"terms": ["coding assistant"], "categories": ["cs.SE"]}],
    "semanticScholar": ["AI coding assistant developer"],
    "maxPerQuery": 100,
}


@pytest.fixture
def sf(tmp_path):
    return make_session_factory(tmp_path / "r.sqlite3")


def _fetchers(arxiv=None, s2=None):
    arxiv_bytes = (FIX / "arxiv_real.xml").read_bytes() if arxiv is None else arxiv
    s2_payload = json.loads((FIX / "s2_real.json").read_text()) if s2 is None else s2
    calls = {"arxiv": [], "s2": []}

    def fetch_arxiv(q, since, until, start, n):
        calls["arxiv"].append((q, since, until, start, n))
        if isinstance(arxiv_bytes, Exception):
            raise arxiv_bytes
        return (
            arxiv_bytes
            if start == 0
            else b'<feed xmlns="http://www.w3.org/2005/Atom"/>'
        )

    def fetch_s2(q, since, until, token, n):
        calls["s2"].append((q, since, until, token, n))
        if isinstance(s2_payload, Exception):
            raise s2_payload
        return s2_payload

    return fetch_arxiv, fetch_s2, calls


def _run(sf, **kw):
    fa, fs, calls = _fetchers(kw.pop("arxiv", None), kw.pop("s2", None))
    out = rp.refresh(
        sf,
        config=CONFIG,
        since="2026-09-08",
        until="2026-10-08",
        fetch_arxiv=fa,
        fetch_s2=fs,
        score_fn=lambda c: 1.0,
        now=lambda: "2026-10-08T12:00:00Z",
        **kw,
    )
    return out, calls


def test_new_papers_become_candidates_and_a_run_is_recorded(sf):
    out, calls = _run(sf)
    assert (
        out["status"] == "ok" and out["newCandidates"] == 4 and out["duplicates"] == 0
    )
    with sf() as s:
        rows = s.query(rp.CorpusCandidate).all()
        assert len(rows) == 4 and all(
            r.status == "new" and r.score == 1.0 for r in rows
        )
        assert any(r.ref == "arxiv:2610.07639" and r.abstract for r in rows)
        run = s.query(rp.CorpusRefreshRun).one()
        assert (run.status, run.new_candidates, run.since, run.until) == (
            "ok",
            4,
            "2026-09-08",
            "2026-10-08",
        )
    assert calls["arxiv"][0][1:3] == ("2026-09-08", "2026-10-08")


def test_a_second_run_finds_nothing_new(sf):
    _run(sf)
    out, _ = _run(sf)
    assert out["newCandidates"] == 0 and out["duplicates"] == 4
    with sf() as s:
        assert s.query(rp.CorpusCandidate).count() == 4


def test_papers_already_in_the_corpus_are_not_candidates(sf):
    with sf() as s:
        s.add(
            Paper(
                study_id=CORPUS_STUDY_ID,
                paper_ref="arxiv:2610.07639",
                title="Anything",
                added_at="",
            )
        )
        s.commit()
    out, _ = _run(sf)
    assert "arxiv:2610.07639" not in out["candidates"] and out["duplicates"] == 1


def test_a_failing_source_is_recorded_and_the_other_still_runs(sf):
    out, _ = _run(sf, s2=RuntimeError("429 Too Many Requests"))
    assert out["status"] == "partial" and out["newCandidates"] == 2
    assert out["errors"][0]["source"] == "s2" and "429" in out["errors"][0]["message"]


def test_all_sources_failing_is_a_failed_run_that_does_not_move_the_watermark(sf):
    out, _ = _run(sf, arxiv=RuntimeError("down"), s2=RuntimeError("down"))
    assert out["status"] == "failed" and out["newCandidates"] == 0
    with sf() as s:
        assert rp.last_until(s) is None


def test_dry_run_writes_nothing(sf):
    out, _ = _run(sf, dry_run=True)
    assert out["status"] == "dry-run" and out["newCandidates"] == 4
    with sf() as s:
        assert (
            s.query(rp.CorpusCandidate).count() == 0
            and s.query(rp.CorpusRefreshRun).count() == 0
        )


def test_window_resumes_from_the_last_good_run_with_one_day_overlap(sf):
    _run(sf)
    with sf() as s:
        assert rp.window(s, today=date(2026, 10, 20), default_days=30, since=None) == (
            "2026-10-07",
            "2026-10-20",
        )
        assert rp.window(
            s, today=date(2026, 10, 20), default_days=30, since="2026-01-01"
        ) == ("2026-01-01", "2026-10-20")


def test_first_window_uses_the_default_span(sf):
    with sf() as s:
        assert rp.window(s, today=date(2026, 10, 8), default_days=30, since=None) == (
            "2026-09-08",
            "2026-10-08",
        )


def test_arxiv_query_builder_and_quote_safety():
    assert rp.arxiv_query(["coding assistant", 'say "hi"'], ["cs.SE", "cs.HC"]) == (
        '(cat:cs.SE OR cat:cs.HC) AND (all:"coding assistant" OR all:"say  hi")'
    )
    with pytest.raises(ValueError):
        rp.arxiv_query([], ["cs.SE"])


def test_paging_stops_when_a_page_is_short(sf):
    _, calls = _run(sf)
    assert len(calls["arxiv"]) == 1  # 2 results < page size, so no second request


def test_a_recent_running_run_blocks_a_new_one_but_a_stale_one_does_not(sf):
    from datetime import datetime  # noqa: F401

    with sf() as s:
        s.add(
            rp.CorpusRefreshRun(
                started_at="2026-10-08T11:00:00Z",
                status="running",
                since="a",
                until="b",
            )
        )
        s.commit()
        with pytest.raises(rp.RefreshInProgress):
            rp.ensure_not_running(s, now_iso="2026-10-08T12:00:00Z")
        rp.ensure_not_running(
            s, now_iso="2026-10-08T18:30:00Z"
        )  # 7.5 h later: considered dead


def test_scheduler_runs_repeatedly_survives_failures_and_stops():
    import threading
    import time

    calls = []

    def run():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")

    stop = threading.Event()
    t = threading.Thread(
        target=rp.run_scheduler,
        kwargs={"stop": stop, "interval_s": 0.01, "run": run, "first_delay_s": 0.0},
    )
    t.start()
    deadline = time.time() + 5
    while len(calls) < 3 and time.time() < deadline:
        time.sleep(0.01)
    stop.set()
    t.join(2)
    assert len(calls) >= 3 and not t.is_alive()


def test_scheduler_first_delay_can_be_cancelled_before_any_run():
    import threading

    calls = []
    stop = threading.Event()
    stop.set()
    rp.run_scheduler(stop, interval_s=1, run=lambda: calls.append(1), first_delay_s=60)
    assert calls == []


def test_start_scheduler_rejects_a_non_positive_interval():
    with pytest.raises(ValueError):
        rp.start_scheduler(interval_hours=0, run=lambda: None)


def test_partial_runs_do_not_skip_a_failed_sources_date_window(sf):
    _run(sf, s2=RuntimeError("offline"))
    with sf() as s:
        assert rp.last_until(s) is None


def test_repeated_s2_pagination_tokens_are_refused():
    calls = []

    def repeated(*args):
        calls.append(1)
        assert len(calls) <= 3, "pagination did not stop"
        return {"data": [], "token": "same"}

    with pytest.raises(rp.SourceFormatError):
        rp._collect_s2(repeated, "q", "a", "b", 10)


def test_overlapping_refreshes_are_refused_atomically(sf, monkeypatch):
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy.exc import IntegrityError

    barrier = threading.Barrier(2)
    release = threading.Event()
    entered = threading.Event()
    lock = threading.Lock()
    calls = []
    original = rp.ensure_not_running

    def simultaneous_checks(s, **kwargs):
        original(s, **kwargs)
        barrier.wait(timeout=5)

    monkeypatch.setattr(rp, "ensure_not_running", simultaneous_checks)
    xml = (FIX / "arxiv_real.xml").read_bytes()

    def fetch(*args):
        with lock:
            calls.append(1)
        entered.set()
        release.wait(5)
        return xml

    def run():
        return rp.refresh(
            sf,
            config={"arxiv": CONFIG["arxiv"]},
            since="2026-09-08",
            until="2026-10-08",
            fetch_arxiv=fetch,
            fetch_s2=lambda *args: {"data": []},
            score_fn=lambda _: 1.0,
            now=lambda: "2026-10-08T12:00:00Z",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run), pool.submit(run)]
        try:
            assert entered.wait(5)
            deadline = time.monotonic() + 2
            while (
                len(calls) < 2
                and not any(f.done() for f in futures)
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            observed = len(calls)
        finally:
            release.set()
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result(timeout=5))
            except (rp.RefreshInProgress, IntegrityError) as exc:
                outcomes.append(exc)
    assert observed == 1, (
        "two refreshes fetched concurrently after both checked an empty lock"
    )
    assert sum(isinstance(item, rp.RefreshInProgress) for item in outcomes) == 1
