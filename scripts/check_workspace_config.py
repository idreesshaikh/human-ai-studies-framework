#!/usr/bin/env python3
"""Check workspace coverage and documented environment configuration."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PYPROJECT = REPO / "pyproject.toml"


SOURCES = ("middleware/src", "analysis/src", "protocol/src", "scripts")
# Standard process environment variables.
PLATFORM_PROVIDED = {"PORT", "USER"}

_DIRECT = re.compile(
    r"""os\.environ(?:\.get\()\s*["']([A-Z0-9_]+)["']"""
    r"""|os\.environ\[\s*["']([A-Z0-9_]+)["']"""
    r"""|os\.getenv\(\s*["']([A-Z0-9_]+)["']"""
)
_HELPER_ARGS = re.compile(r"_env\(([^)]*)\)")
_HELPER_NAME = re.compile(r"""["']([A-Z][A-Z0-9_]{3,})["']""")
_NUMBER_ENV = re.compile(r"""_number_env\(\s*["']([A-Z][A-Z0-9_]+)["']""")


def _names_read() -> set[str]:
    names: set[str] = set()
    for root in SOURCES:
        for path in (REPO / root).rglob("*.py"):
            text = path.read_text()
            for match in _DIRECT.finditer(text):
                names.add(next(g for g in match.groups() if g))
            for call in _HELPER_ARGS.finditer(text):
                names.update(_HELPER_NAME.findall(call.group(1)))
            names.update(_NUMBER_ENV.findall(text))
    return names


def _documented() -> set[str]:
    text = (REPO / ".env.example").read_text()
    return set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, re.M))


def _environment_problems() -> list[str]:
    problems = []
    missing = sorted(_names_read() - _documented() - PLATFORM_PROVIDED)
    if missing:
        problems.append(f"undocumented in .env.example: {', '.join(missing)}")
    return problems


def main() -> int:
    with PYPROJECT.open("rb") as fh:
        cfg = tomllib.load(fh)

    members = cfg["tool"]["uv"]["workspace"]["members"]
    testpaths = cfg["tool"]["pytest"]["ini_options"]["testpaths"]
    cov_source = [s.split("/", 1)[0] for s in cfg["tool"]["coverage"]["run"]["source"]]

    problems: list[str] = _environment_problems()

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
        print("Project configuration is inconsistent:\n", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(
            "  Fix: make [tool.uv.workspace].members, "
            "[tool.pytest.ini_options].testpaths, and\n"
            "  [tool.coverage.run].source name the same packages.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Project config is consistent ({len(members)} packages; "
        "environment documented)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
