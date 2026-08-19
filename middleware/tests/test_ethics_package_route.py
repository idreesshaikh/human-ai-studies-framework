"""``GET /studies/{id}/ethics-package`` over HTTP: the same generator the unit
tests exercise, reachable as a download from the workspace rather than only
from a Python import."""

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

STUDY = "ethics-study"


def _protocol_yaml() -> str:
    """A real, valid protocol instantiated from the registry, so this test
    can never pass against a shape the platform would reject."""
    import yaml

    from middleware import template_registry

    out = template_registry.instantiate_template("metr-rct-v1", {"studyId": STUDY})
    return yaml.safe_dump(out["protocol"], sort_keys=False)


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "ethics.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    tc = TestClient(create_app(settings))
    tc.db_url = f"sqlite:///{settings.db_path}"
    return tc


def _seed_draft(client) -> None:
    from middleware.db import ProtocolDraftRow, make_session_factory

    factory = make_session_factory(client.db_url)
    with factory() as s:
        s.add(ProtocolDraftRow(study_id=STUDY, yaml=_protocol_yaml()))
        s.commit()


def test_study_without_a_protocol_refuses_to_export(client):
    res = client.get(f"/studies/{STUDY}/ethics-package")
    assert res.status_code == 409
    assert "no compiled protocol" in res.json()["detail"]


def test_export_returns_a_downloadable_markdown_document(client):
    _seed_draft(client)
    res = client.get(f"/studies/{STUDY}/ethics-package")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/markdown")
    assert f'filename="{STUDY}-ethics-package.md"' in (
        res.headers["content-disposition"]
    )
    assert res.text.startswith("# Ethics package:")
    assert "## Informed consent statement" in res.text
    assert "## Withdrawal" in res.text


def test_export_is_byte_reproducible(client):
    _seed_draft(client)
    first = client.get(f"/studies/{STUDY}/ethics-package").content
    second = client.get(f"/studies/{STUDY}/ethics-package").content
    assert first == second
