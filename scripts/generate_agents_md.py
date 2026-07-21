#!/usr/bin/env python3
"""Generate AGENTS.md from the documents of record.

AGENTS.md is the context file an agent working *in this repository* reads. It
is **generated, never hand-maintained** — context that drifts is worse than
no context. Its inputs are all documents of record:

  - the glossary            (requirements/glossary.md, via redocs.parse_glossary)
  - the SRS index           (requirements/srs.md, via redocs.parse_srs)
  - a platform-manifest snapshot (middleware.manifest, deterministic form)
  - the System invariants   (parsed from CLAUDE.md by heading — CLAUDE.md
                             itself stays hand-written; it is the generator's
                             *input* for invariants, so human judgment stays
                             human and only facts get generated)

Generation is **deterministic**: stable ordering, no timestamps in the
content. So `git diff --exit-code AGENTS.md` after regeneration is a
meaningful drift check — editing the glossary without regenerating turns CI
red, exactly like a lockfile (F2.1/F2.2).

    uv run python scripts/generate_agents_md.py            # write AGENTS.md
    uv run python scripts/generate_agents_md.py --check    # CI: fail on drift
    uv run python scripts/generate_agents_md.py --stdout   # print, don't write
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GLOSSARY = REPO / "requirements" / "glossary.md"
SRS = REPO / "requirements" / "srs.md"
CLAUDE_MD = REPO / "CLAUDE.md"
OUTPUT = REPO / "AGENTS.md"

# The heading whose section we lift verbatim from CLAUDE.md. The section runs
# to the next second-level heading.
INVARIANTS_HEADING = "## System invariants"

GENERATED_NOTICE = (
    "<!-- GENERATED FILE — do not edit by hand. Regenerate with\n"
    "     `uv run python scripts/generate_agents_md.py`. Its inputs are the\n"
    "     glossary, the SRS, a manifest snapshot, and CLAUDE.md's System\n"
    "     invariants section. CI fails if this file drifts from its sources\n"
    "     (FR-AGF-2). -->"
)


def _invariants_section(claude_md: str) -> str:
    """Lift the System-invariants section from CLAUDE.md verbatim (the human
    judgment stays human; the generator only relocates the facts)."""
    lines = claude_md.splitlines()
    out: list[str] = []
    capturing = False
    for line in lines:
        if line.startswith(INVARIANTS_HEADING):
            capturing = True
            continue
        if capturing and line.startswith("## "):
            break
        if capturing:
            out.append(line)
    return "\n".join(out).strip()


def build_agents_md() -> str:
    """Assemble AGENTS.md deterministically from the documents of record."""
    # Import here so the script runs even if middleware deps shift; these are
    # workspace siblings.
    from middleware.redocs import parse_glossary, parse_srs

    from middleware import manifest as manifest_mod

    glossary = parse_glossary(GLOSSARY)
    srs = parse_srs(SRS)
    snapshot = manifest_mod.generate_manifest(deployment="hosted").to_dict(
        deterministic=True
    )
    invariants = _invariants_section(CLAUDE_MD.read_text("utf-8"))

    parts: list[str] = []
    parts.append("# AGENTS.md — context for agents working in this repository")
    parts.append("")
    parts.append(GENERATED_NOTICE)
    parts.append("")
    parts.append(
        "This file orients an AI agent (Claude Code, a browser agent, or an "
        "SDK agent) working in this repository. Every section below is "
        "generated from a document of record, so it never drifts from the "
        "truth. For the live deployment's API, fetch "
        "`/.well-known/platform-manifest`."
    )
    parts.append("")

    # 1. Platform snapshot (from the generated manifest).
    parts.append("## Platform")
    parts.append("")
    parts.append(f"- **Name:** {snapshot['platform']['name']}")
    parts.append(f"- **Version:** {snapshot['platform']['version']}")
    parts.append(f"- **Capabilities:** {', '.join(snapshot['capabilities'])}")
    parts.append(
        f"- **Protocol schema versions:** "
        f"{snapshot['schemas']['protocol']['versions']} "
        "(consumers branch on version, never guess)"
    )
    parts.append(
        f"- **Event schema versions:** {snapshot['schemas']['event']['versions']}"
    )
    parts.append(
        f"- **Corpus:** {snapshot['corpus']['count']} papers "
        f"({snapshot['corpus']['tierA']} Tier A + "
        f"{snapshot['corpus']['tierB']} Tier B); "
        f"**templates:** {snapshot['templates']['count']}"
    )
    parts.append("")

    # 2. System invariants (verbatim from CLAUDE.md).
    parts.append("## System invariants (violating these breaks the science)")
    parts.append("")
    parts.append(invariants)
    parts.append("")

    # 3. Vocabulary (the glossary — code identifiers and schema fields follow
    #    these terms).
    parts.append("## Vocabulary")
    parts.append("")
    parts.append(
        "Use these terms in code identifiers, schema fields, and prose "
        "(`participant` not `user`, `condition` not `group`, `recipe` not "
        "`script`). Terminology disputes are settled by editing the glossary "
        "first."
    )
    parts.append("")
    for entry in sorted(glossary, key=lambda e: e["term"].lower()):
        definition = re.sub(r"\s+", " ", entry["definition"]).strip()
        parts.append(f"- **{entry['term']}** — {definition}")
    parts.append("")

    # 4. Requirements index (IDs + one-liners — the map from feature to spec).
    parts.append("## Requirements index")
    parts.append("")
    parts.append(
        "Every feature traces to a requirement ID. The full text lives in "
        "`requirements/srs.md`; this is the index."
    )
    parts.append("")
    for row in srs:
        status = row.get("status", "")
        text = re.sub(r"\s+", " ", row["text"]).strip()
        # Keep each row to one line; trim overly long requirement prose.
        if len(text) > 200:
            text = text[:197].rstrip() + "…"
        parts.append(
            f"- **{row['id']}** ({row.get('priority', '?')}) {text} — _{status}_"
        )
    parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail (exit 1) if AGENTS.md differs from freshly generated "
        "content — the CI drift gate (FR-AGF-2 F2.2)",
    )
    parser.add_argument(
        "--stdout", action="store_true", help="print to stdout, don't write"
    )
    args = parser.parse_args()

    content = build_agents_md()

    if args.stdout:
        print(content, end="")
        return 0

    if args.check:
        existing = OUTPUT.read_text("utf-8") if OUTPUT.exists() else ""
        if existing != content:
            print(
                "AGENTS.md is stale — a document of record changed but "
                "AGENTS.md was not regenerated.\n"
                "Run: uv run python scripts/generate_agents_md.py",
                file=sys.stderr,
            )
            return 1
        print("AGENTS.md is up to date.")
        return 0

    OUTPUT.write_text(content, "utf-8")
    print(f"Wrote {OUTPUT.relative_to(REPO)} ({len(content)} bytes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
