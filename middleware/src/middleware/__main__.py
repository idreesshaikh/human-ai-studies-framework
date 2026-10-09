"""``python -m middleware`` - run the ingestion service or CLI commands."""

import argparse
import json
import os
import sys
import urllib.request


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Study server and corpus tools")
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=[
            "serve",
            "corpus-import",
            "corpus-verify",
            "corpus-enrich",
            "corpus-refresh",
            "corpus-candidates",
            "corpus-decide",
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
    parser.add_argument(
        "--since",
        default=None,
        help="corpus-refresh: first date to fetch, YYYY-MM-DD "
        "(default: resume from the last good run, or 30 days back)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="corpus-refresh: fetch and report, but store nothing",
    )
    parser.add_argument(
        "--queries",
        default=None,
        help="corpus-refresh: queries JSON (default: MIDDLEWARE_REFRESH_QUERIES, "
        "else docs/papers/refresh-queries.json)",
    )
    parser.add_argument("--ref", default=None, help="corpus-decide: the paper ref")
    parser.add_argument(
        "--decision", choices=["accept", "reject"], help="corpus-decide: the decision"
    )
    parser.add_argument("--note", default="", help="corpus-decide: why")

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

    elif args.command == "corpus-refresh":
        import logging
        from pathlib import Path

        from middleware import corpus_refresh
        from middleware.db import make_session_factory
        from middleware.settings import Settings

        logging.basicConfig(level=logging.INFO, format="%(message)s")
        queries = args.queries or os.environ.get("MIDDLEWARE_REFRESH_QUERIES")
        factory = make_session_factory(Settings().db_url)
        try:
            result = corpus_refresh.run_once(
                factory,
                config_path=Path(queries) if queries else None,
                since=args.since,
                dry_run=args.dry_run,
            )
        except (ValueError, corpus_refresh.RefreshInProgress) as exc:
            print(f"corpus-refresh: {exc}", file=sys.stderr)
            sys.exit(2)
        print(corpus_refresh.format_summary(result))
        sys.exit(0 if result["status"] in ("ok", "dry-run") else 1)

    elif args.command == "corpus-candidates":
        from middleware import corpus_refresh
        from middleware.db import make_session_factory
        from middleware.settings import Settings

        factory = make_session_factory(Settings().db_url)
        with factory() as s:
            counts = corpus_refresh.candidate_counts(s)
            rows = corpus_refresh.list_candidates(s, limit=args.limit or 20)
        print(
            f"candidates: {counts['new']} new, {counts['accepted']} accepted, "
            f"{counts['rejected']} rejected"
        )
        for row in rows:
            print(f"  {row['ref']}  [{row['score']}]  {row['year']}  {row['title']}")
        sys.exit(0)

    elif args.command == "corpus-decide":
        from middleware import corpus_refresh
        from middleware.db import make_session_factory
        from middleware.settings import Settings

        if not args.ref or not args.decision:
            print(
                "corpus-decide needs --ref and --decision accept|reject",
                file=sys.stderr,
            )
            sys.exit(2)
        factory = make_session_factory(Settings().db_url)
        who = os.environ.get("USER") or "cli"
        decide = (
            corpus_refresh.promote
            if args.decision == "accept"
            else corpus_refresh.reject
        )
        with factory() as s:
            try:
                out = decide(
                    s,
                    args.ref,
                    decided_by=who,
                    now=corpus_refresh.utc_now(),
                    note=args.note,
                )
            except KeyError:
                print(f"no candidate {args.ref}", file=sys.stderr)
                sys.exit(1)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                sys.exit(1)
            s.commit()
        print(f"{out['ref']}: {out['status']}")
        sys.exit(0)

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
