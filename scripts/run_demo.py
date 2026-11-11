#!/usr/bin/env python3
"""Serve a fresh synthetic demo on localhost, separate from configured study data.

Run after installation and the platform build:
    uv run --no-sync python scripts/run_demo.py

Add --live for a live example: the design chat uses your model provider and
suggests literature from the bundled paper corpus. Load the provider key
explicitly, for example:
    uv run --no-sync --env-file .env python scripts/run_demo.py --live
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (
    "import sys, uvicorn; "
    "from middleware.app import create_app; "
    "uvicorn.run(create_app(), host='127.0.0.1', port=int(sys.argv[1]))"
)


MODEL_ROUTE = ("LLM_", "MISTRAL_")
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]")


def has_model_route(environ) -> bool:
    """A provider key, or a local OpenAI-compatible server that needs none."""
    if environ.get("LLM_API_KEY") or environ.get("MISTRAL_API_KEY"):
        return True
    base = environ.get("LLM_BASE_URL", "")
    return any(f"//{host}" in base for host in LOCAL_HOSTS)


def demo_environment(directory: Path, port: int, live: bool = False) -> dict[str, str]:
    """Child processes receive disposable storage and, unless live, no model route.

    A live example keeps only the model-route variables and imports the bundled
    paper corpus in the background. Storage, sign-in and every other inherited
    server setting stay disposable either way, so an ``--env-file`` written for
    a deployment cannot point the demo at participant data."""
    stripped = ("MIDDLEWARE_",) if live else (*MODEL_ROUTE, "MIDDLEWARE_")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(stripped)
    }
    env.update(
        DATABASE_URL="",
        MIDDLEWARE_DB=str(directory / "demo.sqlite3"),
        MIDDLEWARE_DATA_DIR=str(directory),
        MIDDLEWARE_WEB=str(ROOT / "platform" / "dist"),
        MIDDLEWARE_AUTH="none",
        MIDDLEWARE_PROTOCOL="",
        MIDDLEWARE_CORPUS_BOOTSTRAP="1" if live else "0",
        MIDDLEWARE_REFRESH_INTERVAL_H="",
        MIDDLEWARE_PUBLIC_URL=f"http://127.0.0.1:{port}",
    )
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--live",
        action="store_true",
        help="use your model provider for the design chat and load the paper "
        "corpus for literature suggestions (makes provider requests)",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if args.live and not has_model_route(os.environ):
        parser.error(
            "--live needs a model provider: set LLM_API_KEY (or MISTRAL_API_KEY), "
            "or LLM_BASE_URL for a local server. To use .env: uv run --no-sync "
            "--env-file .env python scripts/run_demo.py --live"
        )
    if not (ROOT / "platform" / "dist" / "index.html").is_file():
        parser.error("Build the platform first: npm --prefix platform run build")

    with tempfile.TemporaryDirectory(prefix="studyloop-demo-") as directory:
        env = demo_environment(Path(directory), args.port, live=args.live)
        seeded = subprocess.run(
            [sys.executable, "-m", "middleware", "seed-example"],
            cwd=ROOT,
            env=env,
            check=False,
        )
        if seeded.returncode:
            return seeded.returncode
        mode = (
            "Live example: the chat uses your model provider and makes paid "
            "requests.\nLiterature suggestions start once the paper corpus has "
            "loaded (about a minute).\n"
            if args.live
            else "Synthetic demo only. Chat has no live provider; use the "
            "checklist.\n"
        )
        print(
            f"\nOpen http://127.0.0.1:{args.port}\n"
            + mode
            + "Example links are illustrative. Ctrl+C stops the server and "
            "removes this demo's temporary data.\n",
            flush=True,
        )
        with subprocess.Popen(
            [sys.executable, "-c", SERVER, str(args.port)], cwd=ROOT, env=env
        ) as server:
            try:
                return server.wait()
            except KeyboardInterrupt:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
                return 0


if __name__ == "__main__":
    sys.exit(main())
