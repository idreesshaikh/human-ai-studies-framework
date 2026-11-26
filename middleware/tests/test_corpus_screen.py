"""Screening new refresh candidates (SPECTER2 first, mistral-embed for the rest)."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest
from middleware.corpus_curate import store_embedding
from middleware.corpus_refresh import CURATION_DEFAULTS
from middleware.db import CORPUS_STUDY_ID, CorpusCandidate, Paper, make_session_factory
from sqlalchemy import select

from middleware import corpus_refresh, corpus_screen, semantic_scholar

LONG = "A controlled study of developers. " * 10  # a real-length abstract
CONFIG = {"curation": {**CURATION_DEFAULTS, "keepAt": 0.9, "hideBelow": 0.5}}
ON, OFF = [1.0, 0.05, 0.0], [0.0, 0.0, 1.0]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No test here reaches Mistral or Semantic Scholar."""

    def refuse(*args, **kwargs):
        raise AssertionError("network access in a test")

    monkeypatch.setattr(corpus_screen, "_urlopen", refuse)
    monkeypatch.setattr(semantic_scholar, "_urlopen", refuse)


@pytest.fixture
def sf(tmp_path):
    factory = make_session_factory(tmp_path / "screen.sqlite3")
    with factory() as s:
        for i in range(6):
            ref = f"corpus:seed-{i}"
            s.add(
                Paper(
                    study_id=CORPUS_STUDY_ID,
                    paper_ref=ref,
                    title=f"Seed about AI pair programming {i}",
                    abstract=LONG,
                    tier="A",
                    added_at="",
                )
            )
            store_embedding(s, ref, [1.0, 0.01 * i, 0.0], "2026-01-01T00:00:00Z")
        for ref, s2_id, title in (
            ("arxiv:2610.00001", "on", "Pair programming with an AI assistant"),
            ("arxiv:2610.00002", "off", "Crop yields under drought"),
            ("arxiv:2610.00003", "", "Brand-new preprint on AI pair programming"),
        ):
            s.add(
                CorpusCandidate(
                    ref=ref,
                    arxiv_id=ref.split(":")[1],
                    s2_id=s2_id or None,
                    title=title,
                    abstract=LONG,
                    year=2026,
                    source="arxiv",
                    run_id=1,
                    first_seen_at="",
                    score=1.0,
                )
            )
        s.commit()
    return factory


def _post(url, payload):
    """S2 batch: SPECTER2 vectors for the two papers it has embedded."""
    assert "embedding.specter_v2" in url
    vectors = {"on": ON, "off": OFF}
    return [
        {"paperId": i, "embedding": {"vector": vectors[i]}} if i in vectors else None
        for i in payload["ids"]
    ]


def _embed(texts):
    return [ON if "programming" in t else OFF for t in texts]


def test_candidates_are_screened_in_one_space_each(sf):
    embedded = []

    def embed(texts):
        embedded.append(texts)
        return _embed(texts)

    out = corpus_screen.screen_candidates(
        sf, config=CONFIG, post=_post, embed=embed, now=lambda: "2026-11-23T00:00:00Z"
    )
    assert (out["bySpecter2"], out["byMistralEmbed"]) == (2, 1)
    assert (out["admitted"], out["dismissed"], out["waiting"]) == (2, 1, 0)
    # Only the candidate S2 had no vector for went to mistral-embed.
    assert len(embedded) == 1 and embedded[0][-1].startswith("Brand-new preprint")
    with sf() as s:
        by_ref = {c.ref: c for c in s.query(CorpusCandidate)}
        assert by_ref["arxiv:2610.00001"].status == "accepted"
        assert by_ref["arxiv:2610.00002"].status == "dismissed"
        new = by_ref["arxiv:2610.00003"]
        assert new.status == "accepted" and "mistral-embed" in new.triage_reason
        row = s.query(Paper).filter_by(paper_ref="arxiv:2610.00003").one()
        assert row.added_via == "refresh-auto" and row.curation_by == "auto"
        # Existing corpus rows are never re-triaged by screening.
        assert {p.curation for p in s.query(Paper).filter_by(tier="A")} == {""}


def test_judged_candidates_are_not_screened_again_and_unjudged_ones_retry(sf):
    out = corpus_screen.screen_candidates(sf, config=CONFIG, post=_post, embed=None)
    assert out["byMistralEmbed"] == 0 and out["waiting"] == 1
    asked = []

    def post(url, payload):
        asked.extend(payload["ids"])
        return _post(url, payload)

    again = corpus_screen.screen_candidates(sf, config=CONFIG, post=post, embed=None)
    # Only the candidate nothing could judge is asked about again (S2 may have
    # embedded it by now); the two judged ones are left alone.
    assert asked == ["ARXIV:2610.00003"] and again["screened"] == 0
    assert again["waiting"] == 1


