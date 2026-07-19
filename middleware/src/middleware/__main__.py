"""``python -m middleware`` - run the ingestion service or CLI commands.

Usage:
    python -m middleware                   # start the FastAPI service
    python -m middleware corpus-import     # land the corpus (FR-LIT-8 importer)
    python -m middleware corpus-verify     # spot-check an existing import
    python -m middleware templates         # list + validate the registry

(FR-ING-1; override the port with MIDDLEWARE_PORT, the DB with --db or
MIDDLEWARE_DB.)"""

import argparse
import os
import sys

DEFAULT_DB = "data/middleware.db"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Middleware server and CLI (FR-ING-1, FR-LIT-8/9, FR-TPL-1)"
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "corpus-import", "corpus-verify", "templates"],
        help="Command to run (default: serve)",
    )
    parser.add_argument(
        "--db", default=None, help="SQLite DB path (overrides MIDDLEWARE_DB)"
    )
    args = parser.parse_args()
    db_path = args.db or os.environ.get("MIDDLEWARE_DB", DEFAULT_DB)

    if args.command == "serve":
        import uvicorn

        from middleware.app import create_app
        from middleware.settings import Settings

        settings = Settings()
        uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)
    elif args.command == "corpus-import":
        from middleware.corpus_importer import import_corpus

        result = import_corpus(db_path)
        for tier in ("tierA", "tierB"):
            print(
                f"{tier}: {result[tier]['count']} papers, "
                f"{result[tier]['chunks']} FTS chunks"
            )
        ok = result["tierA"]["count"] > 0 and result["tierB"]["count"] > 0
        sys.exit(0 if ok else 1)
    elif args.command == "corpus-verify":
        from middleware.corpus_importer import verify_import

        checks = verify_import(db_path)
        for name, passed in checks.items():
            print(f"  {'ok ' if passed else 'FAIL'} {name}")
        sys.exit(0 if all(checks.values()) else 1)
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
