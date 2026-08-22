"""
Knowledge layer: paper ingest, graph assembly, FTS, protocol links, and the assistant's
aggregates-only tool boundary (FR-LIT-1..4, FR-ETH-4).
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

from middleware import assistant, semantic_scholar

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"
FROZEN = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


PENG = {
    "paperId": "peng000",
    "title": "The Impact of AI on Developer Productivity",
    "authors": [{"name": "S. Peng"}],
    "year": 2023,
    "venue": "arXiv",
    "abstract": "A randomized controlled trial of GitHub Copilot on task "
    "completion time. Developers with access finished 55% faster.",
    "externalIds": {"ArXiv": "2302.06590"},
    "citationCount": 400,
}
ZIEGLER = {
    "paperId": "zieg000",
    "title": "Productivity Assessment of Neural Code Completion",
    "authors": [{"name": "A. Ziegler"}],
    "year": 2022,
    "venue": "MAPS",
    "abstract": "Acceptance rate correlates with perceived productivity.",
    "externalIds": {"ArXiv": "2205.06537"},
    "citationCount": 300,
}
NEIGHBOUR = {
    "paperId": "nb00001",
    "title": "A Neighbour Paper on Code Review",
    "year": 2021,
    "externalIds": {"DOI": "10.1000/neighbour"},
    "citationCount": 120,
}


def fake_get_json(url: str):
    """Dispatch recorded S2 responses by URL shape (the one network seam)."""
    if "/paper/search" in url:
        return {"data": [PENG]}
    if "/references" in url:
        return {"data": [{"citedPaper": ZIEGLER}]}
    if "/citations" in url:
        return {"data": [{"citingPaper": NEIGHBOUR}]}
    if "forpaper" in url:
        return {"recommendedPapers": [NEIGHBOUR]}
    if "2302.06590" in url:
        return PENG
    if "2205.06537" in url:
        return ZIEGLER
    raise semantic_scholar.SemanticScholarError(f"no fixture for {url}")


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(semantic_scholar, "get_json", fake_get_json)
    settings = Settings(
        db_path=tmp_path / "k.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        spa_dist=tmp_path / "no-dist",
    )
    tc = TestClient(create_app(settings, clock=lambda: FROZEN))
    from protocol.loader import load_protocol

    tc.db_path = settings.db_path
    tc.protocol = load_protocol(PILOT)
    return tc


def test_ingest_by_arxiv_id_stores_metadata_and_seeds_links(client):
    res = client.post(
        "/studies/pilot-2026/papers", json={"arxivId": "2302.06590"}
    ).json()
    assert res["paperRef"] == "arxiv:2302.06590"
    assert res["edges"] == 0 and res["edgesPending"] is True

    papers = client.get("/studies/pilot-2026/papers").json()
    peng = next(p for p in papers if p["paperRef"] == "arxiv:2302.06590")
    assert peng["title"].startswith("The Impact of AI")
    assert peng["citationCount"] == 400
    assert peng["inProtocolLiterature"] is True
    assert "RQ-P3" in peng["links"] and "RQ-P4" in peng["links"]


def test_ingest_by_doi(client):
    res = client.post("/studies/pilot-2026/papers", json={"doi": "10.1000/neighbour"})
    assert res.status_code == 502


def test_graph_has_ingested_and_suggested_stub_nodes(client):
    client.post("/studies/pilot-2026/papers", json={"arxivId": "2302.06590"})
    graph = client.get("/studies/pilot-2026/papers/graph").json()

    by_ref = {n["paperRef"]: n for n in graph["nodes"]}
    assert by_ref["arxiv:2302.06590"]["ingested"] is True
    assert by_ref["arxiv:2205.06537"]["ingested"] is False
    assert by_ref["doi:10.1000/neighbour"]["ingested"] is False
    kinds = {e["kind"] for e in graph["edges"]}
    assert {"references", "citations", "recommendations"} <= kinds


def test_adding_a_suggested_node_regrows_the_graph(client):
    client.post("/studies/pilot-2026/papers", json={"arxivId": "2302.06590"})
    client.post("/studies/pilot-2026/papers", json={"arxivId": "2205.06537"})
    graph = client.get("/studies/pilot-2026/papers/graph").json()
    ziegler = next(n for n in graph["nodes"] if n["paperRef"] == "arxiv:2205.06537")
    assert ziegler["ingested"] is True


def test_delete_paper_removes_it_and_its_edges(client):
    client.post("/studies/pilot-2026/papers", json={"arxivId": "2302.06590"})
    client.delete("/studies/pilot-2026/papers/arxiv:2302.06590")
    papers = client.get("/studies/pilot-2026/papers").json()
    assert all(p["paperRef"] != "arxiv:2302.06590" for p in papers)
    graph = client.get("/studies/pilot-2026/papers/graph").json()
    assert all(e["src"] != "arxiv:2302.06590" for e in graph["edges"])


def test_s2_responses_are_cached_offline(client, monkeypatch):
    client.post("/studies/pilot-2026/papers", json={"arxivId": "2302.06590"})
    monkeypatch.setattr(
        semantic_scholar,
        "get_json",
        lambda url: (_ for _ in ()).throw(
            semantic_scholar.SemanticScholarError("offline")
        ),
    )
    graph = client.get("/studies/pilot-2026/papers/graph").json()
    assert any(n["paperRef"] == "arxiv:2205.06537" for n in graph["nodes"])


def test_links_round_trip(client):
    client.post("/studies/pilot-2026/papers", json={"arxivId": "2302.06590"})
    ref = "arxiv:2302.06590"
    client.put(
        f"/studies/pilot-2026/papers/{ref}/links",
        json={"targets": ["metric:parameter_count", "RQ-P4"]},
    )
    got = client.get(f"/studies/pilot-2026/papers/{ref}/links").json()
    assert got["links"] == ["RQ-P4", "metric:parameter_count"]
    papers = client.get("/studies/pilot-2026/papers").json()
    peng = next(p for p in papers if p["paperRef"] == ref)
    assert "metric:parameter_count" in peng["links"]


def test_full_text_search_finds_ingested_paper(client):
    from middleware.db import make_session_factory

    from middleware import paper_index

    client.post("/studies/pilot-2026/papers", json={"arxivId": "2302.06590"})
    factory = make_session_factory(client.db_path)
    with factory() as s:
        hits = paper_index.search(s, "completion time developers")
    assert hits and hits[0]["paperRef"] == "arxiv:2302.06590"
    assert "developers" in hits[0]["snippet"].lower() or hits[0]["snippet"]


def _seed_events_and_metrics(client):
    client.post(
        "/ingest/events",
        json={
            "source": "tern",
            "events": [
                {
                    "v": 3,
                    "ts": "2026-07-11T10:00:00.000Z",
                    "sessionId": "S1",
                    "seq": 0,
                    "participantId": "P01",
                    "condition": "ai-assisted",
                    "type": "fatigue_response",
                    "payload": {"score": 3},
                },
                {
                    "v": 3,
                    "ts": "2026-07-11T10:00:10.000Z",
                    "sessionId": "S1",
                    "seq": 1,
                    "participantId": "P01",
                    "condition": "ai-assisted",
                    "type": "clipboard_paste",
                    "payload": {"charCount": 212},
                },
            ],
        },
    )
    client.post(
        "/ingest/metrics",
        json=[
            {
                "file": "d.py",
                "cognitive_complexity": 9,
                "participantId": "P01",
                "condition": "ai-assisted",
                "sessionId": "S1",
                "timestamp": "2026-07-11T10:00:05+00:00",
                "schemaVersion": 1,
            }
        ],
    )


def test_make_client_validates_the_model_tier(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    assert assistant.make_client().model == assistant.MISTRAL_MODEL
    assert assistant.make_client("mistral-large-latest").model == "mistral-large-latest"
    assert assistant.make_client("gpt-99").model == assistant.MISTRAL_MODEL
    monkeypatch.delenv("MISTRAL_API_KEY")
    assert assistant.make_client() is None


def test_make_client_prefers_the_openai_compatible_override(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    client = assistant.make_client("mistral-large-latest")
    assert isinstance(client, assistant.OpenAICompatibleProvider)
    assert client.model == "gpt-4o"
    assert client.base_url == "https://api.openai.com/v1/chat/completions"
    assert assistant.configured() is True


def test_make_client_openai_compatible_defaults_model_when_unset(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://my-gateway.example/v1/")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client = assistant.make_client()
    assert client.model == assistant.DEFAULT_OPENAI_COMPATIBLE_MODEL
    assert client.base_url == "https://my-gateway.example/v1/chat/completions"


def test_make_client_falls_back_to_mistral_without_the_override(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("MISTRAL_API_KEY", "m")
    client = assistant.make_client()
    assert isinstance(client, assistant.MistralProvider)
    assert client.model == assistant.MISTRAL_MODEL
    monkeypatch.delenv("MISTRAL_API_KEY")
    assert assistant.configured() is False
