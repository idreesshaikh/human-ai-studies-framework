"""A presentation must never inherit a participant database or model route."""

import importlib.util
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("run_demo", ROOT / "scripts/run_demo.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_demo_overrides_storage_and_disables_external_services(tmp_path, monkeypatch):
    inherited = {
        "DATABASE_URL": "postgresql://example.invalid/participant-data",
        "MIDDLEWARE_DB": "/not-the-demo/participants.sqlite3",
        "MIDDLEWARE_PROTOCOL": "/not-the-demo/protocol.yaml",
        "MIDDLEWARE_AUTH": "clerk",
        "MIDDLEWARE_TOKEN": "synthetic-secret",
        "MIDDLEWARE_CORPUS_BOOTSTRAP": "1",
        "MIDDLEWARE_REFRESH_INTERVAL_H": "1",
        "MIDDLEWARE_CLERK_PUBLISHABLE_KEY": "synthetic-clerk-key",
        "LLM_API_KEY": "synthetic-provider-key",
        "LLM_BASE_URL": "http://127.0.0.1:9999/v1",
        "MISTRAL_API_KEY": "synthetic-legacy-key",
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
    assert env["MIDDLEWARE_REFRESH_INTERVAL_H"] == ""
    assert env["MIDDLEWARE_PUBLIC_URL"] == "http://127.0.0.1:8123"
    assert not any(key.startswith(("LLM_", "MISTRAL_")) for key in env)
    assert "MIDDLEWARE_TOKEN" not in env
    assert "MIDDLEWARE_CLERK_PUBLISHABLE_KEY" not in env
    assert Path(env["MIDDLEWARE_WEB"]) == ROOT / "platform/dist"


def test_live_demo_keeps_only_the_model_route_and_loads_literature(
    tmp_path, monkeypatch
):
    """--live adds the chat model and the paper corpus, nothing else: storage,
    sign-in and every other inherited server setting stay disposable."""
    for key, value in {
        "LLM_API_KEY": "synthetic-provider-key",
        "LLM_MODEL": "synthetic-model",
        "MISTRAL_API_KEY": "synthetic-legacy-key",
        "MIDDLEWARE_AUTH": "clerk",
        "MIDDLEWARE_DB": "/not-the-demo/participants.sqlite3",
        "DATABASE_URL": "postgresql://example.invalid/participant-data",
    }.items():
        monkeypatch.setenv(key, value)
    env = launcher.demo_environment(tmp_path, 8123, live=True)
    assert env["LLM_API_KEY"] == "synthetic-provider-key"
    assert env["LLM_MODEL"] == "synthetic-model"
    assert env["MISTRAL_API_KEY"] == "synthetic-legacy-key"
    assert env["MIDDLEWARE_CORPUS_BOOTSTRAP"] == "1"
    assert env["MIDDLEWARE_AUTH"] == "none"
    assert env["MIDDLEWARE_DB"] == str(tmp_path / "demo.sqlite3")
    assert env["DATABASE_URL"] == ""


def test_live_demo_needs_a_model_route(monkeypatch):
    for key in list(os.environ):
        if key.startswith(("LLM_", "MISTRAL_")):
            monkeypatch.delenv(key)
    assert not launcher.has_model_route(os.environ)
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    assert launcher.has_model_route(os.environ)
    monkeypatch.delenv("MISTRAL_API_KEY")
    # A local OpenAI-compatible server needs no key.
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    assert launcher.has_model_route(os.environ)
