"""``python -m middleware`` - run the ingestion service or CLI commands.

Usage:
    python -m middleware                   # start the FastAPI service
    python -m middleware corpus-import     # land the corpus (FR-LIT-8 importer)
    python -m middleware corpus-verify     # spot-check an existing import
    python -m middleware corpus-enrich     # backfill abstracts from S2 (batch)
    python -m middleware templates         # list + validate the registry

(FR-ING-1; override the port with MIDDLEWARE_PORT, set DATABASE_URL for
PostgreSQL or MIDDLEWARE_DB for SQLite fallback.)"""

import argparse
import os
import sys


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
            "templates",
        ],
        help="Command to run (default: serve)",
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
    args = parser.parse_args()

    # Override MIDDLEWARE_DB via --db flag (SQLite only; DATABASE_URL takes precedence)
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
        # An enrichment run that resolved nothing while candidates existed is
        # a failure worth a non-zero exit (a scripted backfill should notice).
        sys.exit(0 if result["enriched"] or not result["candidates"] else 1)

    elif args.command == "templates":
        from middleware import template_registry

        problems = template_registry.validate_registry()
        for meta in template_registry.list_templates():
            print(f"  {meta['templateId']} v{meta['templateVersion']}: {meta['title']}")
        for problem in problems:
            print(f"  FAIL {problem}")
        sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
