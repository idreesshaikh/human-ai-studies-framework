"""
Runtime template composition (FR-TPL): merging templates into one novel protocol, and
deriving a paper-specialised template from an archetype.
"""

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.db import CORPUS_STUDY_ID, Paper, make_session_factory
from middleware.settings import Settings
from protocol.loader import validate_protocol

from middleware import paper_index
from middleware import template_registry as tr


@pytest.fixture()
def client_tpl(tmp_path) -> TestClient:
    """
    A middleware with one corpus paper, so the paper-keyed template routes have
    something real to resolve.
    """
    settings = Settings(
        db_path=tmp_path / "tpl.sqlite3",
        data_dir=tmp_path / "data",
        spa_dist=tmp_path / "no-dist",
    )
    factory = make_session_factory(f"sqlite:///{settings.db_path}")
    with factory() as s:
        s.add(
            Paper(
                study_id=CORPUS_STUDY_ID,
                paper_ref="corpus:ai-assistants-in-practice",
                title="AI Assistants in Practice",
                abstract="How developers work alongside AI coding assistants.",
                tier="A",
                added_at="",
            )
        )
        paper_index.index_paper(
            s,
            "corpus:ai-assistants-in-practice",
            "AI Assistants in Practice",
            "How developers work alongside AI coding assistants.",
        )
        s.commit()
    return TestClient(create_app(settings))


def test_merge_two_templates_yields_valid_protocol_with_renumbered_rqs():
    result = tr.merge_templates(["metr-rct-v1", "survey-self-report-v1"], {})
    proto = result["protocol"]

    assert validate_protocol(proto) == []

    # RQs from both templates, renumbered sequentially so ids can't collide.
    ids = [rq["id"] for rq in proto["researchQuestions"]]
    assert ids == [f"RQ-{i}" for i in range(1, len(ids) + 1)]
    assert len(ids) >= 4

    covered = {e["rq"] for e in proto["analysisPlan"]}
    assert set(ids) <= covered

    contributed = {s["templateId"] for s in result["sources"]}
    assert contributed == {"metr-rct-v1", "survey-self-report-v1"}
    all_papers = {p for s in result["sources"] for p in s["papers"]}
    assert "corpus:ai-assistants-in-practice" in all_papers


def test_merge_remaps_literature_justifies_to_new_rq_ids():
    # A borrowed template's literature must point at the RENUMBERED rq ids, never a
    # stale id from before the merge.
    proto = tr.merge_templates(["metr-rct-v1", "survey-self-report-v1"], {})["protocol"]
    valid_ids = {rq["id"] for rq in proto["researchQuestions"]}
    for lit in proto["literature"]:
        for rq_id in lit.get("justifies", []):
            assert rq_id in valid_ids


def test_merge_needs_at_least_two():
    with pytest.raises(tr.TemplateError):
        tr.merge_templates(["metr-rct-v1"], {})


def test_derive_from_paper_leads_provenance_and_stays_valid():
    t = tr.derive_template_from_paper(
        "corpus:grounded-copilot", "metr-rct-v1", title="Grounded Copilot"
    )
    assert t["source"][0]["paperRef"] == "corpus:grounded-copilot"
    assert t["templateId"] != "metr-rct-v1"
    vals = tr.resolve_parameters(t, {})
    proto = tr._fill(t["protocolSkeleton"], vals)
    assert validate_protocol(proto) == []


def test_a_paper_derived_template_instantiates_to_a_valid_protocol():
    """Deriving from a paper has to end somewhere a study can start."""
    derived = tr.derive_template_from_paper(
        "corpus:some-paper", "metr-rct-v1", title="A Paper", year=2026
    )
    out = tr.instantiate_doc(derived, {})

    assert validate_protocol(out["protocol"]) == []
    assert out["templateId"] == derived["templateId"]
    assert derived["source"][0]["paperRef"] == "corpus:some-paper"


def test_from_paper_route_hands_back_a_protocol_to_start_from(client_tpl):
    """
    The route carries the protocol, not just the template — otherwise the UI has a card
    it can display and nothing it can act on.
    """
    hits = client_tpl.get("/corpus/search?q=ai").json()["results"]
    assert hits, "the compose fixture needs at least one corpus paper"
    res = client_tpl.post(
        "/templates/from-paper",
        json={"paperRef": hits[0]["ref"], "baseTemplateId": "metr-rct-v1"},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert "protocol" in body, "no protocol to seed a study with"
    assert isinstance(body["protocol"].get("study"), dict)
    assert isinstance(body["protocol"].get("researchQuestions"), list)
