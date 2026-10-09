"""Both literature clients resolve the same key and legacy alias."""

import importlib.util
from pathlib import Path

import pytest

from middleware import semantic_scholar


@pytest.mark.parametrize(
    "primary,alias,expected",
    [("main", "alias", "main"), ("", "alias", "alias"), (" \t", "", "")],
)
def test_s2_key_resolution(monkeypatch, primary, alias, expected):
    monkeypatch.setenv("MIDDLEWARE_S2_API_KEY", primary)
    monkeypatch.setenv("S2_API_KEY", alias)
    script = Path(__file__).resolve().parents[2] / "scripts" / "corpus_harvest.py"
    spec = importlib.util.spec_from_file_location("corpus_harvest", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    headers = {"x-api-key": expected} if expected else {}
    assert semantic_scholar._headers() == headers
    assert module.api_headers() == headers
