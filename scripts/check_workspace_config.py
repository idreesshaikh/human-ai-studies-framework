#!/usr/bin/env python3
"""Fail when the root pyproject.toml's package lists disagree.

Three lists in the root `pyproject.toml` must name the same packages, and
nothing but a convention was keeping them aligned:

  - ``[tool.uv.workspace].members``   - what the workspace builds
  - ``[tool.pytest.ini_options].testpaths`` - whose tests actually run
  - ``[tool.coverage.run].source``    - whose lines are actually measured

A package present in the first but missing from the second is invisible: its
tests never run, locally or in CI, and the build stays green over unguarded
code. That is not hypothetical - ``curated`` (the FR-CUR curated-dataset leg,
896 lines of source and 11 tests) was absent from ``testpaths`` for its whole
life until this check was written. A package missing from the third is worse than
invisible: it silently *raises* the reported coverage percentage by shrinking
the denominator.

Same idea as the AGENTS.md drift gate (``generate_agents_md.py --check``):
mechanical, so it cannot be forgotten.

    uv run python scripts/check_workspace_config.py     # CI: fail on drift
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"


def main() -> int:
    with PYPROJECT.open("rb") as fh:
        cfg = tomllib.load(fh)

    members = cfg["tool"]["uv"]["workspace"]["members"]
    testpaths = cfg["tool"]["pytest"]["ini_options"]["testpaths"]
    # source entries are "<package>/src"; compare on the package directory.
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

    # A path in testpaths or coverage that is not a workspace member is
    # usually a rename that was only half-applied.
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
