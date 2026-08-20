"""Abstract-backfill tests (D4): the corpus-enrich job."""

import pytest
from middleware.corpus_enrich import (
    ENRICH_FIELDS,
    enrich_abstracts,
    enrichment_status,
    s2_id_for_row,
    select_candidates,
)
from middleware.corpus_importer import MIN_REAL_ABSTRACT_CHARS
from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory

from middleware import paper_index

ABSTRACT = (
    "We ran a within-subjects experiment in which professional developers "
    "completed maintenance tasks with and without an AI coding assistant. "
    "Completion time, defect density and self-reported confidence were "
    "recorded for every task, and we report exact tests with effect sizes "
    "and per-cell counts throughout the analysis of the resulting data set."
)


def _rows():
    """Three harvested rows of descending score + one seed with only a DOI."""
    return [
        Paper(
            study_id=CORPUS_STUDY_ID,
            paper_ref="arxiv:2510.20703",
            title="Trust, But Verify",
            s2_id="s2-high",
            tier="B",
            score=18.0,
            added_at="",
        ),
        Paper(
            study_id=CORPUS_STUDY_ID,
            paper_ref="arxiv:2211.03622",
            title="Security Weaknesses of Generated Code",
            s2_id="s2-mid",
            tier="B",
            score=12.0,
            added_at="",
        ),
        Paper(
            study_id=CORPUS_STUDY_ID,
            paper_ref="arxiv:1111.00001",
            title="A Paper S2 No Longer Knows",
            s2_id="s2-stale",
            tier="B",
            score=3.0,
            added_at="",
        ),
        Paper(
            study_id=CORPUS_STUDY_ID,
            paper_ref="corpus:trust-in-ai-code-generation",
            title="Investigating and Designing for Trust",
            abstract="Developer over-reliance on AI-generated code.",
            curator_note="Developer over-reliance on AI-generated code.",
            doi="10.1145/3613904.3642706",
            tier="A",
            score=14.0,
            added_at="",
        ),
    ]


@pytest.fixture()
def db_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'corpus.sqlite3'}"
    factory = make_session_factory(url)
    with factory() as s:
        for row in _rows():
            s.add(row)
            paper_index.index_paper(s, row.paper_ref, row.title, row.abstract or "")
        s.commit()
    return url


class _Stub:
    """Stands in for ``semantic_scholar.post_json``; records what was asked."""

    def __init__(self, abstracts: dict[str, str]):
        self.abstracts = abstracts
        self.calls: list[dict] = []

    def __call__(self, url: str, payload: dict) -> list[dict | None]:
        self.calls.append({"url": url, "ids": list(payload["ids"])})
        out: list[dict | None] = []
        for sid in payload["ids"]:
            abstract = self.abstracts.get(sid)
            out.append(
                {"paperId": sid, "abstract": abstract} if abstract is not None else None
            )
        return out


def test_candidates_are_ordered_by_confidence(db_url):
    """
    The backfill spends its first calls on the papers most likely to be recommended — so
    a --limit run is a useful partial run.
    """
    factory = make_session_factory(db_url)
    with factory() as s:
        refs = [p.paper_ref for p in select_candidates(s)]
    assert refs[0] == "arxiv:2510.20703"
    assert refs[1] == "corpus:trust-in-ai-code-generation"
    assert refs[-1] == "arxiv:1111.00001"


def test_enrich_backfills_and_reindexes(db_url):
    post = _Stub(
        {
            "s2-high": ABSTRACT,
            "s2-mid": ABSTRACT,
            "DOI:10.1145/3613904.3642706": ABSTRACT,
        }
    )
    result = enrich_abstracts(db_url, post=post)

    assert result["candidates"] == 4
    assert result["enriched"] == 3
    assert result["unresolved"] == 1
    assert post.calls and ENRICH_FIELDS in post.calls[0]["url"]

    factory = make_session_factory(db_url)
    with factory() as s:
        rows = {p.paper_ref: p for p in s.query(Paper).all()}
        assert rows["arxiv:2510.20703"].abstract == ABSTRACT
        assert rows["arxiv:1111.00001"].abstract == ""
        seed = rows["corpus:trust-in-ai-code-generation"]
        assert seed.abstract == ABSTRACT
        assert seed.curator_note == "Developer over-reliance on AI-generated code."
        hits = paper_index.search(s, "maintenance tasks defect density", limit=5)
        assert "arxiv:2510.20703" in {h["paperRef"] for h in hits}

    status = enrichment_status(db_url)
    assert status["papers"] == 4 and status["withAbstract"] == 3


def test_enrich_is_idempotent_and_resumable(db_url):
    """A second run only re-attempts what is still missing."""
    post = _Stub({"s2-high": ABSTRACT})
    first = enrich_abstracts(db_url, post=post)
    assert first["enriched"] == 1

    post2 = _Stub({"s2-mid": ABSTRACT})
    second = enrich_abstracts(db_url, post=post2)
    assert second["candidates"] == 3
    assert second["enriched"] == 1
    assert "s2-high" not in [i for c in post2.calls for i in c["ids"]]


def test_limit_takes_the_highest_confidence_first(db_url):
    post = _Stub({"s2-high": ABSTRACT, "s2-mid": ABSTRACT})
    result = enrich_abstracts(db_url, limit=1, post=post)
    assert result["candidates"] == 1
    assert [i for c in post.calls for i in c["ids"]] == ["s2-high"]


def test_batches_respect_the_chunk_size(db_url):
    post = _Stub({"s2-high": ABSTRACT, "s2-mid": ABSTRACT})
    enrich_abstracts(db_url, batch_size=2, post=post)
    assert all(len(c["ids"]) <= 2 for c in post.calls)


def test_short_abstract_still_counts_as_missing(db_url):
    """
    A curator's one-liner is not an abstract — the seed stays a candidate until a real
    one lands.
    """
    factory = make_session_factory(db_url)
    with factory() as s:
        seed = (
            s.query(Paper)
            .filter_by(paper_ref="corpus:trust-in-ai-code-generation")
            .one()
        )
        assert len(seed.abstract) < MIN_REAL_ABSTRACT_CHARS
        assert seed.paper_ref in {p.paper_ref for p in select_candidates(s)}


def test_row_without_a_resolvable_id_is_skipped_not_guessed(db_url):
    factory = make_session_factory(db_url)
    with factory() as s:
        s.add(
            Paper(
                study_id=CORPUS_STUDY_ID,
                paper_ref="corpus:local-only-seed",
                title="A seed with no external id",
                tier="A",
                score=14.0,
                added_at="",
            )
        )
        s.commit()
        row = s.query(Paper).filter_by(paper_ref="corpus:local-only-seed").one()
        assert s2_id_for_row(row) == ""

    post = _Stub({"s2-high": ABSTRACT})
    result = enrich_abstracts(db_url, post=post)
    assert result["skipped_no_id"] == 1
    assert "corpus:local-only-seed" not in [i for c in post.calls for i in c["ids"]]
