"""A presentation must never inherit a participant database or model route."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("run_demo", ROOT / "scripts/run_demo.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_demo_overrides_storage_and_disables_external_services(tmp_path, monkeypatch):
    inherited = {
        "DATABASE_URL": "postgresql://example.invalid/participant-data",
        "MIDDLEWARE_DB": "/not-the-demo/participants.sqlite3",
        "MIDDLEWARE_PROTOCOL": "/not-the-demo/protocol.yaml",
        "MIDDLEWARE_AUTH": "token",
        "MIDDLEWARE_TOKEN": "synthetic-secret",
        "MIDDLEWARE_CORPUS_BOOTSTRAP": "1",
        "MIDDLEWARE_REFRESH_INTERVAL_H": "1",
        "LLM_API_KEY": "synthetic-provider-key",
        "LLM_BASE_URL": "http://127.0.0.1:9999/v1",
    }
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)
    before = dict(os.environ)
    env = launcher.demo_environment(tmp_path, 8123)
    assert dict(os.environ) == before
    assert env["DATABASE_URL"] == ""
    assert env["MIDDLEWARE_DB"] == str(tmp_path / "demo.sqlite3")
    assert env["MIDDLEWARE_DATA_DIR"] == str(tmp_path)
    assert env["MIDDLEWARE_PROTOCOL"] == ""
    assert env["MIDDLEWARE_AUTH"] == "none"
    assert env["MIDDLEWARE_CORPUS_BOOTSTRAP"] == "0"
    assert env["MIDDLEWARE_REFRESH_INTERVAL_H"] == "off"
    assert not any(key.startswith("LLM_") for key in env)
    assert "MIDDLEWARE_TOKEN" not in env
    assert Path(env["MIDDLEWARE_WEB"]) == ROOT / "platform/dist"


def test_live_demo_keeps_only_the_model_route_and_loads_literature(
    tmp_path, monkeypatch
):
    """--live adds the chat model and the paper corpus, nothing else: storage,
    sign-in and every other inherited server setting stay disposable."""
    for key, value in {
        "LLM_API_KEY": "synthetic-provider-key",
        "LLM_MODEL": "synthetic-model",
        "MIDDLEWARE_AUTH": "token",
        "MIDDLEWARE_DB": "/not-the-demo/participants.sqlite3",
        "MIDDLEWARE_REFRESH_INTERVAL_H": "1",
        "DATABASE_URL": "postgresql://example.invalid/participant-data",
    }.items():
        monkeypatch.setenv(key, value)
    env = launcher.demo_environment(tmp_path, 8123, live=True)
    assert env["LLM_API_KEY"] == "synthetic-provider-key"
    assert env["LLM_MODEL"] == "synthetic-model"
    assert env["MIDDLEWARE_CORPUS_BOOTSTRAP"] == "1"
    assert env["MIDDLEWARE_REFRESH_INTERVAL_H"] == "off"
    assert env["MIDDLEWARE_AUTH"] == "none"
    assert env["MIDDLEWARE_DB"] == str(tmp_path / "demo.sqlite3")
    assert env["DATABASE_URL"] == ""


@pytest.mark.parametrize(
    ("base_url", "api_key"),
    [("", ""), ("https://localhost.example.invalid/v1", ""), ("not-a-url", "key")],
)
def test_live_demo_rejects_an_unusable_model_route(
    monkeypatch, capsys, base_url, api_key
):
    for key in list(os.environ):
        if key.startswith("LLM_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("LLM_BASE_URL", base_url)
    monkeypatch.setenv("LLM_API_KEY", api_key)
    monkeypatch.setattr(sys, "argv", ["run_demo.py", "--live"])

    with pytest.raises(SystemExit) as error:
        launcher.main()

    assert error.value.code == 2
    assert "--live needs a model provider" in capsys.readouterr().err
