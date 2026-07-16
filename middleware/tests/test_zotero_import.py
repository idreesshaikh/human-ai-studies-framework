"""Zotero import tests (FR-LIT-5, D9; roadmap/09 item 2).

The HTTP layer is faked at ``zotero._get_json`` with recorded-shape API v3
JSON (the local and web APIs speak the same format, per the Zotero docs),
so the tests exercise everything real except the wire: collection
resolution, pagination, normalization to paperRef-keyed records, the
idempotent re-import, the local -> web fallback, and honest failure when
neither source is reachable.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

from middleware import zotero

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"

COLLECTIONS = [
    {
        "key": "ABCD1234",
        "version": 10,
        "data": {"key": "ABCD1234", "name": "Pilot Reading List"},
    },
    {"key": "ZZZZ9999", "version": 11, "data": {"key": "ZZZZ9999", "name": "Misc"}},
]

#: Top-level items of the "Pilot Reading List" collection: the pilot's two
#: replicated papers (DOI field / arXiv archiveID), a conferencePaper whose
#: DOI hides in `extra`, an institutional-author report with no id at all,
#: and a standalone note (skipped).
ITEMS = [
    {
        "key": "MEYER017",
        "version": 20,
        "data": {
            "itemType": "journalArticle",
            "title": "The Work Life of Developers",
            "creators": [
                {"creatorType": "author", "firstName": "Andre", "lastName": "Meyer"},
                {"creatorType": "author", "firstName": "Thomas", "lastName": "Fritz"},
            ],
            "date": "2017-12-01",
            "publicationTitle": "IEEE Transactions on Software Engineering",
            "DOI": "10.1109/TSE.2017.2656886",
            "url": "",
            "extra": "",
            "abstractNote": "Fragmented work ...",
        },
    },
    {
        "key": "ZIEGLR22",
        "version": 21,
        "data": {
            "itemType": "preprint",
            "title": "Productivity Assessment of Neural Code Completion",
            "creators": [
                {"creatorType": "author", "firstName": "Albert", "lastName": "Ziegler"}
            ],
            "date": "July 12, 2022",
            "repository": "arXiv",
            "archiveID": "arXiv:2205.06537",
            "url": "https://arxiv.org/abs/2205.06537",
            "abstractNote": "",
        },
    },
    {
        "key": "PENG2023",
        "version": 22,
        "data": {
            "itemType": "conferencePaper",
            "title": "The Impact of AI on Developer Productivity",
            "creators": [
                {"creatorType": "author", "firstName": "Sida", "lastName": "Peng"}
            ],
            "date": "2023",
            "proceedingsTitle": "Working paper",
            "extra": "DOI: 10.48550/arXiv.2302.06590",
            "url": "",
        },
    },
    {
        "key": "SPACE021",
        "version": 23,
        "data": {
            "itemType": "report",
            "title": "The SPACE of Developer Productivity",
            "creators": [{"creatorType": "author", "name": "GitHub Research"}],
            "date": "2021",
            "publisher": "ACM Queue",
            "url": "",
        },
    },
    {
        "key": "NOTE0001",
        "version": 24,
        "data": {"itemType": "note", "note": "<p>reading notes</p>"},
    },
]


def _fake_get_json():
    """A stand-in for ``zotero._get_json`` serving the recorded fixtures."""

    def fake(url: str, headers: dict) -> object:
        if "/collections?" in url:
            return COLLECTIONS if "start=0" in url else []
        if "/collections/ABCD1234/items/top" in url:
            return ITEMS if "start=0" in url else []
        raise zotero.ZoteroError(f"unexpected fixture URL {url}")

    return fake


@pytest.fixture()
def client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        port=8000,
        dashboard_dist=tmp_path / "no-dist",
    )
    return TestClient(create_app(settings))


def test_import_normalizes_papers_and_joins_protocol_refs(client, monkeypatch):
    monkeypatch.setattr(zotero, "_get_json", _fake_get_json())

    res = client.post(
        "/studies/pilot-2026/papers/zotero-import",
        json={"collection": "pilot reading list"},  # case-insensitive name
    )
    assert res.status_code == 200
    body = res.json()
    assert body["received"] == 5
    assert body["imported"] == 4
    assert body["skipped"] == 1  # the note
    assert body["duplicates"] == 0
    assert body["source"] == "local"

    papers = {p["paperRef"]: p for p in
              client.get("/studies/pilot-2026/papers").json()}
    assert set(papers) == {
        "doi:10.1109/TSE.2017.2656886",      # DOI field
        "arxiv:2205.06537",                   # archiveID, DOI absent
        "arxiv:2302.06590",                   # arXiv DataCite DOI in `extra`
        "zotero:SPACE021",                    # no DOI/arXiv -> item-key ref
    }
    meyer = papers["doi:10.1109/TSE.2017.2656886"]
    assert meyer["authors"] == ["Andre Meyer", "Thomas Fritz"]
    assert meyer["year"] == 2017
    assert meyer["venue"] == "IEEE Transactions on Software Engineering"
    # The protocol's literature list already cites all three replicated
    # papers - the canonical paperRef makes the join work with zero glue
    # (FR-LIT-3 builds on this in MP-10). Peng is cited as `arxiv:2302.06590`
    # but Zotero carries arXiv's DataCite DOI - canonicalizing the arXiv DOI
    # to the arXiv ref is what lets them join.
    assert meyer["inProtocolLiterature"] is True
    assert papers["arxiv:2205.06537"]["inProtocolLiterature"] is True
    peng = papers["arxiv:2302.06590"]
    assert peng["inProtocolLiterature"] is True
    assert peng["doi"] == "10.48550/arXiv.2302.06590"  # DOI still recorded
    assert papers["zotero:SPACE021"]["inProtocolLiterature"] is False
    assert papers["zotero:SPACE021"]["authors"] == ["GitHub Research"]


def test_reimport_is_idempotent_on_paper_ref(client, monkeypatch):
    monkeypatch.setattr(zotero, "_get_json", _fake_get_json())
    first = client.post(
        "/studies/pilot-2026/papers/zotero-import",
        json={"collection": "ABCD1234"},  # by key this time
    ).json()
    assert first["imported"] == 4

    again = client.post(
        "/studies/pilot-2026/papers/zotero-import",
        json={"collection": "Pilot Reading List"},
    ).json()
    assert again["imported"] == 0
    assert again["duplicates"] == 4
    assert again["skipped"] == 1
    assert len(client.get("/studies/pilot-2026/papers").json()) == 4


def test_falls_back_to_web_api_with_key(tmp_path, monkeypatch):
    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        port=8000,
        dashboard_dist=tmp_path / "no-dist",
        zotero_user_id="u1234",
        zotero_api_key="k-secret",
    )
    client = TestClient(create_app(settings))
    seen: list[tuple[str, dict]] = []

    def fake(url: str, headers: dict) -> object:
        seen.append((url, headers))
        if url.startswith("http://127.0.0.1:23119"):
            raise zotero.ZoteroUnreachable("connection refused")
        if "/collections?" in url:
            return COLLECTIONS if "start=0" in url else []
        if "/collections/ABCD1234/items/top" in url:
            return ITEMS if "start=0" in url else []
        raise zotero.ZoteroError(f"unexpected fixture URL {url}")

    monkeypatch.setattr(zotero, "_get_json", fake)

    res = client.post(
        "/studies/pilot-2026/papers/zotero-import",
        json={"collection": "Pilot Reading List"},
    )
    assert res.status_code == 200
    assert res.json()["source"] == "web"
    web_calls = [(u, h) for u, h in seen if u.startswith(zotero.WEB_API)]
    assert web_calls, "web API was never tried"
    assert all(u.startswith(f"{zotero.WEB_API}/users/u1234/") for u, _ in web_calls)
    assert all(h.get("Zotero-API-Key") == "k-secret" for _, h in web_calls)


def test_unreachable_without_fallback_is_a_clear_502(client, monkeypatch):
    def fake(url: str, headers: dict) -> object:
        raise zotero.ZoteroUnreachable(f"GET {url} failed: connection refused")

    monkeypatch.setattr(zotero, "_get_json", fake)
    res = client.post(
        "/studies/pilot-2026/papers/zotero-import",
        json={"collection": "Pilot Reading List"},
    )
    assert res.status_code == 502
    assert "MIDDLEWARE_ZOTERO_USER_ID" in res.json()["detail"]


def test_unknown_collection_names_the_available_ones(client, monkeypatch):
    monkeypatch.setattr(zotero, "_get_json", _fake_get_json())
    res = client.post(
        "/studies/pilot-2026/papers/zotero-import",
        json={"collection": "No Such List"},
    )
    assert res.status_code == 502
    assert "pilot reading list" in res.json()["detail"]
    assert "misc" in res.json()["detail"]


def test_paged_fetch_follows_start_until_short_page(monkeypatch):
    pages: list[str] = []

    def fake(url: str, headers: dict) -> object:
        pages.append(url)
        start = int(url.split("start=")[1])
        return (
            [{"key": f"K{start + i}"} for i in range(zotero.PAGE)]
            if start == 0
            else [{"key": "LAST"}]
        )

    monkeypatch.setattr(zotero, "_get_json", fake)
    out = zotero._get_paged("http://x", "/collections", {})
    assert len(out) == zotero.PAGE + 1
    assert len(pages) == 2 and "start=100" in pages[1]


def test_normalize_extracts_arxiv_from_extra_and_url():
    from_extra = zotero.normalize_item(
        {"key": "K1", "data": {"itemType": "journalArticle",
                               "extra": "arXiv: 2507.03156 [cs.SE]"}}
    )
    assert from_extra["paperRef"] == "arxiv:2507.03156"
    from_url = zotero.normalize_item(
        {"key": "K2", "data": {"itemType": "preprint",
                               "url": "https://arxiv.org/pdf/2507.09089v2"}}
    )
    assert from_url["arxivId"] == "2507.09089v2"
    doi_url_prefix = zotero.normalize_item(
        {"key": "K3", "data": {"itemType": "journalArticle",
                               "DOI": "https://doi.org/10.1145/3520312"}}
    )
    assert doi_url_prefix["paperRef"] == "doi:10.1145/3520312"
    # An arXiv DataCite DOI canonicalizes to the arXiv ref (join robustness).
    arxiv_doi = zotero.normalize_item(
        {"key": "K4", "data": {"itemType": "preprint",
                               "DOI": "10.48550/arXiv.2507.03156"}}
    )
    assert arxiv_doi["paperRef"] == "arxiv:2507.03156"
    assert arxiv_doi["arxivId"] == "2507.03156"
    assert arxiv_doi["doi"] == "10.48550/arXiv.2507.03156"
