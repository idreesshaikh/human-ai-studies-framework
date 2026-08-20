"""``python -m middleware`` - run the ingestion service or CLI commands."""

import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


def _auth_headers() -> dict:
    token = os.environ.get("MIDDLEWARE_TOKEN", "")
    return {"authorization": f"Bearer {token}"} if token else {}


def _post(server: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(  # noqa: S310
        f"{server.rstrip('/')}{path}",
        data=json.dumps(body).encode(),
        headers={**_auth_headers(), "content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as res:  # noqa: S310
        return json.loads(res.read())


def _get(server: str, path: str) -> dict:
    req = urllib.request.Request(  # noqa: S310
        f"{server.rstrip('/')}{path}", headers=_auth_headers(), method="GET"
    )
    with urllib.request.urlopen(req, timeout=60) as res:  # noqa: S310
        return json.loads(res.read())

def _get_raw(server: str, path: str) -> str:
    req = urllib.request.Request(  # noqa: S310
        f"{server.rstrip('/')}{path}", headers=_auth_headers()
    )
    with urllib.request.urlopen(req, timeout=60) as res:  # noqa: S310
        return res.read().decode("utf-8")


def cmd_ethics(study_id: str, server: str, out: str | None = None) -> int:
    """Download the study's ethics package (Markdown) via the platform route."""
    text = _get_raw(server, f"/studies/{study_id}/ethics-package")
    if out:
        Path(out).write_text(text)
        print(f"ethics package: {out}")
    else:
        print(text)
    return 0


def cmd_simulate(
    study_id: str,
    server: str,
    count: int,
    profile: str,
    seed: int | None,
    protocol_path: str | None = None,
) -> int:
    """
    Dry-run a study over plain HTTP, then validate the analysis plan on the synthetic
    data.
    """
    import analysis.recipes  # noqa: F401 - registers the built-in recipes
    import yaml
    from analysis.dataset import Dataset
    from analysis.runner import run_plan

    protocol: dict = {}
    if protocol_path:
        protocol = yaml.safe_load(Path(protocol_path).read_text()) or {}
    if not protocol.get("analysisPlan"):
        export = _get(server, f"/studies/{study_id}/conversation/export")
        protocol = yaml.safe_load(export.get("currentDraft") or "{}") or {}
    if not protocol.get("analysisPlan"):
        print(
            "protocol has no analysis plan to validate "
            "(pass --protocol <yaml> for a boot-protocol study)"
        )
        return 2
    outcome = _post(
        server,
        f"/studies/{study_id}/simulate",
        {"count": count, "profile": profile, "seed": seed},
    )
    print(
        f"simulated {outcome['participants']} participants "
        f"({outcome['profile']}): {outcome['sessions']} sessions, "
        f"{outcome['events']} events, {outcome['metricRows']} metric rows, "
        f"{outcome['tokensMinted']} tokens minted"
    )
    dataset = Dataset.fetch(server, study_id)
    print(f"dataset: {len(dataset.rows)} joined rows")
    outcome_run = run_plan(protocol, dataset, study_id, out_root=Path("results"))
    failed = len(outcome_run.failed_validation)
    print(
        f"plan validation: {len(outcome_run.executed)} recipe(s) ran, "
        f"{failed} check(s) failed; report under results/{study_id}/"
    )
    return 1 if failed else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Middleware server and CLI (FR-ING-1, FR-LIT-8/9, FR-TPL-1)"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=[
            "serve",
            "corpus-import",
            "corpus-verify",
            "corpus-enrich",
            "demo-seed",
            "templates",
            "simulate",
            "ethics-package",
        ],
        help="Command to run (default: serve)",
    )
    parser.add_argument(
        "study_id",
        nargs="?",
        default=None,
        help="simulate / ethics-package: the study id to dry-run or export",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="SQLite DB path (overrides MIDDLEWARE_DB; "
        "ignored when DATABASE_URL is set)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="corpus-enrich: cap how many papers to backfill "
        "(highest confidence first; default: every one still missing)",
    )
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:8000",
        help="simulate: middleware base URL (default http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="simulate: how many synthetic participants (default 5)",
    )
    parser.add_argument(
        "--profile",
        default="mixed",
        help="simulate: mixed|fast|struggling|novice|expert (default mixed)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="simulate: RNG seed for a reproducible dry run",
    )
    parser.add_argument(
        "--protocol",
        default=None,
        help="simulate: local protocol YAML to validate against "
        "(needed when the study was boot-loaded via MIDDLEWARE_PROTOCOL "
        "and has no design-conversation draft)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="ethics-package: write the Markdown to this file "
        "(default: print to stdout)",
    )
    args = parser.parse_args()

    if args.db and not os.environ.get("DATABASE_URL"):
        os.environ["MIDDLEWARE_DB"] = args.db

    if args.command == "serve":
        import uvicorn

        from middleware.app import create_app
        from middleware.settings import Settings

        settings = Settings()
        uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)

    elif args.command == "corpus-import":
        from middleware.corpus_importer import import_corpus
        from middleware.settings import Settings

        settings = Settings()
        result = import_corpus(settings.db_url)
        for tier in ("tierA", "tierB"):
            print(
                f"{tier}: {result[tier]['count']} papers, "
                f"{result[tier]['chunks']} FTS chunks"
            )
        ok = result["tierA"]["count"] > 0 and result["tierB"]["count"] > 0
        sys.exit(0 if ok else 1)

    elif args.command == "demo-seed":
        from middleware.demo import seed_demo
        from middleware.settings import Settings

        settings = Settings()
        made = seed_demo(settings.db_url, now=datetime.now(UTC).isoformat())
        print(
            f"demo: project {'created' if made['project'] else 'present'}, "
            f"study {'created' if made['study'] else 'present'}, "
            f"{made['sessions']} session mapping(s) added"
        )

    elif args.command == "corpus-verify":
        from middleware.corpus_importer import verify_import
        from middleware.settings import Settings

        settings = Settings()
        checks = verify_import(settings.db_url)
        for name, passed in checks.items():
            print(f"  {'ok ' if passed else 'FAIL'} {name}")
        sys.exit(0 if all(checks.values()) else 1)

    elif args.command == "corpus-enrich":
        import logging

        from middleware.corpus_enrich import enrich_abstracts, enrichment_status
        from middleware.settings import Settings

        logging.basicConfig(level=logging.INFO, format="%(message)s")
        settings = Settings()
        before = enrichment_status(settings.db_url)
        print(
            f"corpus: {before['papers']} papers, "
            f"{before['withAbstract']} with an abstract, {before['missing']} missing"
        )
        result = enrich_abstracts(settings.db_url, limit=args.limit)
        after = enrichment_status(settings.db_url)
        print(
            f"  enriched {result['enriched']} of {result['candidates']} candidates "
            f"in {result['batches']} batch(es); "
            f"{result['unresolved']} unresolved, "
            f"{result['skipped_no_id']} without a resolvable id"
        )
        print(f"  now {after['withAbstract']} of {after['papers']} carry an abstract")
        sys.exit(0 if result["enriched"] or not result["candidates"] else 1)

    elif args.command == "templates":
        from middleware import template_registry

        problems = template_registry.validate_registry()
        for meta in template_registry.list_templates():
            print(f"  {meta['templateId']} v{meta['templateVersion']}: {meta['title']}")
        for problem in problems:
            print(f"  FAIL {problem}")
        sys.exit(0 if not problems else 1)

    elif args.command == "simulate":
        if not args.study_id:
            print("simulate needs a study id: python -m middleware simulate <study_id>")
            sys.exit(2)
        sys.exit(
            cmd_simulate(
                args.study_id,
                server=args.server,
                count=args.count,
                profile=args.profile,
                seed=args.seed,
                protocol_path=args.protocol,
            )
        )

    elif args.command == "ethics-package":
        if not args.study_id:
            print(
                "ethics-package needs a study id: "
                "python -m middleware ethics-package <study_id>"
            )
            sys.exit(2)
        sys.exit(cmd_ethics(args.study_id, server=args.server, out=args.out))


if __name__ == "__main__":
    main()
