"""
``GET /studies/{id}/data-bundle``: the post-run data as a zip of tidy files a
researcher can postprocess without the platform.
"""

import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.export_bundle import flatten
from middleware.settings import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"
STUDY = "pilot-2026"
JOIN = ["participantId", "condition", "sessionId", "taskId", "ts", "schemaVersion"]


@pytest.fixture()
def client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "bundle.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    return TestClient(
        create_app(settings, clock=lambda: datetime(2026, 7, 11, tzinfo=UTC))
    )


def _event(seq, payload, session="S1", type_="fatigue_response"):
    return {
        "v": 2,
        "ts": f"2026-07-11T10:00:{seq:02d}.000Z",
        "mono": seq * 1000.0,
        "sessionId": session,
        "participantId": "P01",
        "condition": "ai-assisted",
        "seq": seq,
        "type": type_,
        "payload": payload,
    }


def _open(client, **params) -> zipfile.ZipFile:
    res = client.get(f"/studies/{STUDY}/data-bundle", params=params)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/zip"
    assert f'filename="{STUDY}-data.zip"' in res.headers["content-disposition"]
    return zipfile.ZipFile(io.BytesIO(res.content))


def _seed(client):
    client.post(
        "/ingest/events",
        json=[
            _event(0, {"answer": 3, "meta": {"scale": "likert", "n": 7}}),
            _event(1, {"answer": 5, "meta": {"scale": "likert", "n": 7}}),
            _event(2, {"synthetic": True, "answer": 1}, session="S2"),
            _event(3, {"tool": "edit"}, type_="agent_tool_call"),
        ],
    )


def test_bundle_has_one_tidy_csv_per_event_type_with_join_keys_first(client):
    _seed(client)
    zf = _open(client)
    names = set(zf.namelist())
    assert {
        "README.md",
        "data-dictionary.md",
        "manifest.json",
        "events/all.json",
        "events/fatigue_response.csv",
        "events/agent_tool_call.csv",
    } <= names
    rows = list(
        csv.DictReader(io.StringIO(zf.read("events/fatigue_response.csv").decode()))
    )
    assert len(rows) == 2
    assert list(rows[0])[: len(JOIN)] == JOIN
    # nested payload flattened to dotted columns, not a JSON blob
    assert rows[0]["meta.scale"] == "likert"
    assert rows[0]["answer"] == "3"
    assert all(r["participantId"] == "P01" and r["condition"] for r in rows)


def test_synthetic_rows_are_excluded_unless_requested(client):
    _seed(client)
    default = json.loads(_open(client).read("events/all.json"))["rows"]
    assert len(default) == 3
    assert not any(r["payload"].get("synthetic") for r in default)
    everything = json.loads(
        _open(client, includeSynthetic="true").read("events/all.json")
    )["rows"]
    assert len(everything) == 4


def test_manifest_hashes_match_members(client):
    import hashlib

    _seed(client)
    zf = _open(client)
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["rows"] == 3
    for name, digest in manifest["members"].items():
        assert hashlib.sha256(zf.read(name)).hexdigest() == digest


def test_export_is_byte_identical_across_calls(client):
    _seed(client)
    url = f"/studies/{STUDY}/data-bundle"
    assert client.get(url).content == client.get(url).content


def test_uploaded_files_are_included_and_study_scoped(client):
    client.post(
        "/ingest/files",
        data={"studyId": STUDY},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    zf = _open(client)
    assert [n for n in zf.namelist() if n.startswith("files/")] != []
    member = next(n for n in zf.namelist() if n.startswith("files/"))
    assert zf.read(member) == b"hello"


def test_unknown_study_is_refused(client):
    assert client.get("/studies/other-study/data-bundle").status_code == 404


def test_flatten_keeps_lists_and_empty_dicts_as_values():
    assert flatten({"a": {"b": 1}, "c": [1, 2], "d": {}}) == {
        "a.b": 1,
        "c": [1, 2],
        "d": {},
    }


def test_dataset_csv_download_has_a_filename(client):
    res = client.get(f"/studies/{STUDY}/dataset?format=csv")
    assert f'filename="{STUDY}-dataset.csv"' in res.headers["content-disposition"]


def test_manifest_records_provenance_metadata(client):
    import hashlib

    import yaml

    _seed(client)
    zf = _open(client)
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["formatVersion"] == 1
    assert manifest["studyId"] == STUDY
    assert manifest["encoding"] == "utf-8"
    assert manifest["timestampFormat"] == "ISO 8601, UTC"
    assert manifest["includesSynthetic"] is False
    assert manifest["schemaVersions"] == [2]
    assert manifest["participants"] == {"P01": ["ai-assisted"]}
    protocol = manifest["protocol"]
    assert protocol["id"] == STUDY
    assert protocol["title"]
    assert protocol["version"] == yaml.safe_load(zf.read("protocol.yaml"))[
        "protocolVersion"
    ]
    canonical = json.dumps(yaml.safe_load(zf.read("protocol.yaml")), sort_keys=True)
    assert protocol["sha256"] == hashlib.sha256(canonical.encode()).hexdigest()


def test_manifest_says_when_synthetic_rows_are_included(client):
    _seed(client)
    zf = _open(client, includeSynthetic="true")
    assert json.loads(zf.read("manifest.json"))["includesSynthetic"] is True


def test_readme_documents_every_member_and_the_conventions(client):
    _seed(client)
    zf = _open(client)
    readme = zf.read("README.md").decode()
    for token in ("events/", "protocol.yaml", "data-dictionary.md", "manifest.json"):
        assert token in readme
    assert "UTF-8" in readme and "ISO 8601" in readme
    for name in zf.namelist():
        assert name == "README.md" or name.split("/")[0] in readme.replace("`", "")


def test_csv_decodes_as_utf8(client):
    client.post(
        "/ingest/events",
        json=[_event(0, {"answer": "naïve – ok"})],
    )
    zf = _open(client)
    rows = list(
        csv.DictReader(io.StringIO(zf.read("events/fatigue_response.csv").decode()))
    )
    assert rows[0]["answer"] == "naïve – ok"
