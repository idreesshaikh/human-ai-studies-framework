"""
``GET /studies/{id}/notebook`` over HTTP: the same notebook the CLI's ``analysis
notebook`` writes, reachable as a download from the workspace.
"""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

STUDY = "notebook-study"


def _protocol_yaml() -> str:
    import yaml

    from middleware import template_registry

    out = template_registry.instantiate_template("metr-rct-v1", {"studyId": STUDY})
    return yaml.safe_dump(out["protocol"], sort_keys=False)


@pytest.fixture()
def client(tmp_path):
    settings = Settings(
        db_path=tmp_path / "notebook.sqlite3",
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
    res = client.get(f"/studies/{STUDY}/notebook")
    assert res.status_code == 409
    assert "no compiled protocol" in res.json()["detail"]


def test_export_returns_a_downloadable_zip_with_both_artifacts(client):
    _seed_draft(client)
    res = client.get(f"/studies/{STUDY}/notebook")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/zip"
    assert f'filename="{STUDY}-notebook.zip"' in res.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        names = set(zf.namelist())
        assert names == {"notebook.ipynb", "data-dictionary.md"}
        doc = json.loads(zf.read("notebook.ipynb"))
        assert doc["nbformat"] == 4
        assert "## Data dictionary" in zf.read("data-dictionary.md").decode()


def test_the_exported_notebook_actually_validates(client):
    """
    The route's output, not just the library function, has to open in Jupyter  -  an
    empty
    dataset (no sessions run yet) is the common case for a study that has only just been
    set up.
    """
    import nbformat

    _seed_draft(client)
    res = client.get(f"/studies/{STUDY}/notebook")
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        doc = json.loads(zf.read("notebook.ipynb"))
    nbformat.validate(nbformat.from_dict(doc))


def test_export_is_byte_reproducible(client):
    _seed_draft(client)
    first = client.get(f"/studies/{STUDY}/notebook").content
    second = client.get(f"/studies/{STUDY}/notebook").content
    assert first == second
