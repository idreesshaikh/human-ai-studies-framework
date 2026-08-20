from pathlib import Path

import pytest
import yaml
from protocol.loader import load_protocol

_TESTS_DIR = Path(__file__).parent


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return _TESTS_DIR / "fixtures"


@pytest.fixture(scope="session")
def example_path() -> Path:
    return _TESTS_DIR.parent / "examples" / "pilot-study.yaml"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return _TESTS_DIR.parents[1]


@pytest.fixture(scope="session")
def pilot(example_path) -> dict:
    """The example pilot protocol, loaded and validated."""
    return load_protocol(example_path)


@pytest.fixture
def pilot_doc(example_path) -> dict:
    """
    The example pilot protocol as a fresh plain (pre-validation) dict, for
    mutation-based invalid-protocol tests.
    """
    return yaml.safe_load(example_path.read_text("utf-8"))


@pytest.fixture
def write_protocol(tmp_path):
    """Dump a protocol dict to a temp YAML file and return its path."""

    def _write(data: dict) -> Path:
        path = tmp_path / "protocol.yaml"
        path.write_text(yaml.safe_dump(data), "utf-8")
        return path

    return _write
