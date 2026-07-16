"""``agent-capture`` command-line interface - the session-runner instruments.

Subcommands the facilitator runbook drives (join keys default to the
``STUDY_*`` environment variables it sets):

- ``agent-capture snapshot`` - one shadow-git snapshot tick + participant-
  commit observation (FR-INST-15/17); run on save and/or a timer.
- ``agent-capture harness``  - run the task's acceptance tests, emit
  ``task_outcome`` (FR-INST-16).
- ``agent-capture import``   - import a finished transcript (the FR-AGENT-2
  backstop; thin wrapper over :mod:`agent_capture.import_transcript`).
- ``agent-capture correlate`` - post-ingest cross-leg correlation +
  code-evolution derivation (FR-AGENT-3, FR-INST-17).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from agent_capture.correlate import correlate_session
from agent_capture.events import SOURCE_DERIVED, Keys
from agent_capture.evolution import derive_evolution
from agent_capture.harness import Harness
from agent_capture.ingest import DEFAULT_ENDPOINT, post_events
from agent_capture.snapshot import Snapshotter


def _keys(args: argparse.Namespace) -> Keys:
    return Keys(
        participant_id=args.participant,
        condition=args.condition,
        session_id=args.session,
    )


def _add_keys(p: argparse.ArgumentParser) -> None:
    env = Keys.from_env()
    p.add_argument("--participant", default=env.participant_id)
    p.add_argument("--condition", default=env.condition)
    p.add_argument("--session", default=env.session_id)
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    p.add_argument("--print", action="store_true", help="print events, do not POST")


def _emit(events: list[dict], args) -> int:
    """POST events, splitting by producer stream (each source is one batch)."""
    if args.print:
        print(json.dumps(events, indent=2))
        return 0
    grouped: dict[str, list[dict]] = {}
    for e in events:
        grouped.setdefault(e["source"], []).append(e)
    total = 0
    for source, batch in grouped.items():
        res = post_events(batch, source=source, endpoint=args.endpoint)
        if res.get("error"):
            print(f"warn: POST {source} failed: {res['error']}", file=sys.stderr)
        total += res.get("inserted", 0)
    print(f"agent-capture: {len(events)} events, {total} newly inserted")
    return 0


def _cmd_snapshot(args) -> int:
    snap = Snapshotter(_keys(args), args.workspace, args.git_dir)
    return _emit(snap.snapshot(trigger=args.trigger), args)


def _cmd_harness(args) -> int:
    harness = Harness(_keys(args), args.tests_dir)
    return _emit([harness.run(trigger=args.trigger)], args)


def _cmd_import(args) -> int:
    from agent_capture.import_transcript import main as import_main

    return import_main(
        [
            str(args.transcript),
            "--participant", args.participant,
            "--condition", args.condition,
            "--session", args.session,
            "--content-policy", args.content_policy,
            "--endpoint", args.endpoint,
            *(["--print"] if args.print else []),
        ]
    )


def _fetch_dataset(server: str, study_id: str) -> list[dict]:
    url = f"{server.rstrip('/')}/studies/{study_id}/dataset?format=json"
    with urllib.request.urlopen(url, timeout=30) as res:
        return json.loads(res.read()).get("rows", [])


def _cmd_correlate(args) -> int:
    rows = (
        json.loads(Path(args.dataset).read_text())["rows"]
        if args.dataset
        else _fetch_dataset(args.server, args.study)
    )
    by_session: dict[str, list[dict]] = {}
    for r in rows:
        by_session.setdefault(r.get("sessionId", ""), []).append(r)

    derived: list[dict] = []
    for sid, events in by_session.items():
        if not sid:
            continue
        first = events[0]
        keys = Keys(
            participant_id=first.get("participantId", ""),
            condition=first.get("condition", ""),
            session_id=sid,
        )
        derived.extend(correlate_session(events, keys, window_s=args.window))
        evo = derive_evolution(events, keys)
        if evo is not None:
            derived.append(evo)

    if args.print:
        print(json.dumps(derived, indent=2))
        return 0
    if not derived:
        print("correlate: no derivable cross-leg events in this dataset")
        return 0
    res = post_events(derived, source=SOURCE_DERIVED, endpoint=args.endpoint)
    loops = sum(1 for e in derived if e["type"] == "reliance_loop")
    print(
        f"correlate: {len(derived)} derived events "
        f"({loops} reliance loop(s)), {res.get('inserted', 0)} inserted"
    )
    return 0 if not res.get("error") else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-capture", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="one shadow-git snapshot tick")
    _add_keys(snap)
    snap.add_argument("--workspace", required=True, help="task workspace path")
    snap.add_argument(
        "--git-dir", required=True, help="shadow repo git-dir (in .study-data/)"
    )
    snap.add_argument("--trigger", default="timer", choices=["save", "timer"])
    snap.set_defaults(func=_cmd_snapshot)

    harn = sub.add_parser("harness", help="run acceptance tests -> task_outcome")
    _add_keys(harn)
    harn.add_argument("--tests-dir", required=True, help="task-tests/ directory")
    harn.add_argument(
        "--trigger", default="session-end", choices=["save", "session-end"]
    )
    harn.set_defaults(func=_cmd_harness)

    imp = sub.add_parser("import", help="import a finished transcript (backstop)")
    _add_keys(imp)
    imp.add_argument("transcript", type=Path)
    imp.add_argument("--content-policy", default="metadata-only")
    imp.set_defaults(func=_cmd_import)

    corr = sub.add_parser("correlate", help="cross-leg correlation + evolution")
    corr.add_argument("--study", default="pilot-2026")
    corr.add_argument("--server", default="http://127.0.0.1:8000")
    corr.add_argument("--dataset", help="dataset JSON file (instead of fetching)")
    corr.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    corr.add_argument("--window", type=float, default=120.0, help="window seconds")
    corr.add_argument("--print", action="store_true")
    corr.set_defaults(func=_cmd_correlate)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
