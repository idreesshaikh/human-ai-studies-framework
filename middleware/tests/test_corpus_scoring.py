"""Literature screening and relevance ranking protect usable, verifiable evidence."""

from middleware.corpus_scoring import candidate_score, quality_gate, score


def test_screening_requires_identifiable_recent_or_cited_literature():
    recent = {
        "title": "AI-assisted software maintenance",
        "year": 2026,
        "citationCount": 0,
        "externalIds": {"ArXiv": "2610.1"},
    }
    assert quality_gate(recent, 2026)
    assert not quality_gate({**recent, "externalIds": {}}, 2026)
    assert not quality_gate({**recent, "title": ""}, 2026)
    assert not quality_gate({**recent, "year": None}, 2026)
    assert not quality_gate({**recent, "year": 2016, "citationCount": 50}, 2026)
    assert quality_gate({**recent, "year": 2016, "citationCount": 100}, 2026)
    assert not quality_gate({**recent, "year": 2024, "citationCount": 2}, 2026)
    assert quality_gate({**recent, "year": 2024, "citationCount": 3}, 2026)


def test_ranking_rewards_relevance_signals_and_bounds_graph_support():
    paper = {"year": 2026, "citationCount": 0, "venue": ""}
    baseline = score(paper, 0, 2026)
    assert score({**paper, "citationCount": 20}, 0, 2026) > baseline
    assert (
        score({**paper, "openAccessPdf": {"url": "https://example.org/paper"}}, 0, 2026)
        > baseline
    )
    assert score({**paper, "venue": "ICSE 2026"}, 0, 2026) > score(
        {**paper, "venue": "Unknown venue"}, 0, 2026
    )
    assert score(paper, 3, 2026) > baseline
    assert score(paper, 6, 2026) == score(paper, 100, 2026)
    candidate = {**paper, "arxivId": "2610.1", "citationCount": None}
    assert candidate_score(candidate, 2026) > candidate_score(paper, 2026)
    assert candidate_score({"year": None, "venue": ""}, 2026) >= 0
