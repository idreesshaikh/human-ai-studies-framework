"""Model routing stays configurable without reimporting the application."""

import pytest

from middleware import assistant


@pytest.fixture(autouse=True)
def isolated_model_environment(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.delenv("MISTRAL_MODEL", raising=False)
    monkeypatch.delenv("MISTRAL_DESIGN_MODEL", raising=False)


def test_default_routes_use_ministral():
    assert assistant.make_client().model == "ministral-14b-latest"
    assert assistant.make_design_client().model == "ministral-14b-latest"


def test_shared_override_is_resolved_after_import(monkeypatch):
    monkeypatch.setenv("MISTRAL_MODEL", "  ministral-8b-2512  ")
    assert assistant.make_client().model == "ministral-8b-2512"
    assert assistant.make_design_client().model == "ministral-8b-2512"
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-small-latest")
    assert assistant.make_client().model == "mistral-small-latest"


def test_design_override_does_not_change_corpus(monkeypatch):
    monkeypatch.setenv("MISTRAL_MODEL", "ministral-8b-latest")
    monkeypatch.setenv("MISTRAL_DESIGN_MODEL", "ministral-14b-2512")
    assert assistant.make_client().model == "ministral-8b-latest"
    assert assistant.make_design_client().model == "ministral-14b-2512"


def test_blank_settings_fall_back(monkeypatch):
    monkeypatch.setenv("MISTRAL_MODEL", "  ")
    monkeypatch.setenv("MISTRAL_DESIGN_MODEL", "\t")
    assert assistant.make_client().model == "ministral-14b-latest"
    assert assistant.make_design_client().model == "ministral-14b-latest"


def test_missing_key_keeps_offline_path(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY")
    assert assistant.make_client() is None
    assert assistant.make_design_client() is None


def test_design_preserves_injected_provider(monkeypatch):
    provider = object()
    monkeypatch.setattr(assistant, "make_client", lambda: provider)
    assert assistant.make_design_client() is provider
