"""Find candidate study-template drafts from recurring literature vocabulary.

The command reports or writes drafts only. It never changes the supported
template registry; registry changes remain a reviewed, manual decision.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "middleware" / "src"))
sys.path.insert(0, str(REPO / "analysis" / "src"))

from middleware.db import make_session_factory  # noqa: E402
from middleware.settings import Settings  # noqa: E402

from middleware import mine_designs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gaps",
        action="store_true",
        help="Report methodology phrases the corpus uses that no registry "
        "template claims, then exit. The report identifies gaps; it does not "
        "author a template.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write qualifying drafts to templates/drafts/ as YAML. "
        "Without this flag, nothing is written.",
    )
    parser.add_argument(
        "--min-papers",
        type=int,
        default=8,
        help="Minimum corpus support for a cluster (default 8).",
    )
    parser.add_argument(
        "--min-phrases",
        type=int,
        default=2,
        help="Minimum distinct design phrases for a cluster (default 2).",
    )
    args = parser.parse_args()

    settings = Settings()
    session_factory = make_session_factory(settings.db_url)
    s = session_factory()
    try:
        if args.gaps:
            gaps = mine_designs.uncovered_methodology_phrases(s)
            if not gaps:
                print("No uncovered methodology phrases above the support floor.")
                return 0
            print("Methodology phrases no registry template's designSignature claims:")
            print(f"{'papers':>7}  phrase")
            for g in gaps:
                print(f"{g['papers']:>7}  {g['phrase']}")
            print()
            print(
                "Each row is a gap, not a template. Read the source papers before "
                "drafting a design."
            )
            return 0

        drafts = mine_designs.mine_and_draft(s, write_files=False)
        qualifying = [
            d
            for d in drafts
            if d["valid"]
            and d["count"] >= args.min_papers
            and len(d["phrases"]) >= args.min_phrases
        ]

        print(mine_designs.report_drafts(drafts))
        print()
        print(
            f"{len(qualifying)}/{len(drafts)} clusters clear the review-worthy "
            f"bar (>= {args.min_papers} papers, >= {args.min_phrases} phrases)."
        )

        if not args.write:
            print("Dry run; nothing written. Pass --write to save drafts.")
            return 0

        if not qualifying:
            print("Nothing to write.")
            return 0

        paths = mine_designs.write_drafts(qualifying)
        print(f"Wrote {len(paths)} draft(s) to templates/drafts/:")
        for path in paths:
            print(f"  {path.name}")
        print("Review the drafts before adding any supported template.")
        return 0
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(main())
