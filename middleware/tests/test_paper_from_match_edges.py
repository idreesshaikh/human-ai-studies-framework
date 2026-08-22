"""A recommender-added paper lands connected, not isolated (live-review fix)."""

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.corpus_importer import VIA_EDGE_KIND
from middleware.db import (
    CORPUS_STUDY_ID,
    Paper,
    PaperEdge,
    make_session_factory,
)
from middleware.settings import Settings

from middleware import semantic_scholar

STUDY = "edge-study"
SEED = "corpus:trust-in-ai-code-generation"
NEW = "arxiv:2510.20703"
OTHER = "arxiv:2211.03622"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """
    S2 unreachable on purpose: whatever connectivity shows up is the corpus's own, not
    something fetched or fabricated.
    """

    def _no_network(*a, **k):
        raise semantic_scholar.SemanticScholarError("offline in tests")

    monkeypatch.setattr(semantic_scholar, "get_json", _no_network)

    settings = Settings(
        db_path=tmp_path / "edges.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    tc = TestClient(create_app(settings))
    factory = make_session_factory(f"sqlite:///{settings.db_path}")

    with factory() as s:
        for ref, title in (
            (SEED, "Investigating and Designing for Trust"),
            (NEW, "Trust, But Verify"),
            (OTHER, "Security Weaknesses of Generated Code"),
        ):
            s.add(
                Paper(
                    study_id=CORPUS_STUDY_ID,
                    paper_ref=ref,
                    title=title,
                    score=14.0,
                    added_at="",
                )
            )
        for dst in (NEW, OTHER):
            s.add(
                PaperEdge(
                    study_id=CORPUS_STUDY_ID,
                    src_ref=SEED,
                    dst_ref=dst,
                    kind=VIA_EDGE_KIND,
                    dst_title="harvested neighbour",
                )
            )
        for ref, title in ((SEED, "Investigating and Designing for Trust"),
                           (OTHER, "Security Weaknesses of Generated Code")):
            s.add(
                Paper(study_id=STUDY, paper_ref=ref, title=title, added_at="")
            )
        s.commit()
    return tc


def _add_from_match(client, ref: str) -> dict:
    res = client.post(
        f"/studies/{STUDY}/papers/from-match",
        json={"ref": ref, "matchReason": "Matches your terms: trust."},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_added_paper_arrives_with_edges(client):
    body = _add_from_match(client, NEW)
    assert body["edges"] >= 1

    graph = client.get(f"/studies/{STUDY}/papers/graph").json()
    touching = [e for e in graph["edges"] if NEW in (e["src"], e["dst"])]
    assert touching, "the added paper is still an isolated node"


def test_the_edge_is_shared_with_a_paper_the_study_already_holds(client):
    """
    The point of showing it: the new paper joins the existing constellation rather than
    floating beside it.
    """
    _add_from_match(client, NEW)
    graph = client.get(f"/studies/{STUDY}/papers/graph").json()
    ingested = {n["paperRef"] for n in graph["nodes"] if n["ingested"]}
    shared = [
        e
        for e in graph["edges"]
        if NEW in (e["src"], e["dst"])
        and {e["src"], e["dst"]} <= ingested
    ]
    assert shared, "no edge connects the new paper to a paper already in the study"
    assert {e["kind"] for e in shared} == {VIA_EDGE_KIND}


def test_no_edge_is_invented_when_the_corpus_has_none(client):
    """
    A corpus paper with no edges and no reachable S2 stays honestly unconnected
    -  added,
    but not wired up with a guess.
    """
    res = client.post(
        f"/studies/{STUDY}/papers/from-match",
        json={"ref": SEED, "matchReason": "already held"},
    )
    assert res.status_code == 200
    graph = client.get(f"/studies/{STUDY}/papers/graph").json()
    assert all(
        e["kind"] == VIA_EDGE_KIND for e in graph["edges"] if e["src"] == SEED
    )


def test_adding_twice_does_not_duplicate_edges(client):
    first = _add_from_match(client, NEW)
    second = _add_from_match(client, NEW)
    assert second["edges"] == 0
    graph = client.get(f"/studies/{STUDY}/papers/graph").json()
    keys = [(e["src"], e["dst"], e["kind"]) for e in graph["edges"]]
    assert len(keys) == len(set(keys))
    assert first["edges"] >= 1
