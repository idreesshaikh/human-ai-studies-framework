#!/usr/bin/env python3
"""Check workspace coverage and the repository's size budget."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"


def check_size() -> bool:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required to count repository files.")
    paths = (
        subprocess.check_output(
            [git, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=REPO,
        )
        .decode()
        .split("\0")
    )
    lockfiles = {"uv.lock", "package-lock.json", "skills-lock.json"}
    lines = 0
    for name in set(paths) - {""}:
        path = REPO / name
        if path.is_symlink() or not path.is_file() or path.name in lockfiles:
            continue
        data = path.read_bytes()
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if "\0" not in content:
            lines += len(content.splitlines())
    print(f"Repository text: {lines:,} lines (must stay below 90,000).")
    return lines < 90_000


def main() -> int:
    with PYPROJECT.open("rb") as fh:
        cfg = tomllib.load(fh)

    members = cfg["tool"]["uv"]["workspace"]["members"]
    testpaths = cfg["tool"]["pytest"]["ini_options"]["testpaths"]
    cov_source = [s.split("/", 1)[0] for s in cfg["tool"]["coverage"]["run"]["source"]]

    problems: list[str] = []

    untested = sorted(set(members) - set(testpaths))
    if untested:
        problems.append(
            "these workspace members are absent from "
            "[tool.pytest.ini_options].testpaths, so their tests never run:\n"
            + "".join(f"    - {m}\n" for m in untested)
        )

    unmeasured = sorted(set(members) - set(cov_source))
    if unmeasured:
        problems.append(
            "these workspace members are absent from [tool.coverage.run].source, "
            "so their lines are excluded from the coverage floor:\n"
            + "".join(f"    - {m}\n" for m in unmeasured)
        )

    for name, extra in (
        ("[tool.pytest.ini_options].testpaths", sorted(set(testpaths) - set(members))),
        ("[tool.coverage.run].source", sorted(set(cov_source) - set(members))),
    ):
        if extra:
            problems.append(
                f"{name} names paths that are not workspace members:\n"
                + "".join(f"    - {p}\n" for p in extra)
            )

    if problems:
        print("pyproject.toml package lists disagree:\n", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(
            "  Fix: make [tool.uv.workspace].members, "
            "[tool.pytest.ini_options].testpaths, and\n"
            "  [tool.coverage.run].source name the same packages.",
            file=sys.stderr,
        )
        return 1

    print(f"Workspace config is consistent ({len(members)} packages).")
    return 0 if check_size() else 1


if __name__ == "__main__":
    sys.exit(main())
