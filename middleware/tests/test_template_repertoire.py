"""Protocol-repertoire tests (D2/FR-TPL)."""

import pytest
from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory

from middleware import paper_index, template_registry, template_repertoire

_CORPUS = [
    (
        "arxiv:2507.09089",
        "Measuring the Impact of Early-2025 AI on Developer Productivity",
        "A randomized controlled trial in which experienced developers "
        "completed real tasks with and without AI assistance, within "
        "subjects and counterbalanced, measuring task completion time and "
        "self-reported perception of speed.",
        18.0,
    ),
    (
        "corpus:metr-early-2025-dev-productivity",
        "Measuring Early-2025 AI Impact on Developer Productivity",
        "Developers felt faster with AI while measurably slower.",
        14.0,
    ),
    (
        "arxiv:3000.00001",
        "A Within-Subjects Crossover Study of Assisted Programming",
        "Participants completed programming tasks in a counterbalanced "
        "crossover design; task completion time was compared within "
        "subjects using paired nonparametric tests with effect sizes.",
        16.0,
    ),
    (
        "arxiv:3000.00002",
        "Paired Task Completion Time Under AI Assistance",
        "A within-subjects randomized controlled trial measuring task "
        "completion time and perceived productivity for developers using an "
        "AI assistant on real maintenance tasks.",
        15.0,
    ),
    (
        "arxiv:3000.00003",
        "An Unrelated Paper About Compiler Optimization",
        "We describe loop unrolling heuristics in an optimizing compiler.",
        2.0,
    ),
]


@pytest.fixture()
def session(tmp_path):
    template_repertoire.clear_cache()
    factory = make_session_factory(f"sqlite:///{tmp_path / 'rep.sqlite3'}")
    with factory() as s:
        for ref, title, abstract, score in _CORPUS:
            s.add(
                Paper(
                    study_id=CORPUS_STUDY_ID,
                    paper_ref=ref,
                    title=title,
                    abstract=abstract,
                    score=score,
                    added_at="",
                )
            )
            paper_index.index_paper(s, ref, title, abstract)
        s.commit()
        yield s
    template_repertoire.clear_cache()


def test_signature_describes_the_shape_not_the_paper(session):
    """
    A shape's signature is design vocabulary  -  if it were built from the source paper's
    title or prose, the template would collapse back into a replica of that one paper
    and every topical paper would 'use' it.
    """
    template = template_registry.load_template("metr-rct-v1")
    signature = template_repertoire.design_signature(template)
    assert "within-subjects" in signature
    assert not any("early-2025" in phrase for phrase in signature)
    assert not any("developer" in phrase for phrase in signature)


def test_signature_falls_back_to_design_type_and_tests():
    """A template with no curated signature still gets a narrow one."""
    signature = template_repertoire.design_signature(
        {
            "designType": "rct-between-subjects",
            "statisticalPlan": {"perRQ": [{"test": "mann-whitney-u"}]},
        }
    )
    assert signature == ["mann whitney u", "rct between subjects"]


def test_references_rank_papers_that_used_the_design(session):
    template = template_registry.load_template("metr-rct-v1")
    found = template_repertoire.references_for(session, template)
    refs = [r["ref"] for r in found["references"]]

    assert refs[0] == "arxiv:2507.09089"
    assert found["references"][0]["role"] == "primary-design"
    users = [r for r in found["references"] if r["role"] == "uses-this-design"]
    assert users
    assert "within-subjects" in users[0]["matchReason"]
    # The unrelated compiler paper never mentions the design vocabulary.
    assert "arxiv:3000.00003" not in refs
    assert found["support"] >= 3


def test_every_reference_clears_the_confidence_gate(session):
    template = template_registry.load_template("metr-rct-v1")
    found = template_repertoire.references_for(session, template)
    for ref in found["references"]:
        if ref["role"] == "uses-this-design":
            gate = template_repertoire.MIN_REFERENCE_CONFIDENCE
            assert (ref["confidence"] or 0) >= gate


def test_support_is_a_census_not_a_topical_match(session):
    """
    The compiler paper shares no design vocabulary, so it supports nothing; a paper is
    support for a shape only if it says so.
    """
    entries = template_repertoire.rank_repertoire(session, use_cache=False)
    for entry in entries:
        assert all(r["ref"] != "arxiv:3000.00003" for r in entry["references"])
    survey = next(e for e in entries if e["id"] == "survey-self-report-v1")
    crossover = next(e for e in entries if e["id"] == "within-subjects-crossover-v1")
    assert crossover["support"] > survey["support"]


def test_repertoire_is_ranked_common_to_rare(session):
    entries = template_repertoire.rank_repertoire(session, use_cache=False)
    supports = [e["support"] for e in entries]
    assert supports == sorted(supports, reverse=True)
    assert entries[0]["band"] in ("common", "established", "rare")
    assert all("references" in e for e in entries)


def test_ranking_is_deterministic(session):
    """No LLM decides which design is common  -  two runs rank identically."""
    first = template_repertoire.rank_repertoire(session, use_cache=False)
    second = template_repertoire.rank_repertoire(session, use_cache=False)
    assert [e["id"] for e in first] == [e["id"] for e in second]
    assert [e["support"] for e in first] == [e["support"] for e in second]


def test_rare_design_needs_a_strong_source_to_be_admitted():
    """Below the support floor, admission turns on the best reference."""
    weak = [{"confidence": 0.4}]
    strong = [{"confidence": 0.95}]
    assert template_repertoire._admission(1, strong)[0] is True
    admitted, note = template_repertoire._admission(1, weak)
    assert admitted is False
    assert "confidence" in note
    assert template_repertoire._admission(template_repertoire.RARE_SUPPORT_FLOOR, [])[0]


def test_declared_source_missing_from_the_corpus_is_reported_not_invented(session):
    template = {
        "templateId": "fake-v1",
        "title": "A shape citing a paper we do not hold",
        "description": "within-subjects crossover",
        "source": [{"paperRef": "doi:10.0000/not-in-corpus", "role": "primary-design"}],
    }
    found = template_repertoire.references_for(session, template)
    assert found["unresolved"] == ["doi:10.0000/not-in-corpus"]
    assert all(r["ref"] != "doi:10.0000/not-in-corpus" for r in found["references"])
