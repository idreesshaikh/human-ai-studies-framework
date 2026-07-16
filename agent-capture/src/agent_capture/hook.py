"""Claude Code hook entry point - the live capture source (FR-AGENT-2).

Wired into the task workspace's ``.claude/settings.json`` by
``protocol derive agent-hooks`` (:mod:`protocol.derive`). Every hook trigger
(SessionStart / PostToolUse / Stop / SessionEnd) runs this one command,
which:

1. reads the hook JSON from stdin (Claude Code passes ``session_id``,
   ``transcript_path``, ``cwd`` and, for tool events, ``tool_name`` etc.),
2. re-normalizes the transcript-so-far (:mod:`agent_capture.transcript`),
3. POSTs the whole batch fire-and-forget with a short timeout.

Because every trigger re-POSTs the full normalized set and ingestion is
idempotent, the scheme is self-healing: a trigger that fails to reach a
down middleware costs nothing, and the next trigger (or the post-session
importer) carries everything. The hook never blocks the agent (NFR-1): it
exits 0 no matter what, and swallows all errors.

The join keys and content policy come from the environment the facilitator
runbook sets (``STUDY_PARTICIPANT``/``STUDY_CONDITION``/``STUDY_SESSION``,
``STUDY_CONTENT_POLICY``, ``STUDY_INGEST_ENDPOINT``) - the derive command
bakes the policy into the hook args, so there is no hand-maintained side
configuration (FR-PROT-4).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from agent_capture.events import SOURCE_AGENT, Keys
from agent_capture.ingest import DEFAULT_ENDPOINT, post_events
from agent_capture.redact import normalize_policy
from agent_capture.transcript import normalize_transcript


def run(stdin_json: str, argv: list[str], environ: dict) -> dict:
    """Pure core (testable): given the hook stdin + args + env, normalize and
    POST. Returns the POST summary (or a no-op summary)."""
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
    endpoint = (
        args.endpoint or environ.get("STUDY_INGEST_ENDPOINT") or DEFAULT_ENDPOINT
    )
    events = normalize_transcript(transcript_path, keys, policy)
    return post_events(events, source=SOURCE_AGENT, endpoint=endpoint)


def main(argv: list[str] | None = None) -> int:
    stdin_json = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        run(stdin_json, argv or sys.argv[1:], dict(os.environ))
    except Exception:  # noqa: BLE001 - never surface an error to the agent
        pass
    return 0  # always succeed: a hook must not block the participant


if __name__ == "__main__":
    sys.exit(main())
