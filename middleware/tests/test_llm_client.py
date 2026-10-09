"""Model routing, endpoint selection, timeouts and retries come from the environment."""

import io
import json
import urllib.error

import pytest

from middleware import assistant as llm

_POST_JSON = llm._post_json
_POST_STREAM = llm._post_stream
sleeps: list[float] = []


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_DESIGN_MODEL",
        "LLM_ALLOW_HTTP",
        "LLM_TIMEOUT_S",
        "LLM_STREAM_TIMEOUT_S",
        "LLM_MAX_RETRIES",
        "MISTRAL_API_KEY",
        "MISTRAL_MODEL",
        "MISTRAL_DESIGN_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "_sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(llm, "_post_json", _POST_JSON)
    monkeypatch.setattr(llm, "_post_stream", _POST_STREAM)
    sleeps.clear()


def test_legacy_mistral_settings_still_work(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    monkeypatch.setenv("MISTRAL_MODEL", "legacy-model")
    assert llm.make_client().model == "legacy-model"
    assert llm.make_client().base_url == llm.DEFAULT_BASE_URL


def test_llm_settings_win_over_legacy(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "old")
    monkeypatch.setenv("LLM_API_KEY", "new")
    monkeypatch.setenv("MISTRAL_MODEL", "legacy")
    monkeypatch.setenv("LLM_MODEL", "shared")
    monkeypatch.setenv("MISTRAL_DESIGN_MODEL", "legacy-design")
    monkeypatch.setenv("LLM_DESIGN_MODEL", "design")
    assert llm.make_client().api_key == "new"
    assert llm.make_client().model == "shared"
    assert llm.make_design_client().model == "design"


def test_design_model_falls_back_to_shared_then_default(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    assert llm.make_design_client().model == llm.DEFAULT_MODEL
    monkeypatch.setenv("LLM_MODEL", "shared")
    assert llm.make_design_client().model == "shared"
    monkeypatch.setenv("LLM_DESIGN_MODEL", "  \t")
    assert llm.make_design_client().model == "shared"


@pytest.mark.parametrize(
    "given,expected",
    [
        ("https://api.example.com/v1", "https://api.example.com/v1/chat/completions"),
        ("https://api.example.com/v1/", "https://api.example.com/v1/chat/completions"),
        (
            "https://api.example.com/v1/chat/completions",
            "https://api.example.com/v1/chat/completions",
        ),
    ],
)
def test_base_url_accepts_an_api_base_or_a_full_url(monkeypatch, given, expected):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", given)
    assert llm.make_client().base_url == expected


def test_no_key_means_no_remote_route():
    assert llm.make_client() is None and llm.configured() is False


def test_a_local_server_needs_no_key(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    client = llm.make_client()
    assert client is not None and client.headers == {}


def test_key_is_sent_as_a_bearer_header(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "secret")
    assert llm.make_client().headers == {"Authorization": "Bearer secret"}


def test_plain_http_to_a_remote_host_is_refused_unless_allowed(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "http://models.internal.example/v1")
    assert llm.make_client() is None
    monkeypatch.setenv("LLM_ALLOW_HTTP", "1")
    assert llm.make_client() is not None


@pytest.mark.parametrize("bad", ["ftp://x/v1", "not a url", "https://"])
def test_invalid_base_url_disables_the_route(monkeypatch, bad):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", bad)
    assert llm.make_client() is None


def test_refusals_never_log_the_key(monkeypatch, caplog):
    monkeypatch.setenv("LLM_API_KEY", "super-secret-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://models.internal.example/v1")
    assert llm.make_client() is None
    assert "super-secret-key" not in caplog.text


def test_legacy_provider_name_and_injection_seam_survive():
    assert llm.MistralProvider is llm.ChatProvider
    sent = []
    provider = llm.MistralProvider(
        "test-key", post=lambda url, body, headers: sent.append(body) or {}
    )
    provider.post(provider.base_url, {"x": 1}, provider.headers)
    assert sent == [{"x": 1}]


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(code, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after else {}
    return urllib.error.HTTPError("http://x", code, "err", headers, None)


def _script(monkeypatch, outcomes):
    calls = []

    def fake_urlopen(req, timeout):
        calls.append(timeout)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(outcome)

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_429_is_retried_and_honours_retry_after(monkeypatch):
    calls = _script(
        monkeypatch, [_http_error(429, "2"), json.dumps({"ok": 1}).encode()]
    )
    assert llm._post_json("http://x", {}, {}) == {"ok": 1}
    assert sleeps == [2.0] and len(calls) == 2


def test_retry_after_is_capped(monkeypatch):
    _script(monkeypatch, [_http_error(503, "9999"), b"{}"])
    llm._post_json("http://x", {}, {})
    assert sleeps == [30.0]


def test_backoff_without_retry_after_grows(monkeypatch):
    _script(monkeypatch, [_http_error(500), _http_error(502), b"{}"])
    llm._post_json("http://x", {}, {})
    assert sleeps == [0.5, 1.0]


def test_a_client_error_is_not_retried(monkeypatch):
    calls = _script(monkeypatch, [_http_error(400), b"{}"])
    with pytest.raises(urllib.error.HTTPError):
        llm._post_json("http://x", {}, {})
    assert len(calls) == 1 and sleeps == []


def test_retries_are_bounded_and_configurable(monkeypatch):
    monkeypatch.setenv("LLM_MAX_RETRIES", "1")
    calls = _script(monkeypatch, [_http_error(503)] * 5)
    with pytest.raises(urllib.error.HTTPError):
        llm._post_json("http://x", {}, {})
    assert len(calls) == 2


def test_connection_errors_are_retried(monkeypatch):
    _script(monkeypatch, [urllib.error.URLError("down"), b"{}"])
    assert llm._post_json("http://x", {}, {}) == {}
    assert len(sleeps) == 1


def test_timeouts_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_S", "7")
    monkeypatch.setenv("LLM_STREAM_TIMEOUT_S", "3000")
    calls = _script(monkeypatch, [b"{}", b""])
    llm._post_json("http://x", {}, {})
    list(llm._post_stream("http://x", {}, {}))
    assert calls == [7.0, 1800.0]  # the stream timeout is clamped to its ceiling


def test_a_bad_number_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("LLM_TIMEOUT_S", "soon")
    calls = _script(monkeypatch, [b"{}"])
    llm._post_json("http://x", {}, {})
    assert calls == [60.0]


def test_stream_is_retried_before_the_first_byte_and_yields_deltas(monkeypatch):
    frames = [
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo"}}]},
    ]
    body = "".join(f"data: {json.dumps(f)}\n" for f in frames) + "data: [DONE]\n"
    _script(monkeypatch, [_http_error(429), body.encode()])
    assert "".join(llm._post_stream("http://x", {"model": "m"}, {})) == "Hello"
    assert len(sleeps) == 1


def test_design_compatibility_cli_honors_a_keyless_local_route(monkeypatch, tmp_path):
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    import check_design_models

    calls = []

    def post(url, body, headers):
        calls.append((url, headers))
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"text":"Check the task and outcome.","moves":[]}'
                    }
                }
            ]
        }

    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setattr(check_design_models, "_post_json", post)
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_design_models",
            "--live",
            "--models",
            "local-model",
            "--output",
            str(tmp_path / "comparison.json"),
        ],
    )
    check_design_models.main()
    assert calls == [("http://localhost:11434/v1/chat/completions", {})] * 3


