"""Both literature clients use the same optional Semantic Scholar key."""

import importlib.util
from pathlib import Path

import pytest

from middleware import semantic_scholar


@pytest.mark.parametrize("key,expected", [("main", "main"), (" \t", "")])
def test_s2_key_resolution(monkeypatch, key, expected):
    monkeypatch.setenv("MIDDLEWARE_S2_API_KEY", key)
    monkeypatch.delenv("S2_API_KEY", raising=False)
    script = Path(__file__).resolve().parents[2] / "scripts" / "corpus_harvest.py"
    spec = importlib.util.spec_from_file_location("corpus_harvest", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    headers = {"x-api-key": expected} if expected else {}
    assert semantic_scholar._headers() == headers
    assert module.api_headers() == headers
