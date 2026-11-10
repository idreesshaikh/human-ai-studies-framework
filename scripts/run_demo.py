#!/usr/bin/env python3
"""Serve a fresh synthetic demo on localhost, separate from configured study data.

Run after installation and the platform build:
    uv run --no-sync python scripts/run_demo.py
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


def demo_environment(directory: Path, port: int) -> dict[str, str]:
    """Child processes receive disposable storage and no live model route."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("LLM_", "MISTRAL_", "MIDDLEWARE_"))
    }
    env.update(
        DATABASE_URL="",
        MIDDLEWARE_DB=str(directory / "demo.sqlite3"),
        MIDDLEWARE_DATA_DIR=str(directory),
        MIDDLEWARE_WEB=str(ROOT / "platform" / "dist"),
        MIDDLEWARE_AUTH="none",
        MIDDLEWARE_PROTOCOL="",
        MIDDLEWARE_CORPUS_BOOTSTRAP="0",
        MIDDLEWARE_REFRESH_INTERVAL_H="",
        MIDDLEWARE_PUBLIC_URL=f"http://127.0.0.1:{port}",
    )
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    if not (ROOT / "platform" / "dist" / "index.html").is_file():
        parser.error("Build the platform first: npm --prefix platform run build")

    with tempfile.TemporaryDirectory(prefix="studyloop-demo-") as directory:
        env = demo_environment(Path(directory), args.port)
        seeded = subprocess.run(
            [sys.executable, "-m", "middleware", "seed-example"],
            cwd=ROOT,
            env=env,
            check=False,
        )
        if seeded.returncode:
            return seeded.returncode
        print(
            f"\nOpen http://127.0.0.1:{args.port}\n"
            "Synthetic demo only. Chat has no live provider; use the checklist.\n"
            "Example links are illustrative. Ctrl+C stops the server and "
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
