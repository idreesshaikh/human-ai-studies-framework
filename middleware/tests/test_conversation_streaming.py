"""Streamed design turn (D3): SSE token frames + an identical stored turn.

The perceived-latency fix must not become a second, differently-worded
answer: what streams is the prose of the *same* turn the blocking endpoint
would have produced, persisted identically. These drive the real endpoint
with a scripted LLM stream — no network.
"""

import json

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.design_llm import _ReplyTextExtractor
from middleware.settings import Settings

from middleware import assistant, design_assistant

STUDY = "stream-study"

#: What a provider would emit for one design turn, split mid-word and
#: mid-escape so the extractor is exercised the way a real stream arrives.
_REPLY = {
    "text": "Here is a within-subjects design.\nIt measures task time.",
    "moves": [
        {
            "kind": "add-rq",
            "target": "researchQuestions",
            "proposal": "Does AI assistance change task completion time?",
            "patch": {
                "section": "researchQuestions",
                "op": "append",
                "value": "Does AI assistance change task completion time?",
            },
            "refs": [],
        }
    ],
}


def _chunks(text: str, size: int = 7) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)]


class _StubClient:
    """A provider whose stream emits the JSON reply in small fragments."""

    model = "stub"
    base_url = "https://example.invalid/v1/chat/completions"
    api_key = "stub"

    def __init__(self, body: str | None = None):
        self.body = body if body is not None else json.dumps(_REPLY)

    def stream(self, url, payload, headers):
        assert payload["response_format"] == {"type": "json_object"}
        yield from _chunks(self.body)

    def post(self, url, payload, headers):
        return {"choices": [{"message": {"content": self.body}}]}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _StubClient())
    settings = Settings(
        db_path=tmp_path / "stream.sqlite3",
        data_dir=tmp_path / "data",
        port=8000,
        spa_dist=tmp_path / "no-dist",
        dev_mode=True,
    )
    return TestClient(create_app(settings))


def _events(raw: str) -> list[tuple[str, dict]]:
    out = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        kind = payload = None
        for line in block.splitlines():
            if line.startswith("event: "):
                kind = line[len("event: ") :]
            elif line.startswith("data: "):
                payload = json.loads(line[len("data: ") :])
        if kind:
            out.append((kind, payload))
    return out


# ------------------------------------------------------- the extractor


def test_extractor_yields_prose_not_json():
    """The researcher sees prose, never the braces of the JSON envelope."""
    extractor = _ReplyTextExtractor()
    body = json.dumps({"text": "Hello there", "moves": []})
    streamed = "".join(extractor.feed(c) for c in _chunks(body, 3))
    assert streamed == "Hello there"


def test_extractor_decodes_escapes_and_stops_at_the_close():
    extractor = _ReplyTextExtractor()
    body = json.dumps({"text": 'a "quoted" line\nnext', "moves": [{"kind": "x"}]})
    streamed = "".join(extractor.feed(c) for c in _chunks(body, 5))
    assert streamed == 'a "quoted" line\nnext'


# ------------------------------------------------------- the endpoint


def test_stream_emits_tokens_then_the_full_turn(client):
    with client.stream(
        "POST", f"/studies/{STUDY}/conversation/turns/stream", json={"text": "rct"}
    ) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        events = _events("".join(res.iter_text()))

    kinds = [k for k, _ in events]
    assert "token" in kinds and kinds[-1] == "done"
    streamed = "".join(d["text"] for k, d in events if k == "token")
    assert streamed == _REPLY["text"]

    done = events[-1][1]
    assert done["text"] == _REPLY["text"]
    assert done["source"] == "llm"
    assert [m["kind"] for m in done["moves"]] == ["add-rq"]


def test_streamed_turn_is_stored_like_a_blocking_one(client):
    with client.stream(
        "POST", f"/studies/{STUDY}/conversation/turns/stream", json={"text": "rct"}
    ) as res:
        events = _events("".join(res.iter_text()))
    done = events[-1][1]

    stored = client.get(f"/studies/{STUDY}/conversation").json()["turns"]
    assert [t["role"] for t in stored] == ["researcher", "platform"]
    platform = stored[1]
    assert platform["turnId"] == done["platformTurnId"]
    assert platform["text"] == done["text"]
    assert len(platform["moves"]) == len(done["moves"])


def test_a_broken_stream_falls_back_to_the_blocking_call(client, monkeypatch):
    """A stream that dies mid-reply must still produce the turn — the
    fallback is the whole degradation contract (NFR-4)."""

    class _Broken(_StubClient):
        def stream(self, url, payload, headers):
            yield '{"text": "partial'
            raise ConnectionError("provider hung up")

    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _Broken())
    with client.stream(
        "POST", f"/studies/{STUDY}/conversation/turns/stream", json={"text": "rct"}
    ) as res:
        events = _events("".join(res.iter_text()))

    assert events[-1][0] == "done"
    assert events[-1][1]["text"] == _REPLY["text"]  # from the blocking retry


def test_no_llm_key_still_answers_over_the_stream(client, monkeypatch):
    """With no provider the scripted assistant answers; the stream carries
    no tokens but still delivers the turn."""
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: None)
    with client.stream(
        "POST",
        f"/studies/{STUDY}/conversation/turns/stream",
        json={"text": "over-trust in AI code"},
    ) as res:
        events = _events("".join(res.iter_text()))

    assert [k for k, _ in events] == ["done"]
    assert events[0][1]["source"] == "scripted"
    assert events[0][1]["text"]


def test_streaming_and_blocking_produce_the_same_turn(client, tmp_path):
    """The stream is a view of the reply, not a different reply."""
    blocking = client.post(
        f"/studies/{STUDY}-b/conversation/turns", json={"text": "rct"}
    ).json()
    with client.stream(
        "POST", f"/studies/{STUDY}-s/conversation/turns/stream", json={"text": "rct"}
    ) as res:
        streamed = _events("".join(res.iter_text()))[-1][1]

    assert streamed["text"] == blocking["text"]
    assert [m["kind"] for m in streamed["moves"]] == [
        m["kind"] for m in blocking["moves"]
    ]
    assert streamed["source"] == blocking["source"]


def test_respond_streaming_returns_the_same_dict_as_respond(client, tmp_path):
    """The generator's return value is the ordinary result dict."""
    from middleware.db import make_session_factory

    factory = make_session_factory(f"sqlite:///{tmp_path / 'x.sqlite3'}")
    with factory() as s:
        gen = design_assistant.respond_streaming(
            s, "rct", seq=2, study_id=None, client=_StubClient()
        )
        prose = []
        try:
            while True:
                prose.append(next(gen))
        except StopIteration as done:
            result = done.value
    assert "".join(prose) == _REPLY["text"]
    assert result["text"] == _REPLY["text"]
    assert result["source"] == "llm"
