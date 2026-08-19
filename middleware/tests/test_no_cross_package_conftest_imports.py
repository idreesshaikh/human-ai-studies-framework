"""No test file imports another package's ``conftest.py`` by bare name.

None of the test directories in this workspace (`middleware/tests/`,
`agent-capture/tests/`, `protocol/tests/`, `analysis/tests/`, `curated/tests/`)
are proper packages - none carries an ``__init__.py``. Under pytest's default
"prepend" import mode that means every one of their ``conftest.py`` files
shares the *same* bare module name, ``conftest``: whichever one pytest
imports first wins that name in ``sys.modules``, and every later
``from conftest import ...`` anywhere in the run resolves against that same
one, not the file that actually sits next to it.

This was a real, silent failure: ``middleware/tests/test_simulation.py`` did
``from conftest import _STUDY_SKETCH, _accept, ...``. It collected and passed
cleanly when run alone (only middleware's own ``conftest.py`` was ever
imported), and failed collection entirely the moment the *whole* workspace
ran together - exactly how CI invokes it - because
``agent-capture/tests/conftest.py`` had already claimed the name and does not
define any of those symbols.

The established fix in this codebase (``test_evolution.py``,
``test_conversation.py``) is for a file to keep its own small local copy of
whatever conftest helpers it needs, never to import a sibling file's
``conftest.py`` across a package boundary. This test makes that convention
mechanical rather than a thing to remember.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Every directory pytest collects tests from (testpaths in pyproject.toml),
#: each without an __init__.py - the precondition for the collision.
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
