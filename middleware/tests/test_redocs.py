"""Requirements-of-record endpoints (FR-DASH-9): the SRS + glossary parse
into the tooltip payloads the dashboard's lexicon consumes, live from the
real files - and degrade to [] when the documents are absent."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.redocs import parse_glossary, parse_srs
from middleware.settings import Settings

REPO = Path(__file__).resolve().parents[2]
REQS = REPO / "requirements"
PILOT = REPO / "protocol" / "examples" / "pilot-study.yaml"
FROZEN = datetime(2026, 7, 12, 12, 0, 0, tzinfo=UTC)


# ------------------------------------------------------------ parse_srs


def test_parse_srs_reads_the_real_document_of_record():
    rows = parse_srs(REQS / "srs.md")
    by_id = {r["id"]: r for r in rows}
    assert len(rows) >= 70
    # A known FR row, fully shaped.
    r = by_id["FR-PROT-1"]
    assert r["priority"] == "M"
    assert "YAML protocol" in r["text"]
    assert r["status"].startswith("✅")
    # The requirement this feature itself traces to.
    assert "guided tour" in by_id["FR-DASH-9"]["text"]
    # NFR table has no Status column - empty, never missing.
    assert by_id["NFR-1"]["status"] == ""
    assert "Non-intrusiveness" in by_id["NFR-1"]["text"]


def test_parse_srs_handles_superseded_and_markdown_noise():
    by_id = {r["id"]: r for r in parse_srs(REQS / "srs.md")}
    # The struck-through row still resolves, de-struck.
    assert "FR-PROT-6" in by_id
    assert "~~" not in by_id["FR-PROT-6"]["text"]
    # No row leaks emphasis markers into tooltip text.
    assert all("**" not in r["text"] for r in by_id.values())


# ------------------------------------------------------- parse_glossary


def test_parse_glossary_reads_the_real_glossary():
    rows = parse_glossary(REQS / "glossary.md")
    terms = {r["term"]: r["definition"] for r in rows}
    assert len(rows) >= 35
    assert "Participant" in terms
    assert "Condition" in terms
    # Qualified term names key on the bare term.
    assert not any("*(" in t for t in terms)
    # Escaped pipes inside definitions survive as literal pipes.
    assert all("\\|" not in d for d in terms.values())


def test_missing_files_degrade_to_empty(tmp_path):
    assert parse_srs(tmp_path / "srs.md") == []
    assert parse_glossary(tmp_path / "glossary.md") == []


# ------------------------------------------------------------ endpoints


@pytest.fixture()
def client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "t.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        dashboard_dist=tmp_path / "no-dist",
        requirements_dir=REQS,
    )
    return TestClient(create_app(settings, clock=lambda: FROZEN))


def test_requirements_and_glossary_endpoints(client):
    reqs = client.get("/requirements").json()
    assert any(r["id"] == "FR-DASH-9" for r in reqs)
    gloss = client.get("/glossary").json()
    assert any(g["term"] == "Recipe" for g in gloss)


def test_endpoints_empty_when_documents_absent(tmp_path):
    settings = Settings(
        db_path=tmp_path / "t.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        dashboard_dist=tmp_path / "no-dist",
        requirements_dir=tmp_path / "nowhere",
    )
    client = TestClient(create_app(settings, clock=lambda: FROZEN))
    assert client.get("/requirements").json() == []
    assert client.get("/glossary").json() == []
