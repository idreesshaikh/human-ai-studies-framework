"""Post-session transcript importer - the completeness backstop (FR-AGENT-2).

Parses a finished Claude Code transcript JSONL and ingests the whole
normalized event set. Because ingestion is idempotent on
``(sessionId, source, seq)`` and the normalized ``seq`` is the transcript
position (:mod:`agent_capture.transcript`), importing a session whose live
hooks already landed reconciles to the same rows rather than duplicating
them - and importing a session whose middleware was down mid-run recovers
everything (NFR-2).

    uv run python -m agent_capture.import_transcript <transcript.jsonl> \
        --participant P01 --condition ai-assisted --session S1 \
        --content-policy metadata-only

Join keys default to the ``STUDY_*`` environment variables the facilitator
runbook sets, so the common case needs no flags.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_capture.events import SOURCE_AGENT, Keys
from agent_capture.ingest import DEFAULT_ENDPOINT, post_events
from agent_capture.redact import DEFAULT_MIN_TOKEN_LEN, normalize_policy
from agent_capture.transcript import normalize_transcript


def import_transcript(
    transcript_path: str | Path,
    keys: Keys,
    policy: str,
    *,
    endpoint: str = DEFAULT_ENDPOINT,
    min_token_len: int = DEFAULT_MIN_TOKEN_LEN,
) -> dict:
    events = normalize_transcript(
        transcript_path, keys, policy, min_token_len=min_token_len
    )
    result = post_events(events, source=SOURCE_AGENT, endpoint=endpoint)
    result["normalized"] = len(events)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path, help="transcript JSONL path")
    env = Keys.from_env()
    parser.add_argument("--participant", default=env.participant_id)
    parser.add_argument("--condition", default=env.condition)
    parser.add_argument("--session", default=env.session_id)
    parser.add_argument("--content-policy", default="metadata-only")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument(
        "--print", action="store_true", help="print normalized events, do not POST"
    )
    args = parser.parse_args(argv)

    keys = Keys(
        participant_id=args.participant,
        condition=args.condition,
        session_id=args.session,
    )
    policy = normalize_policy(args.content_policy)

    if args.print:
        import json

        events = normalize_transcript(args.transcript, keys, policy)
        print(json.dumps(events, indent=2))
        return 0

    result = import_transcript(args.transcript, keys, policy, endpoint=args.endpoint)
    if result.get("error"):
        print(
            f"import: normalized {result['normalized']} events but POST failed: "
            f"{result['error']}",
            file=sys.stderr,
        )
        return 1
    print(
        f"import: {result['normalized']} events normalized -> "
        f"{result.get('inserted', 0)} inserted, "
        f"{result.get('duplicates', 0)} reconciled (idempotent)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
