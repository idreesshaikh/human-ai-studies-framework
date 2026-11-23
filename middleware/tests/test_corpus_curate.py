import numpy as np
import pytest
from middleware.corpus_curate import (
    CurationError,
    Cutoffs,
    _apply_to_row,
    leave_one_out,
    run,
    store_embedding,
    triage,
    triage_all,
)
from middleware.corpus_refresh import CURATION_DEFAULTS
from middleware.db import (
    CORPUS_STUDY_ID,
    CorpusCurationRun,
    Paper,
    make_session_factory,
)


def test_leave_one_out_never_counts_the_paper_itself():
    examples = np.eye(5)
    assert np.allclose(leave_one_out(examples, 20), 0)
    with pytest.raises(CurationError):
        leave_one_out(examples[:1], 1)


def test_missing_embedding_goes_to_review_even_if_metadata_is_incomplete():
    decision, reason = triage(
        relevance=None,
        nearest_example=None,
        nearest_counter=None,
        weak=["no abstract"],
        cutoffs=Cutoffs(0.7, 0.6, "test"),
    )
    assert decision == "review"
    assert "no embedding" in reason and "no abstract" in reason


def test_dry_run_reports_when_triage_cannot_run(tmp_path):
    factory = make_session_factory(tmp_path / "curation.sqlite3")
    result = run(factory, config={}, dry_run=True)
    assert result["status"] == "failed"
    assert "no example paper" in result["triageSkipped"]
    with factory() as session:
        assert session.query(CorpusCurationRun).count() == 0


def test_incomplete_metadata_does_not_erase_citation_counts():
    row = Paper(
        study_id=CORPUS_STUDY_ID,
        paper_ref="paper",
        citation_count=12,
        influential_citation_count=3,
        added_at="",
    )
    _apply_to_row(
        row, {"citationCount": None, "influentialCitationCount": None}, "now", {}
    )
    assert row.citation_count == 12
    assert row.influential_citation_count == 3


def test_invalid_or_incompatible_embeddings_are_not_stored(tmp_path):
    factory = make_session_factory(tmp_path / "curation.sqlite3")
    with factory() as session:
        assert store_embedding(session, "good", [1.0, 0.0], "now")
        assert not store_embedding(session, "nan", [float("nan"), 1.0], "now")
        assert not store_embedding(session, "zero", [0.0, 0.0], "now")
        assert not store_embedding(session, "other-size", [1.0, 0.0, 0.0], "now")


def test_curation_preserves_human_decisions_and_reviews_unscored_papers(tmp_path):
    factory = make_session_factory(tmp_path / "curation.sqlite3")
    with factory() as session:
        for i, vector in enumerate(np.eye(5)):
            ref = f"seed:{i}"
            session.add(
                Paper(study_id=CORPUS_STUDY_ID, paper_ref=ref, tier="A", added_at="")
            )
            store_embedding(session, ref, vector.tolist(), "2026-01-01T00:00:00Z")
        session.add_all(
            [
                Paper(study_id=CORPUS_STUDY_ID, paper_ref="unscored", added_at=""),
                Paper(
                    study_id=CORPUS_STUDY_ID,
                    paper_ref="chosen",
                    curation="keep",
                    curation_by="human:researcher",
                    added_at="",
                ),
            ]
        )
        session.flush()
        triage_all(
            session, CURATION_DEFAULTS, this_year=2026, now="2026-01-01T00:00:00Z"
        )
        papers = {row.paper_ref: row for row in session.query(Paper).all()}
        assert papers["unscored"].curation == "review"
        assert papers["chosen"].curation == "keep"
        assert papers["chosen"].curation_by == "human:researcher"
