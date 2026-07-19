import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_capture.events import Keys

_TESTS_DIR = Path(__file__).parent
_REPO_ROOT = _TESTS_DIR.parents[1]
_PILOT = _REPO_ROOT / "protocol" / "examples" / "pilot-study.yaml"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return _TESTS_DIR / "fixtures"


@pytest.fixture(scope="session")
def transcript_path(fixtures_dir) -> Path:
    """A recorded-shape Claude Code transcript, anonymized (no real code
    content; the assistant text is placeholder)."""
    return fixtures_dir / "sample-transcript.jsonl"


@pytest.fixture()
def keys() -> Keys:
    return Keys(participant_id="P01", condition="ai-assisted", session_id="S1")


@pytest.fixture()
def middleware(tmp_path):
    """A middleware TestClient built against the real pilot protocol, so the
    agent leg's join keys are validated end to end (v4 events are known)."""
    from fastapi.testclient import TestClient
    from middleware.app import create_app
    from middleware.settings import Settings

    settings = Settings(
        db_path=tmp_path / "test.sqlite3",
        data_dir=tmp_path / "data",
        protocol_path=_PILOT,
        spa_dist=tmp_path / "no-dist",
    )
    return TestClient(
        create_app(settings, clock=lambda: datetime(2026, 7, 12, 12, tzinfo=UTC))
    )


@pytest.fixture()
def hook_payload(transcript_path):
    """The stdin JSON Claude Code passes a hook, pointing at the fixture."""
    return json.dumps(
        {
            "session_id": "cc-abc",
            "transcript_path": str(transcript_path),
            "cwd": "/work/task-a",
            "hook_event_name": "Stop",
        }
    )
