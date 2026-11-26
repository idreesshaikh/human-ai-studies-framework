"""Streamed design turn (D3): SSE token frames + an identical stored turn."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from fastapi.testclient import TestClient
from middleware.app import create_app
from middleware.db import ConversationTurn
from middleware.settings import Settings
from middleware.study_plan import ReplyExtractor
from sqlalchemy import event
from sqlalchemy.orm import Session

from middleware import assistant

STUDY = "stream-study"
MESSAGE = "Does Copilot change how long developers take to fix bugs?"

_REPLY = {
    "reply": "Here is a within-subjects design.\n\nIt measures task time.",
    "questions": [],
    "changes": {
        "researchQuestions": ["Does AI assistance change task completion time?"]
    },
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


def test_extractor_yields_prose_not_json():
    """The researcher sees prose, never the braces of the JSON envelope."""
    extractor = ReplyExtractor()
    body = json.dumps({"reply": "Hello there", "changes": {}})
    streamed = "".join(extractor.feed(c) for c in _chunks(body, 3))
    assert streamed == "Hello there"


def test_extractor_decodes_escapes_and_stops_at_the_close():
    extractor = ReplyExtractor()
    body = json.dumps({"reply": 'a "quoted" line\nnext', "changes": {"title": "x"}})
    streamed = "".join(extractor.feed(c) for c in _chunks(body, 5))
    assert streamed == 'a "quoted" line\nnext'


@pytest.mark.parametrize("size", [1, 2, 5, 17])
@pytest.mark.parametrize("ascii_escaped", [True, False])
def test_extractor_preserves_multilingual_text_and_emoji(size, ascii_escaped):
    text = 'Grüße, 日本語, العربية, 👩🏽‍💻.\n"quoted" \\ slash /\tend'
    body = json.dumps({"reply": text, "changes": {}}, ensure_ascii=ascii_escaped)
    extractor = ReplyExtractor()
    assert "".join(extractor.feed(c) for c in _chunks(body, size)) == text
    assert extractor.text == text


@pytest.mark.parametrize("value", [None, 42, [], {}])
def test_extractor_never_streams_json_keys_for_nontext_values(value):
    body = json.dumps({"reply": value, "changes": {"title": "caution"}})
    extractor = ReplyExtractor()
    assert "".join(extractor.feed(c) for c in _chunks(body, 2)) == ""


def test_stream_emits_tokens_then_the_full_turn(client):
    with client.stream(
        "POST", f"/studies/{STUDY}/conversation/turns/stream", json={"text": MESSAGE}
    ) as res:
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("text/event-stream")
        events = _events("".join(res.iter_text()))

    kinds = [k for k, _ in events]
    assert "token" in kinds and kinds[-1] == "done"
    streamed = "".join(d["text"] for k, d in events if k == "token")
    assert streamed == _REPLY["reply"]

    done = events[-1][1]
    assert done["text"] == _REPLY["reply"]
    assert done["source"] == "llm"
    assert [m["kind"] for m in done["moves"]] == ["set-plan"]
    stored = client.get(f"/studies/{STUDY}/conversation").json()["turns"]
    assert [turn["role"] for turn in stored] == ["researcher", "platform"]
    assert stored[1]["turnId"] == done["platformTurnId"]
    assert stored[1]["text"] == done["text"]
    assert len(stored[1]["moves"]) == len(done["moves"])


def test_retried_stream_replays_without_duplicate_turns(client):
    """A stream that committed before disconnecting is safe to retry."""
    body = {"text": MESSAGE, "requestId": "request-once"}
    with client.stream(
        "POST", f"/studies/{STUDY}/conversation/turns/stream", json=body
    ) as res:
        first = _events("".join(res.iter_text()))[-1][1]

    with client.stream(
        "POST", f"/studies/{STUDY}/conversation/turns/stream", json=body
    ) as res:
        replay_events = _events("".join(res.iter_text()))

    assert [kind for kind, _ in replay_events] == ["done"]
    replay = replay_events[0][1]
    assert replay["researcherTurnId"] == first["researcherTurnId"]
    assert replay["platformTurnId"] == first["platformTurnId"]
    turns = client.get(f"/studies/{STUDY}/conversation").json()["turns"]
    assert [turn["role"] for turn in turns] == ["researcher", "platform"]


@pytest.mark.parametrize("same_message", [True, False])
def test_overlapping_stream_and_blocking_turn(client, same_message):
    path = f"/studies/{STUDY}/conversation"
    initial = {"text": MESSAGE, "requestId": "original"}
    retry = initial if same_message else {"text": "different", "requestId": "other"}
    barrier = Barrier(2, timeout=5)

    def wait_before_insert(session, *_):
        if any(
            isinstance(row, ConversationTurn) and row.role == "researcher"
            for row in session.new
        ):
            barrier.wait()

    # Force both requests to calculate the same sequence before either inserts.
    event.listen(Session, "before_flush", wait_before_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            streaming = pool.submit(client.post, f"{path}/turns/stream", json=initial)
            blocking = pool.submit(client.post, f"{path}/turns", json=retry)
            stream_response, block_response = streaming.result(), blocking.result()
    finally:
        event.remove(Session, "before_flush", wait_before_insert)

    stream_event, stream_reply = _events(stream_response.text)[-1]
    if same_message:
        assert stream_event == "done"
        assert block_response.status_code == 200
        assert stream_reply["platformTurnId"] == block_response.json()["platformTurnId"]
    elif stream_event == "done":
        assert block_response.status_code == 409
    else:
        assert stream_reply["status"] == 409
        assert block_response.status_code == 200
    assert len(client.get(path).json()["turns"]) == 2


@pytest.mark.parametrize("suffix", ["", "/stream"])
@pytest.mark.parametrize("remove_study", [False, True])
def test_waiting_for_model_does_not_block_database_writes(
    client, monkeypatch, suffix, remove_study
):
    started = Event()
    release = Event()

    class SlowClient(_StubClient):
        def post(self, *args, **kwargs):
            started.set()
            assert release.wait(10), "the unrelated write did not finish"
            return super().post(*args, **kwargs)

        def stream(self, *args, **kwargs):
            started.set()
            assert release.wait(10), "the unrelated write did not finish"
            yield from super().stream(*args, **kwargs)

    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: SlowClient())
    created = client.post("/projects/implicit/studies", json={"name": "Wait fixture"})
    assert created.is_success
    study_path = f"/studies/{created.json()['id']}"
    path = f"{study_path}/conversation"
    with ThreadPoolExecutor(max_workers=2) as pool:
        turn = pool.submit(client.post, f"{path}/turns{suffix}", json={"text": MESSAGE})
        try:
            assert started.wait(5)
            if remove_study:
                write = pool.submit(client.delete, study_path)
            else:
                write = pool.submit(
                    client.post,
                    "/projects/implicit/studies",
                    json={"name": "Independent"},
                )
            assert write.result(timeout=5).is_success
            assert client.get(path).json()["turns"] == []
        finally:
            release.set()
        response = turn.result(timeout=5)
    turns = client.get(path).json()["turns"]
    if remove_study:
        if suffix:
            kind, error = _events(response.text)[-1]
            assert kind == "error"
            assert error["status"] == 404
        else:
            assert response.status_code == 404
        assert turns == []
    else:
        assert response.is_success
        assert [turn["role"] for turn in turns] == ["researcher", "platform"]


@pytest.mark.parametrize("suffix", ["", "/stream"])
def test_request_id_cannot_replay_a_different_message(client, suffix):
    path = f"/studies/{STUDY}/conversation"
    assert (
        client.post(
            f"{path}/turns", json={"text": MESSAGE, "requestId": "original"}
        ).status_code
        == 200
    )
    response = client.post(
        f"{path}/turns{suffix}", json={"text": "edited", "requestId": "original"}
    )
    assert response.status_code == 409
    assert len(client.get(path).json()["turns"]) == 2


@pytest.mark.parametrize("suffix", ["", "/stream"])
def test_invalid_decision_is_an_http_conflict_without_recording_a_turn(client, suffix):
    response = client.post(
        f"/studies/{STUDY}/conversation/turns{suffix}",
        json={
            "text": "Accepted.",
            "decision": {"moveId": "missing-card", "action": "accepted"},
        },
    )
    assert response.status_code == 409
    assert client.get(f"/studies/{STUDY}/conversation").json()["turns"] == []


def test_unexpected_stream_failure_is_generic_and_rolls_back(client, monkeypatch):
    from middleware import design_assistant

    def broken(*args, **kwargs):
        yield "Before failure"
        raise RuntimeError("database error includes private internal details")

    monkeypatch.setattr(design_assistant, "respond_streaming", broken)
    response = client.post(
        f"/studies/{STUDY}/conversation/turns/stream", json={"text": MESSAGE}
    )
    events = _events(response.text)
    assert [kind for kind, _ in events] == ["token", "error"]
    assert "try again" in events[-1][1]["detail"]
    assert "private internal" not in response.text
    assert client.get(f"/studies/{STUDY}/conversation").json()["turns"] == []


def test_a_broken_stream_falls_back_to_the_blocking_call(client, monkeypatch):
    """
    A stream that dies mid-reply must still produce the turn  -  the fallback is the
    whole degradation contract (NFR-4).
    """

    class _Broken(_StubClient):
        def stream(self, url, payload, headers):
            yield '{"reply": "partial'
            raise ConnectionError("provider hung up")

    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _Broken())
    with client.stream(
        "POST", f"/studies/{STUDY}/conversation/turns/stream", json={"text": MESSAGE}
    ) as res:
        events = _events("".join(res.iter_text()))

    assert events[-1][0] == "done"
    assert events[-1][1]["text"] == _REPLY["reply"]


def test_a_rate_limited_stream_is_not_retried_as_a_blocking_call(client, monkeypatch):
    """The stream transport already waited and retried the rate limit; a
    blocking call would spend the same limit again before saying so."""
    import urllib.error

    blocking_calls = []

    class _Limited(_StubClient):
        def stream(self, url, payload, headers):
            yield from ()
            raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)

        def post(self, *args, **kwargs):
            blocking_calls.append(args)
            return super().post(*args, **kwargs)

    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: _Limited())
    with client.stream(
        "POST", f"/studies/{STUDY}/conversation/turns/stream", json={"text": MESSAGE}
    ) as res:
        events = _events("".join(res.iter_text()))

    kind, done = events[-1]
    assert kind == "done"
    assert done["source"] == "unavailable"
    assert "rate-limiting" in done["text"]
    assert blocking_calls == []


def test_no_model_closes_the_stream_with_a_holding_turn(client, monkeypatch):
    """
    With no provider the stream still closes normally, carrying a holding turn that
    proposes nothing  -  not an ``error`` frame (which leaves the thread looking broken)
    and not an invented reply.
    """
    monkeypatch.setattr(assistant, "make_client", lambda *a, **k: None)
    with client.stream(
        "POST",
        f"/studies/{STUDY}/conversation/turns/stream",
        json={"text": "over-trust in AI code"},
    ) as res:
        events = _events("".join(res.iter_text()))

    assert [k for k, _ in events] == ["done"]
    done = events[0][1]
    assert done["source"] == "unavailable"
    assert done["moves"] == []
    assert "LLM_API_KEY" in done["text"]

    turns = client.get(f"/studies/{STUDY}/conversation").json()["turns"]
    assert any(t["text"] == "over-trust in AI code" for t in turns)


def test_streaming_and_blocking_produce_the_same_turn(client, tmp_path):
    """The stream is a view of the reply, not a different reply."""
    blocking = client.post(
        f"/studies/{STUDY}-b/conversation/turns", json={"text": MESSAGE}
    ).json()
    with client.stream(
        "POST", f"/studies/{STUDY}-s/conversation/turns/stream", json={"text": MESSAGE}
    ) as res:
        streamed = _events("".join(res.iter_text()))[-1][1]

    assert streamed["text"] == blocking["text"]
    assert [m["kind"] for m in streamed["moves"]] == [
        m["kind"] for m in blocking["moves"]
    ]
    assert streamed["source"] == blocking["source"]