def test_mistral_embed_cutoffs_are_calibrated_in_its_own_space(sf):
    """Fixed keepAt/hideBelow are SPECTER2 similarities and must not be reused."""

    def unit(i):
        return [1.0 if j == i else 0.0 for j in range(8)]

    def mix(spread, i):  # the shared topic plus a little of direction ``i``
        return [a + spread * b for a, b in zip(unit(0), unit(i), strict=True)]

    def embed(texts):
        # Examples sit at cosine 0.8 to each other; every candidate at about 0.83
        # to them: inside the examples' own spread, below the fixed keepAt 0.9.
        out = []
        for t in texts:
            seed = next((i for i in range(6) if f"programming {i}" in t), None)
            out.append(mix(0.5, seed + 1) if seed is not None else mix(0.4, 7))
        return out

    nothing = lambda url, payload: [None] * len(payload["ids"])  # noqa: E731
    out = corpus_screen.screen_candidates(sf, config=CONFIG, post=nothing, embed=embed)
    assert out["byMistralEmbed"] == 3 and out["admitted"] == 3


def test_mistral_embed_never_dismisses_on_its_own(sf):
    """Its dismissal margin is unvalidated, so an off-topic paper waits for a
    person rather than disappearing."""
    nothing = lambda url, payload: [None] * len(payload["ids"])  # noqa: E731
    out = corpus_screen.screen_candidates(sf, config=CONFIG, post=nothing, embed=_embed)
    assert out["byMistralEmbed"] == 3 and out["dismissed"] == 0
    with sf() as s:
        drought = s.scalar(
            select(CorpusCandidate).where(CorpusCandidate.ref == "arxiv:2610.00002")
        )
        assert drought.status == "new"
        assert "left for a person" in drought.triage_reason


def test_s2_outage_leaves_candidates_for_mistral_or_review(sf):
    def down(url, payload):
        from middleware import semantic_scholar

        raise semantic_scholar.SemanticScholarError("HTTP 503", status=503)

    out = corpus_screen.screen_candidates(sf, config=CONFIG, post=down, embed=_embed)
    assert out["status"] == "partial" and out["byMistralEmbed"] == 3
    assert out["errors"][0]["source"] == "s2-batch"


# --- mistral-embed client


class _Res:
    def __init__(self, body, headers):
        self.body, self.headers = json.dumps(body).encode(), headers

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body


def test_embed_texts_batches_and_honours_rate_limit_headers(monkeypatch):
    calls, slept = [], []

    def opener(req, timeout):
        body = json.loads(req.data)
        calls.append(len(body["input"]))
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                req.full_url, 429, "busy", {"Retry-After": "3"}, io.BytesIO(b"")
            )
        headers = {
            "x-ratelimit-limit-req-minute": "60",
            "x-ratelimit-remaining-req-minute": "30" if len(calls) == 2 else "59",
        }
        data = [{"embedding": [float(i)]} for i in range(len(body["input"]))]
        return _Res({"data": data}, headers)

    monkeypatch.setattr(corpus_screen, "_urlopen", opener)
    monkeypatch.setattr(corpus_screen, "_sleep", slept.append)
    observed = {}
    vectors = corpus_screen.embed_texts(
        [f"t{i}" for i in range(20)], api_key="k", observed=observed
    )
    assert len(vectors) == 20 and calls == [16, 16, 4]
    # 429 waits its Retry-After; half the minute's quota spent pauses a minute.
    assert slept == [3.0, 60.0]
    assert observed == {"limitPerMinute": "60", "remaining": "59"}


def test_quota_wait_keeps_half_the_minute_free():
    assert corpus_screen._quota_wait({}) == 0.0
    headers = {"x-ratelimit-limit-req-minute": "60"}
    assert (
        corpus_screen._quota_wait({**headers, "x-ratelimit-remaining-req-minute": "31"})
        == 0.0
    )
    assert (
        corpus_screen._quota_wait({**headers, "x-ratelimit-remaining-req-minute": "30"})
        == 60.0
    )


@pytest.mark.parametrize(
    "key,base,usable",
    [
        ("k", "", True),
        ("k", "https://api.mistral.ai/v1", True),
        ("k", "http://127.0.0.1:11434/v1", False),
        ("", "", False),
    ],
)
def test_mistral_embed_only_runs_on_a_mistral_route(monkeypatch, key, base, usable):
    monkeypatch.setenv("LLM_API_KEY", key)
    monkeypatch.setenv("LLM_BASE_URL", base)
    assert (corpus_screen.mistral_embedder() is not None) is usable


def test_the_scheduled_job_refreshes_then_screens(sf, monkeypatch):
    monkeypatch.setattr(
        corpus_refresh, "run_once", lambda *a, **k: {"status": "ok", "newCandidates": 3}
    )
    screened = []
    monkeypatch.setattr(
        corpus_screen,
        "screen_candidates",
        lambda factory, **kw: screened.append(kw) or {"status": "ok"},
    )
    out = corpus_screen.scheduled_refresh(sf)
    assert out["refresh"]["status"] == "ok" and out["screening"] == {"status": "ok"}
    # conftest gives every test a Mistral key, so the job builds an embedder.
    assert "curation" in screened[0]["config"] and screened[0]["embed"] is not None

    def busy(*a, **k):
        raise corpus_refresh.RefreshInProgress("run 1 is still running")

    monkeypatch.setattr(corpus_refresh, "run_once", busy)
    assert corpus_screen.scheduled_refresh(sf)["refresh"]["status"] == "skipped"
