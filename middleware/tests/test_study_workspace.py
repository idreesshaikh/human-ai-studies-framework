"""The study folder a minted link opens (issue 36)."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.settings import Settings

from middleware import workspace

REPO_ROOT = Path(__file__).resolve().parents[2]
PILOT = REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"
STUDY = "pilot-2026"


@pytest.fixture()
def client(tmp_path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "ws.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=PILOT,
        port=8000,
        spa_dist=tmp_path / "no-dist",
    )
    return TestClient(create_app(settings))


def _zip(members: dict[str, bytes], *, raw_names: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(zipfile.ZipInfo(name) if raw_names else name, data)
    return buf.getvalue()


def _upload(client, data: bytes, name="study.zip"):
    return client.put(
        f"/studies/{STUDY}/workspace",
        files={"file": (name, data, "application/zip")},
    )


def _redeem(client) -> dict:
    token = client.post(f"/studies/{STUDY}/enrollment/tokens", json={"count": 1})
    assert token.status_code == 200, token.text
    conn = token.json()[0]["connectionString"]
    res = client.post("/pair/redeem", json={"token": conn.split("#", 1)[1]})
    assert res.status_code == 200, res.text
    return res.json()


def test_no_setting_by_default(client):
    assert client.get(f"/studies/{STUDY}/workspace").json() == {"kind": None}


@pytest.mark.parametrize(
    "value",
    ["/home/study/task", "~/study/task", "file:///home/study/task", "C:\\study\\task"],
)
def test_a_folder_path_is_stored(client, value):
    res = client.put(f"/studies/{STUDY}/workspace", data={"path": value})
    assert res.status_code == 200, res.text
    assert client.get(f"/studies/{STUDY}/workspace").json()["path"] == value


@pytest.mark.parametrize(
    "value",
    ["relative/dir", "https://github.com/x/y", "task.zip", "/a/../etc"],
)
def test_a_path_participants_cannot_open_is_refused(client, value):
    res = client.put(f"/studies/{STUDY}/workspace", data={"path": value})
    assert res.status_code == 422
    assert client.get(f"/studies/{STUDY}/workspace").json() == {"kind": None}


def test_exactly_one_of_path_or_zip_is_required(client):
    assert client.put(f"/studies/{STUDY}/workspace").status_code == 400
    both = client.put(
        f"/studies/{STUDY}/workspace",
        data={"path": "/x"},
        files={"file": ("a.zip", _zip({"a": b"1"}), "application/zip")},
    )
    assert both.status_code == 400


def test_an_uploaded_zip_is_recorded_with_its_hash(client):
    data = _zip({"task/README.md": b"hello"})
    res = _upload(client, data)
    assert res.status_code == 200, res.text
    doc = res.json()
    assert doc["kind"] == "archive"
    assert doc["sha256"] == hashlib.sha256(data).hexdigest()
    assert doc["size"] == len(data)


@pytest.mark.parametrize(
    "members",
    [
        {"../evil.txt": b"x"},
        {"/abs/evil.txt": b"x"},
        {"C:/evil.txt": b"x"},
    ],
)
def test_a_zip_that_could_escape_its_folder_is_refused(client, members):
    res = _upload(client, _zip(members, raw_names=True))
    assert res.status_code == 422
    assert "unsafe path" in res.json()["detail"]


def test_a_non_zip_or_empty_zip_is_refused(client):
    assert _upload(client, b"not a zip").status_code == 422
    assert _upload(client, _zip({"empty/": b""})).status_code == 422


def test_a_zip_over_the_size_limits_is_refused(monkeypatch):
    monkeypatch.setattr(workspace, "MAX_UNPACKED_BYTES", 10)
    with pytest.raises(workspace.WorkspaceError, match="unpacks to more than"):
        workspace.validate_archive(_zip({"a.txt": b"x" * 100}))
    monkeypatch.setattr(workspace, "MAX_ENTRIES", 1)
    with pytest.raises(workspace.WorkspaceError, match="more than 1 entries"):
        workspace.validate_archive(_zip({"a": b"1", "b": b"2"}))


def test_a_symlink_entry_is_refused():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        info = zipfile.ZipInfo("link")
        info.external_attr = 0o120777 << 16
        zf.writestr(info, "/etc/passwd")
    with pytest.raises(workspace.WorkspaceError, match="symbolic link"):
        workspace.validate_archive(buf.getvalue())


def test_clearing_removes_the_setting(client):
    client.put(f"/studies/{STUDY}/workspace", data={"path": "/x/y"})
    client.delete(f"/studies/{STUDY}/workspace")
    assert client.get(f"/studies/{STUDY}/workspace").json() == {"kind": None}


def test_redeem_carries_a_path_workspace(client):
    client.put(f"/studies/{STUDY}/workspace", data={"path": "/home/study/task"})
    block = _redeem(client)["captureConfig"]["block"]
    assert block["workspace"] == {"kind": "path", "path": "/home/study/task"}


def test_redeem_carries_an_archive_workspace_and_it_downloads_with_a_credential(
    client,
):
    data = _zip({"task/README.md": b"hello"})
    _upload(client, data)
    redeemed = _redeem(client)
    workspace_block = redeemed["captureConfig"]["block"]["workspace"]
    assert workspace_block["kind"] == "archive"
    assert workspace_block["url"] == f"/studies/{STUDY}/workspace/archive"
    assert workspace_block["sha256"] == hashlib.sha256(data).hexdigest()

    credential = redeemed["sessionCredential"]
    res = client.get(
        workspace_block["url"], headers={"Authorization": f"Bearer {credential}"}
    )
    assert res.status_code == 200
    assert res.content == data
    assert res.headers["x-content-sha256"] == workspace_block["sha256"]


def test_the_archive_needs_a_valid_credential_for_this_study(client):
    _upload(client, _zip({"a": b"1"}))
    url = f"/studies/{STUDY}/workspace/archive"
    assert client.get(url).status_code == 401
    assert client.get(url, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_the_archive_is_not_in_the_data_export(client):
    _upload(client, _zip({"a": b"1"}))
    bundle = client.get(f"/studies/{STUDY}/dataset?format=json")
    assert bundle.status_code == 200
    assert "workspace" not in bundle.text.lower()
