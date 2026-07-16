"""`analysis` CLI (FR-ANA-4).

    analysis run protocol/examples/pilot-study.yaml            # fetch from :8000
    analysis run pilot.yaml --dataset export.json --out results
    analysis validate pilot.yaml                               # FR-ANA-2 check only
    analysis list                                              # registered recipes

Exit codes: 0 = everything ran; 1 = hard error (bad arguments, no data);
2 = the report was written but the plan had validation failures or a
recipe raised - loud by design, scripts must notice.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import analysis.recipes  # noqa: F401 - registers the built-in recipes
from analysis.core import REGISTRY, validate_plan
from analysis.dataset import Dataset
from analysis.runner import run_plan

DEFAULT_SERVER = "http://127.0.0.1:8000"


def _load_protocol(path: str) -> dict:
    from protocol.loader import load_protocol

    return load_protocol(Path(path))


def _load_dataset(args: argparse.Namespace, study_id: str) -> Dataset:
    if args.dataset:
        return Dataset.from_json(args.dataset)
    try:
        return Dataset.fetch(args.server, study_id)
    except OSError as exc:
        raise SystemExit(
            f"error: could not fetch dataset for {study_id!r} from "
            f"{args.server} ({exc}); is the middleware running, or pass "
            "--dataset <export.json>"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="analysis", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def add_data_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("protocol", help="study protocol YAML (the analysis plan)")
        p.add_argument("--study", help="study id (default: the protocol's)")
        p.add_argument("--server", default=DEFAULT_SERVER,
                       help=f"middleware base URL (default {DEFAULT_SERVER})")
        p.add_argument("--dataset", help="one-timeline dataset JSON file "
                       "(instead of fetching from the middleware)")

    p_run = sub.add_parser("run", help="run the protocol's analysis plan")
    add_data_args(p_run)
    p_run.add_argument("--out", default="results", type=Path,
                       help="output root (default results/)")

    p_val = sub.add_parser(
        "validate", help="check recipe requirements only (FR-ANA-2)"
    )
    add_data_args(p_val)

    p_paper = sub.add_parser(
        "paper", help="generate a paper draft (MD + LaTeX) from protocol + "
        "recipes (FR-ANA-6)"
    )
    add_data_args(p_paper)
    p_paper.add_argument("--out", default="results", type=Path,
                         help="output root (default results/)")

    p_retro = sub.add_parser(
        "retrospective", help="draft a self-improvement changelist proposal "
        "from the findings log (FR-META-2)"
    )
    p_retro.add_argument("protocol", help="study protocol YAML")
    p_retro.add_argument("--study", help="study id (default: the protocol's)")
    p_retro.add_argument("--server", default=DEFAULT_SERVER,
                         help=f"middleware base URL (default {DEFAULT_SERVER})")
    p_retro.add_argument("--findings-md",
                         help="facilitator findings.md (e.g. study/pilot/findings.md)")
    p_retro.add_argument("--out", default="retrospective", type=Path,
                         help="output directory (default retrospective/)")

    p_list = sub.add_parser("list", help="list registered recipes")
    p_list.add_argument(
        "--json", action="store_true",
        help="machine-readable registry (consumed by `protocol export "
        "replication-kit` for the kit manifest)",
    )

    args = parser.parse_args(argv)

    if args.command == "list":
        if args.json:
            print(json.dumps([
                {
                    "id": rec.id,
                    "title": rec.title,
                    "answers": list(rec.answers),
                    "requiresEvents": sorted(rec.requires.events),
                    "requiresMetrics": sorted(rec.requires.metrics),
                }
                for rec in sorted(REGISTRY.values(), key=lambda r: r.id)
            ], indent=2))
            return 0
        for rec in REGISTRY.values():
            req = ", ".join(
                sorted(rec.requires.events)
                + [f"metric:{m}" for m in sorted(rec.requires.metrics)]
            )
            print(f"{rec.id:32} answers {','.join(rec.answers):22} requires {req}")
        return 0

    protocol = _load_protocol(args.protocol)
    study_id = args.study or protocol["study"]["id"]

    if args.command == "retrospective":
        from analysis.retrospective import cmd_retrospective

        return cmd_retrospective(protocol, study_id, args)

    dataset = _load_dataset(args, study_id)

    if args.command == "validate":
        checks = validate_plan(protocol.get("analysisPlan", []), dataset)
        failures = [c for c in checks if not c.ok]
        for c in checks:
            print(("FAIL " if not c.ok else "ok   ") + c.describe())
        return 1 if failures else 0

    if args.command == "paper":
        from analysis.paper_cli import cmd_paper

        return cmd_paper(protocol, dataset, study_id, args)

    outcome = run_plan(
        protocol,
        dataset,
        study_id,
        out_root=args.out,
        server=None if args.dataset else args.server,
    )
    if not outcome.ok:
        print(
            f"completed with {len(outcome.failed_validation)} validation "
            f"failure(s) and {len(outcome.errors)} recipe error(s) - see "
            "the report's validation section",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
