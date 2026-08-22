"""Replication-kit export from the workspace (D5/FR-PROT-7)."""

import gzip
import io
import tarfile

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

STUDY = "kit-study"

def _protocol_yaml() -> str:
    """
    A real, valid protocol  -  instantiated from the registry rather than hand-written, so
    this test can never pass against a shape the platform would reject.
    """
    import yaml

    from middleware import template_registry

    out = template_registry.instantiate_template("metr-rct-v1", {"studyId": STUDY})
    return yaml.safe_dump(out["protocol"], sort_keys=False)


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "kit.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    tc = TestClient(create_app(settings))
    tc.db_url = f"sqlite:///{settings.db_path}"
    return tc


def _seed_draft(client) -> None:
    """Land a compiled draft so the study has a protocol to package."""
    from middleware.db import ProtocolDraftRow, make_session_factory

    factory = make_session_factory(client.db_url)
    with factory() as s:
        s.add(ProtocolDraftRow(study_id=STUDY, yaml=_protocol_yaml()))
        s.commit()


def test_study_without_a_protocol_refuses_to_export(client):
    res = client.get(f"/studies/{STUDY}/replication-kit")
    assert res.status_code == 409
    assert "no compiled protocol" in res.json()["detail"]


def test_export_returns_a_downloadable_kit(client):
    _seed_draft(client)
    res = client.get(f"/studies/{STUDY}/replication-kit")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/gzip"
    assert f'filename="{STUDY}-replication-kit.tar.gz"' in (
        res.headers["content-disposition"]
    )

    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(res.content))) as tar:
        names = {n.split("/", 1)[1] for n in tar.getnames() if "/" in n}
    assert {"protocol.yaml", "dataset.json", "versions.json", "README.md"} <= names
    assert any(n.startswith("report") for n in names)


def test_export_is_byte_reproducible(client):
    """
    Two exports of the same study are the same archive  -  the property the whole kit
    exists for (FR-PROT-7).
    """
    _seed_draft(client)
    first = client.get(f"/studies/{STUDY}/replication-kit").content
    second = client.get(f"/studies/{STUDY}/replication-kit").content
    assert first == second
