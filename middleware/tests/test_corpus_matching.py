"""Corpus import + matching-ladder tests."""

import pytest
from middleware.corpus_importer import VIA_EDGE_KIND
from middleware.db import CORPUS_STUDY_ID, Paper, PaperEdge, make_session_factory

from middleware import matching, paper_index

_TIER_A = [
    (
        "corpus:trust-in-ai-code-generation",
        "Investigating and Designing for Trust in AI-powered Code Generation",
        "Developer over-reliance on and trust in AI-generated code.",
    ),
    (
        "corpus:insecure-code-with-ai-assistants",
        "Do Users Write More Insecure Code with AI Assistants?",
        "Accepted AI code carries security defects developers miss.",
    ),
    (
        "corpus:metr-early-2025-dev-productivity",
        "Measuring Early-2025 AI Impact on Developer Productivity",
        "Developers felt faster with AI while measurably slower.",
    ),
]
_TIER_B = [
    (
        "arxiv:2510.20703",
        "Trust, But Verify: Evaluating AI-Generated Code",
        "corpus:trust-in-ai-code-generation",
    ),
    (
        "arxiv:2211.03622",
        "Security Weaknesses of Copilot-Generated Code",
        "corpus:insecure-code-with-ai-assistants",
    ),
]


@pytest.fixture()
def session(tmp_path):
    factory = make_session_factory(f"sqlite:///{tmp_path / 'corpus.sqlite3'}")
    with factory() as s:
        for ref, title, why in _TIER_A:
            s.add(
                Paper(
                    study_id=CORPUS_STUDY_ID,
                    paper_ref=ref,
                    title=title,
                    abstract=why,
                    tier="A",
                    added_at="",
                )
            )
            paper_index.index_paper(s, ref, title, why)
        for ref, title, via in _TIER_B:
            s.add(
                Paper(
                    study_id=CORPUS_STUDY_ID,
                    paper_ref=ref,
                    title=title,
                    tier="B",
                    added_at="",
                )
            )
            paper_index.index_paper(s, ref, title, "")
            s.add(
                PaperEdge(
                    study_id=CORPUS_STUDY_ID,
                    src_ref=via,
                    dst_ref=ref,
                    kind=VIA_EDGE_KIND,
                    dst_title=title,
                )
            )
        s.commit()
        yield s


def test_rows_land_with_tiers(session):
    """F8.4: papers land as Paper rows carrying their tier."""
    a = session.query(Paper).filter_by(study_id=CORPUS_STUDY_ID, tier="A").count()
    b = session.query(Paper).filter_by(study_id=CORPUS_STUDY_ID, tier="B").count()
    assert a == 3 and b == 2


def test_match_surfaces_demo_papers_no_llm(session):
    """
    F9.1/F9.2: with no LLM key the ladder still surfaces the trust + insecure papers,
    with matched-term reasons.
    """
    results = matching.match_papers(
        session,
        "junior developers over-trust AI-generated code",
        study_id="s",
        limit=5,
        use_llm=False,
    )
    refs = {r["ref"] for r in results}
    assert "corpus:trust-in-ai-code-generation" in refs
    assert "corpus:insecure-code-with-ai-assistants" in refs
    for r in results:
        assert r["matchReason"], "every recommendation carries a visible reason"


def test_match_never_invents_a_paper(session):
    """Honesty: every returned ref is a paper the store actually holds."""
    results = matching.match_papers(
        session, "trust and security in AI code", study_id="s", limit=10, use_llm=False
    )
    held = {ref for (ref,) in session.query(Paper.paper_ref).all()}
    assert {r["ref"] for r in results} <= held


def test_grounding_lookup_resolves_corpus_seed(session):
    """
    FR-CONV-2.2: grounding resolves against the corpus for any study, and carries
    confidence (not a provenance tier  -  the tier system is removed from ranking and
    output).
    """
    meta = matching.get_paper_metadata(
        session, "corpus:metr-early-2025-dev-productivity"
    )
    assert meta is not None
    assert "tier" not in meta
    assert "confidence" in meta


def test_corpus_search_path_returns_confidence_ranked_hits(session):
    """
    The /corpus/search endpoint's exact call  -  no study, corpus-only  -  used by the
    'turn a paper into a template' picker.
    """
    results = matching.match_papers(
        session, "trust in ai generated code", study_id=None, limit=8, use_llm=False
    )
    assert results, "a corpus-only search should surface matching papers"
    assert all("confidence" in r for r in results)
    assert matching.get_paper_metadata(session, "arxiv:9999.99999") is None


def test_query_expansion_degrades_to_raw_query_without_a_key(monkeypatch):
    """
    Semantic expansion (FR-LIT-9) is best-effort: with no LLM key it returns the query
    unchanged, so keyword FTS stays the floor (NFR-4).
    """
    from middleware import assistant

    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: None)
    q = "will AI make developers lazy"
    assert matching.expand_query(q) == q
