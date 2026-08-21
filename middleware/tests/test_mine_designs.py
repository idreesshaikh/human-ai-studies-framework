"""
Corpus-mining pipeline tests (FR-TPL-5): every draft the miner produces must
validate against the real template schema, and a qualifying draft must reach
the review queue as a `pending`/`mined` `TemplateSubmission` — the two
guarantees `scripts/mine_templates.py` relies on.

Before the fixes in this file's companion change, `infer_design_type` and
`draft_template_yaml` produced values the schema has never accepted
(`designType: "empirical-study"`, `dataPath: "archive"`, `effectSize:
"cohens-d"`, and a `statisticalPlan.test` that was actually a recipe id) —
confirmed by running the miner against the real 15k-paper corpus: 28 clusters
with 3+ papers, 0 valid. These tests pin the fix with synthetic data so a
future change can't silently regress it without a real corpus on hand.
"""

from __future__ import annotations

import pytest
from middleware import mine_designs, template_registry
from middleware.db import Paper, TemplateSubmission, CORPUS_STUDY_ID, make_session_factory


def _paper(ref: str, title: str, abstract: str) -> Paper:
    return Paper(
        study_id=CORPUS_STUDY_ID,
        paper_ref=ref,
        title=title,
        abstract=abstract,
        score=0.8,
        added_at="2026-01-01T00:00:00.000Z",
    )


@pytest.fixture
def session(tmp_path):
    sf = make_session_factory(tmp_path / "mine.sqlite3")
    s = sf()
    # A cluster with real, distinct multi-phrase support (3 papers, matching
    # "between subjects" + "control group" + "randomly assigned") — the shape
    # of cluster the miner is meant to surface.
    for i in range(3):
        s.add(
            _paper(
                f"corpus:paper-{i}",
                f"An RCT Comparing AI Assistance {i}",
                "Participants were randomly assigned to a control group or "
                "a treatment condition in a between subjects design.",
            )
        )
    # A within-subjects/crossover cluster, 3 papers.
    for i in range(3):
        s.add(
            _paper(
                f"corpus:crossover-{i}",
                f"Crossover Study of Code Review {i}",
                "A within subjects crossover with counterbalanced order.",
            )
        )
    s.commit()
    yield s
    s.close()


@pytest.mark.parametrize(
    "phrases,expected",
    [
        (frozenset({"between-subject", "randomized"}), "rct-between-subjects"),
        (frozenset({"between-subject"}), "observational"),
        (frozenset({"within-subject", "crossover"}), "rct-within-subjects"),
        (frozenset({"within-subject"}), "quasi-experiment"),
        (frozenset({"field study"}), "observational"),
        (frozenset({"survey"}), "survey"),
        (frozenset({"single-arm"}), "case-study"),
        (frozenset({"benchmark evaluation"}), "case-study"),
        (frozenset({"nothing recognizable"}), "lab-experiment"),
    ],
)
def test_infer_design_type_only_returns_real_schema_values(phrases, expected):
    """
    Every branch must land on one of the schema's nine real `designType`
    values — the bug this pins is `infer_design_type` returning slugs like
    "empirical-study" or "crossover-design" that were never in the enum at
    all, so every mined draft failed validation before it could even be
    read for its actual content.
    """
    schema_enum = {
        "lab-experiment", "field-study", "survey", "rct-within-subjects",
        "rct-between-subjects", "quasi-experiment", "observational",
        "case-study", "simulation",
    }
    result = mine_designs.infer_design_type(phrases)
    assert result in schema_enum
    assert result == expected


def test_draft_template_yaml_validates(session):
    """A drafted template must pass the same validator a hand-authored one does."""
    clusters = mine_designs.cluster_papers_by_designs(session)
    top = mine_designs.identify_top_clusters(clusters, min_papers=3)
    assert top, "the fixture corpus should produce at least one 3+ paper cluster"

    for phrases, count in top:
        design_type = mine_designs.infer_design_type(phrases)
        recipe = mine_designs.infer_analysis_recipe(phrases)
        draft = mine_designs.draft_template_yaml(
            "mined-test-v1", phrases, clusters[phrases], design_type, recipe
        )
        problems = template_registry.validate_template(draft)
        assert problems == [], f"{phrases}: {problems}"

        # The statistical test must be a real test name, not the recipe id
        # reused verbatim (the original bug: `test: "two-group-nonparametric"`,
        # a recipe id, where the schema wants a test like "mann-whitney-u").
        test_name = draft["statisticalPlan"]["perRQ"][0]["test"]
        assert test_name != recipe
        assert test_name in {"mann-whitney-u", "wilcoxon-signed-rank"}


def test_mine_and_draft_end_to_end(session):
    drafts = mine_designs.mine_and_draft(session, write_files=False)
    assert drafts
    assert all(d["valid"] for d in drafts), [d["problems"] for d in drafts if not d["valid"]]


def test_uncovered_phrases_finds_designs_the_registry_does_not_claim(session):
    """
    The blind-spot report: a methodology phrase with real corpus support that
    no template's `designSignature` claims. This is what the fixed keyword
    table in `DESIGN_KEYWORDS` structurally cannot do — it only ever re-finds
    what someone already wrote into it, so an archetype nobody thought to name
    stays invisible however many papers use it.
    """
    for i in range(6):
        session.add(
            _paper(
                f"corpus:diary-{i}",
                f"A Diary Study of AI Assistance {i}",
                "We report a diary study of developers over three weeks.",
            )
        )
    session.commit()

    gaps = mine_designs.uncovered_methodology_phrases(session, min_papers=5)
    phrases = {g["phrase"] for g in gaps}
    assert "diary study" in phrases, phrases
    # It reports support, so a reviewer can rank what to author first.
    assert next(g["papers"] for g in gaps if g["phrase"] == "diary study") >= 5

    # A phrase an existing template already claims is not a gap. Every registry
    # template's signature is excluded by construction.
    covered = {
        p.lower()
        for tpl in template_registry.list_templates()
        for p in (tpl.get("designSignature") or [])
    }
    assert not (phrases & covered)


def test_uncovered_phrases_drops_leading_articles(session):
    """
    "a case study" / "the case study" / "case study" are one finding, not three
    competing for the same slot in a ranked report.
    """
    assert mine_designs._normalise_phrase("an empirical study") == "empirical study"
    assert mine_designs._normalise_phrase("the field experiment") == "field experiment"
    # Nothing meaningful left once the noise is gone.
    assert mine_designs._normalise_phrase("the study") == ""


def test_submit_drafts_only_queues_valid_ones_as_pending_mined(session):
    drafts = mine_designs.mine_and_draft(session, write_files=False)
    ids = mine_designs.submit_drafts(session, drafts)
    assert ids

    rows = session.query(TemplateSubmission).filter(TemplateSubmission.id.in_(ids)).all()
    assert len(rows) == len(ids)
    for row in rows:
        assert row.status == "pending"
        assert row.source == "mined"
        assert row.submitter_sub == "system:miner"
