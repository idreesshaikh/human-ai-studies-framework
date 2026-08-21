"""
Corpus-mining pipeline (FR-TPL-5): cluster the paper corpus by recurring design
vocabulary, draft a template YAML for each cluster with real support, and queue
the ones that validate as `pending` TemplateSubmission rows for human review.

Mining never writes into templates/registry/ directly — approval is a human
decision made through the existing submissions review queue at /submissions,
the same door a hand-authored contribution uses (see
middleware/src/middleware/mine_designs.py:submit_drafts).

Usage:
    uv run python scripts/mine_templates.py                 # report only
    uv run python scripts/mine_templates.py --submit         # also queue them
    uv run python scripts/mine_templates.py --min-papers 15 --min-phrases 2
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
        "template claims, and exit. This is the registry's blind-spot list — "
        "evidence that a design archetype exists in the literature with no "
        "shape for it here. Authoring the shape is human work; the report "
        "only says where to look.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Queue qualifying drafts as pending TemplateSubmission rows. "
        "Without this flag, only the report is printed — nothing is written.",
    )
    parser.add_argument(
        "--min-papers",
        type=int,
        default=8,
        help="Minimum corpus support to even consider a cluster (default 8). "
        "The single-generic-word clusters (\"coding\", \"measuring\") clear the "
        "mining script's own min_papers=3 floor easily on volume alone; this "
        "second, stricter gate is what keeps the review queue from filling "
        "with clusters no reviewer would find worth a decision.",
    )
    parser.add_argument(
        "--min-phrases",
        type=int,
        default=2,
        help="Minimum distinct design phrases a cluster must carry (default "
        "2) — a real methodological signature reads as more than one bare "
        "keyword ('coding' alone) matching by coincidence.",
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
                "Each row is evidence a design exists in the literature that the "
                "repertoire has no shape for — not a template. Read the papers "
                "behind a phrase before authoring one."
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

        if not args.submit:
            print("Dry run — nothing written. Pass --submit to queue these.")
            return 0

        if not qualifying:
            print("Nothing to submit.")
            return 0

        ids = mine_designs.submit_drafts(s, qualifying)
        print(f"Queued {len(ids)} pending TemplateSubmission rows: {ids}")
        print("Review them at /submissions.")
        return 0
    finally:
        s.close()


if __name__ == "__main__":
    sys.exit(main())
