"""``protocol`` command-line interface.

Subcommands prove the study-as-code claim end to end:

- ``protocol validate <file>``       - schema + referential validation, RQ
  coverage report (FR-PROT-1/2/5).
- ``protocol status <file>``         - current lifecycle phase and the open
  gate artifacts per phase (FR-PROT-3).
- ``protocol derive overlay-settings <file> --participant --condition`` -
  the ``cognitiveOverlay.*`` VS Code settings JSON for one session,
  derived from the protocol alone (FR-PROT-4).
- ``protocol export replication-kit <file>`` - the study's reproducible
  archive: protocol + dataset + regenerated report + pinned environment
  (FR-PROT-7, NFR-6).
"""

import argparse
import json
import sys
from pathlib import Path

from protocol.derive import (
    AGENT_HOOK_ENV_VARS,
    derive_agent_hooks,
    derive_overlay_settings,
)
from protocol.errors import ProtocolError
from protocol.export import build_kit, fetch_dataset
from protocol.lifecycle import current_phase, missing_artifacts
from protocol.loader import load_protocol, uncovered_rqs


def _cmd_validate(args: argparse.Namespace) -> int:
    protocol = load_protocol(args.file)
    print(
        f"OK: {args.file} is a valid study protocol "
        f"(protocolVersion {protocol['protocolVersion']})."
    )
    uncovered = uncovered_rqs(protocol)
    if uncovered:
        print(
            "warning: research questions with no analysis-plan coverage: "
            + ", ".join(uncovered)
        )
    else:
        print("All research questions are covered by the analysis plan.")
    return 0


def _collect_artifacts(args: argparse.Namespace) -> set[str]:
    """Artifacts produced so far: ``--artifact`` names plus, for
    ``--artifacts-dir``, every file's path relative to that directory."""
    artifacts = set(args.artifact)
    if args.artifacts_dir:
        root = Path(args.artifacts_dir)
        if not root.is_dir():
            raise ProtocolError(f"--artifacts-dir {root} is not a directory")
        artifacts |= {
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
        }
    return artifacts


def _cmd_status(args: argparse.Namespace) -> int:
    protocol = load_protocol(args.file)
    artifacts = _collect_artifacts(args)
    print(f"Current phase: {current_phase(protocol, artifacts)}")
    missing = missing_artifacts(protocol, artifacts)
    if missing:
        print("Missing gate artifacts (requirements-validation checkpoints):")
        for phase, gates in missing.items():
            print(f"  {phase}: {', '.join(gates)}")
    else:
        print("All gates satisfied.")
    uncovered = uncovered_rqs(protocol)
    if uncovered:
        print("Uncovered research questions: " + ", ".join(uncovered))
    return 0


def _cmd_derive(args: argparse.Namespace) -> int:
    protocol = load_protocol(args.file)
    settings = derive_overlay_settings(protocol, args.participant, args.condition)
    print(json.dumps(settings, indent=2))
    return 0


def _cmd_derive_agent_hooks(args: argparse.Namespace) -> int:
    protocol = load_protocol(args.file)
    hooks = derive_agent_hooks(protocol, command=args.command)
    print(json.dumps(hooks, indent=2))
    # The hook pack is self-contained bar the runbook's exported join keys -
    # surfaced on stderr so piping stdout to .claude/settings.json stays clean.
    print(
        "# write to <task-workspace>/.claude/settings.json; the facilitator "
        "runbook exports: " + ", ".join(AGENT_HOOK_ENV_VARS),
        file=sys.stderr,
    )
    return 0


def _cmd_export_kit(args: argparse.Namespace) -> int:
    protocol = load_protocol(args.file)
    study_id = args.study or protocol["study"]["id"]
    if args.dataset:
        dataset = json.loads(Path(args.dataset).read_text())
    else:
        dataset = fetch_dataset(args.server, study_id)
    out = Path(args.out or f"{study_id}-replication-kit.tar.gz")
    build_kit(
        Path(args.file), dataset, out, repo_root=Path.cwd()
    )
    print(f"replication kit: {out} ({out.stat().st_size} bytes)")
    print(
        "reproduce: uv sync --all-packages && SOURCE_DATE_EPOCH=0 "
        "uv run analysis run <kit>/protocol.yaml --dataset <kit>/dataset.json"
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="protocol",
        description="Validate and interrogate study-as-code protocol files.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate a protocol file")
    validate.add_argument("file")
    validate.set_defaults(func=_cmd_validate)

    status = sub.add_parser(
        "status", help="show lifecycle phase and missing gate artifacts"
    )
    status.add_argument("file")
    status.add_argument(
        "--artifact",
        action="append",
        default=[],
        metavar="NAME",
        help="a gate artifact that exists (repeatable)",
    )
    status.add_argument(
        "--artifacts-dir",
        metavar="DIR",
        help="directory whose files (relative paths) count as artifacts",
    )
    status.set_defaults(func=_cmd_status)

    derive = sub.add_parser(
        "derive", help="derive instrument configuration from the protocol"
    )
    derive_sub = derive.add_subparsers(dest="target", required=True)
    overlay = derive_sub.add_parser(
        "overlay-settings",
        help="emit cognitiveOverlay.* VS Code settings JSON for one session",
    )
    overlay.add_argument("file")
    overlay.add_argument("--participant", required=True)
    overlay.add_argument("--condition", required=True)
    overlay.set_defaults(func=_cmd_derive)

    agent_hooks = derive_sub.add_parser(
        "agent-hooks",
        help="emit the .claude/settings.json hooks section for the agent leg "
        "(FR-AGENT-2), content policy baked from the protocol",
    )
    agent_hooks.add_argument("file")
    agent_hooks.add_argument(
        "--command",
        default="agent-capture-hook",
        help="hook command on the task workspace's PATH (default: "
        "agent-capture-hook)",
    )
    agent_hooks.set_defaults(func=_cmd_derive_agent_hooks)

    export = sub.add_parser(
        "export", help="export study artifacts derived from the protocol"
    )
    export_sub = export.add_subparsers(dest="target", required=True)
    kit = export_sub.add_parser(
        "replication-kit",
        help="one reproducible archive: protocol + dataset + report + "
        "pinned environment (FR-PROT-7)",
    )
    kit.add_argument("file")
    kit.add_argument("--study", help="study id (default: the protocol's)")
    kit.add_argument(
        "--server", default="http://127.0.0.1:8000",
        help="middleware to fetch the dataset from (default :8000)",
    )
    kit.add_argument(
        "--dataset", help="dataset JSON file (instead of fetching)"
    )
    kit.add_argument("--out", help="output archive path (.tar.gz)")
    kit.set_defaults(func=_cmd_export_kit)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ProtocolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