@pytest.mark.parametrize("key", ["", " \t"])
def test_blank_remote_keys_disable_the_route(monkeypatch, key):
    monkeypatch.setenv("LLM_API_KEY", key)
    assert llm.make_client() is None


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@models.example/v1",
        "https://models.example/v1?api_key=secret",
        "http://[broken/v1",
        "https://models.example:invalid/v1",
    ],
)
def test_invalid_or_credential_bearing_urls_are_refused(monkeypatch, caplog, url):
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_BASE_URL", url)
    assert llm.make_client() is None
    assert "secret" not in caplog.text


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_nonfinite_timeout_falls_back_to_default(monkeypatch, value):
    monkeypatch.setenv("LLM_TIMEOUT_S", value)
    calls = _script(monkeypatch, [b"{}"])
    llm._post_json("http://x", {}, {})
    assert calls == [60.0]


@pytest.mark.parametrize("first_byte", [False, True])
def test_stream_read_failure_retries_only_before_the_first_byte(
    monkeypatch, first_byte
):
    calls = []

    class BrokenStream(_Response):
        def __iter__(self):
            if first_byte:
                yield b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n'
            raise TimeoutError("read timed out")

    def open_stream(req, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            return BrokenStream()
        return _Response(b'data: {"choices":[{"delta":{"content":"World"}}]}\n')

    monkeypatch.setattr(llm.urllib.request, "urlopen", open_stream)
    if first_byte:
        stream = llm._post_stream("http://x", {}, {})
        assert next(stream) == "Hello"
        with pytest.raises(TimeoutError):
            next(stream)
        assert len(calls) == 1 and sleeps == []
    else:
        assert list(llm._post_stream("http://x", {}, {})) == ["World"]
        assert len(calls) == 2 and sleeps == [0.5]
