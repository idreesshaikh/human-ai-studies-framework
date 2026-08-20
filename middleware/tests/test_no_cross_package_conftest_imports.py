"""No test file imports another package's ``conftest.py`` by bare name."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

TEST_DIRS = (
    "metrics", "protocol", "middleware", "analysis", "agent-capture", "curated",
)

_BARE_CONFTEST_IMPORT = re.compile(
    r"^\s*(?:from\s+conftest\s+import\s|import\s+conftest\b)", re.MULTILINE
)


def test_no_test_file_imports_a_bare_conftest_module():
    offenders = []
    for test_dir in TEST_DIRS:
        tests_path = REPO_ROOT / test_dir / "tests"
        if not tests_path.is_dir():
            continue
        for path in sorted(tests_path.glob("test_*.py")):
            if _BARE_CONFTEST_IMPORT.search(path.read_text()):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], (
        "these files import 'conftest' by its bare module name, which "
        "collides with every other package's conftest.py under pytest's "
        "flat import mode - keep a local copy of the helpers instead:\n"
        + "\n".join(f"  - {o}" for o in offenders)
    )
