"""Claude Code hook entry point - the live capture source (FR-AGENT-2)."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys

from agent_capture.events import SOURCE_AGENT, Keys
from agent_capture.ingest import DEFAULT_ENDPOINT, post_events
from agent_capture.redact import normalize_policy
from agent_capture.transcript import normalize_transcript


def run(stdin_json: str, argv: list[str], environ: dict) -> dict:
    """
    Pure core (testable): given the hook stdin + args + env, normalize and POST. Returns
    the POST summary (or a no-op summary).
    """
    parser = argparse.ArgumentParser(prog="agent-capture-hook")
    parser.add_argument("--content-policy", default=None)
    parser.add_argument("--endpoint", default=None)
    args, _ = parser.parse_known_args(argv)

    try:
        hook = json.loads(stdin_json) if stdin_json.strip() else {}
    except json.JSONDecodeError:
        hook = {}
    transcript_path = hook.get("transcript_path", "")
    if not transcript_path or not os.path.isfile(transcript_path):
        return {"posted": 0, "error": "no transcript"}

    keys = Keys.from_env(environ)
    policy = normalize_policy(
        args.content_policy or environ.get("STUDY_CONTENT_POLICY")
    )
    endpoint = args.endpoint or environ.get("STUDY_INGEST_ENDPOINT") or DEFAULT_ENDPOINT
    events = normalize_transcript(transcript_path, keys, policy)
    return post_events(events, source=SOURCE_AGENT, endpoint=endpoint)


def main(argv: list[str] | None = None) -> int:
    stdin_json = sys.stdin.read() if not sys.stdin.isatty() else ""
    # Never surface an error to the agent: a hook must not block the participant
    # (NFR-1).
    with contextlib.suppress(Exception):
        run(stdin_json, argv or sys.argv[1:], dict(os.environ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
