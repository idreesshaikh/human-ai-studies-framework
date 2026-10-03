import runpy
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check_workspace_config.py"


@pytest.mark.parametrize("lines,passes", [(89_999, True), (90_000, False)])
def test_repository_size_boundary(tmp_path, lines, passes):
    check = runpy.run_path(str(SCRIPT))["check_size"]
    check.__globals__["REPO"] = tmp_path
    (tmp_path / "source.py").write_text("pass\n" * lines)
    with patch("subprocess.check_output", return_value=b"source.py\0source.py\0"):
        assert check() is passes


def test_repository_size_counts_docs_but_not_locks_or_binary(tmp_path):
    check = runpy.run_path(str(SCRIPT))["check_size"]
    check.__globals__["REPO"] = tmp_path
    (tmp_path / "package-lock.json").write_text("{}\n" * 90_000)
    (tmp_path / "image.png").write_bytes(b"\x00\n" * 90_000)
    (tmp_path / "guide.md").write_text("text\n" * 90_000)
    with patch(
        "subprocess.check_output", return_value=b"package-lock.json\0image.png\0"
    ):
        assert check()
    with patch("subprocess.check_output", return_value=b"guide.md\0deleted.py\0"):
        assert not check()
