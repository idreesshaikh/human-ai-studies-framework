"""Run the AI-use calibration sessions the same way every time.

The frozen plan (docs/experiments/ai-use-calibration/plan.md, sections 4, 6
and 9) describes about ten manual steps per session. This script does the
mechanical ones, so 31 sessions do not depend on retyping them correctly:

    setup            make ~/ai-use-calibration (workspace, rows, env.sh) and
                     install the session extensions into a dedicated VS Code
                     profile, "ai-use-calibration", pinned to fixed versions
    prepare N        session N of the frozen order: fresh copy of the task,
                     the scenario's workspace settings and snippet, agent hooks
                     for hooked agents, the environment record in the rows
                     folder, then print the scenario script and open VS Code
    finish N         append the label row to labels.csv straight after the
                     session, then archive/import agent transcripts
    import-agent N / import-agent dry SESSION_ID
                     retry agent transcript archiving/import without relabelling
    verify N / verify dry SESSION_ID
                     repeat blinded infrastructure/procedure checks; optionally
                     send only procedure evidence to --reviewer codex|claude
    prepare dry SCENARIO / finish dry / check-dry
                     a throwaway rehearsal kept in ~/ai-use-calibration/dry,
                     never mixed with the 31 sessions

`prepare` refuses a real session when the freeze manifest is missing or
`freeze_calibration.py check` fails, and when the session already has a label.
`finish` consolidates live hook batches and saves task evidence, then runs
`verify`. Verification never opens TERN event rows or archived transcript bodies.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import hashlib
import importlib.util
import itertools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "docs" / "experiments" / "ai-use-calibration"
PLAN = EXPERIMENT / "plan.md"
LABELS = EXPERIMENT / "labels.csv"
TASK = EXPERIMENT / "task"
MANIFEST = ROOT / "docs" / "calibration-freeze.json"
HOOKS_PROTOCOL = ROOT / "protocol" / "examples" / "pilot-study.yaml"
VSIX = ROOT / "extension" / "tern-1.0.1.vsix"
EXTENSIONS_ROOT = Path.home() / ".vscode" / "extensions"

PROFILE = "ai-use-calibration"
UV = shutil.which("uv") or "uv"
LABEL_HEADER = [
    "sessionId",
    "scenario",
    "aiUsed",
    "exposed",
    "assisted",
    "rep",
    "operatorNote",
]
HOOKED = {"cli-agent-hooks", "probe-agent-explain"}
AGENT = HOOKED | {"cli-agent-no-hooks", "probe-agent-closed-file"}
REQUIRED_NOTE = {
    "browser-paste": "chatbot and model",
    "retype": "chatbot and model",
    "probe-menu-paste": "chatbot and model",
    "benign-stackoverflow-paste": "answer URL",
    "benign-formatter": "how many saves changed the file",
    "benign-rename": "the two renames and their occurrence counts",
    "probe-word-accept": "roughly how many words were accepted",
    "probe-rename-many": "the number of occurrences",
    "probe-format-large": "that the save reformatted the file",
}
DEVIATIONS = (
    "A failed or warned check is recorded in the plan's Deviations; "
    "sessions are never redone."
)
REVIEW_PROMPT = (
    "You are a blinded procedure reviewer for one scripted calibration session. "
    "Read the files in this directory. You never see the instrument's signals. "
    "Judge (1) whether the session followed scenario.md, using inventory.diff, "
    "pytest.txt, the operator note and the checks, and (2) whether the labels "
    "exposed/assisted/aiUsed fit that evidence under these definitions: "
    "exposed = saw AI output; assisted = AI output informed the work; "
    "aiUsed = AI-generated content ever entered the workspace. "
    "Never suggest redoing the session. Reply with JSON only: "
    '{"verdict": "ok" or "concern", "concerns": [strings], '
    '"suggestedDeviation": string or null}.'
)
CODE_APP = Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code")
BUILTIN_COPILOT = CODE_APP.parents[1] / "extensions" / "copilot" / "package.json"
# Pinned to the versions installed on the calibration machine on 2026-11-17.
PROFILE_EXTENSIONS = (
    "ms-python.python@2026.10.0",
    "ms-python.vscode-pylance@2026.4.1",
    "charliermarsh.ruff@2026.96.0",
)
TDEF_SNIPPET = {
    "Function skeleton": {
        "scope": "python",
        "prefix": "tdef",
        "body": [
            "def ${1:name}(${2:args}):",
            '    """${3:Summary.}',
            "",
            "    Args:",
            "        ${4:args}: ${5:description}",
            "",
            "    Returns:",
            "        ${6:description}",
            '    """',
            "    ${7:pass}",
        ],
    }
}


class Refused(Exception):
    """A precondition failed; the message says what to do."""


def _load(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- places -----------------------------------------------------------------


class Places:
    """Every folder a session touches, all under one calibration home."""

    def __init__(self, home: Path, dry: bool = False):
        self.home = home
        self.work = home / "workspace"
        base = home / "dry" if dry else home
        self.rows = base / "rows"
        self.labels = base / "labels.csv" if dry else LABELS
        self.dry = dry
        self.current = base / "current.json"

    @classmethod
    def default(cls, dry: bool = False) -> Places:
        home = os.environ.get("CALIBRATION_HOME")
        return cls(Path(home) if home else Path.home() / "ai-use-calibration", dry)


def env_sh(places: Places) -> str:
    return (
        f"export REPO={ROOT}\n"
        f'export WORK="{places.work}"\n'
        f'export ROWS="{places.home / "rows"}"\n'
        "# Claude Code must not add its VS Code extension to the profile mid-study.\n"
        "export CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL=1\n"
    )


# --- sessions ---------------------------------------------------------------


def session_for(order: int) -> tuple[str, str, int]:
    """`(sessionId, scenario, rep)` for position `order` of the frozen order."""
    rows = _load("calibration_order").build_order()
    if not 1 <= order <= len(rows):
        raise Refused(f"order must be 1..{len(rows)}, not {order}")
    _, scenario, rep = rows[order - 1]
    return f"cal-{order:02d}-{scenario}-r{rep}", scenario, rep


def dry_session(scenario: str, now: dt.datetime) -> str:
    if scenario not in _load("calibration_order").SCENARIOS:
        raise Refused(f"unknown scenario {scenario!r}")
    return f"dry-{scenario}-{now:%m%d%H%M%S}"


def workspace_settings(session_id: str, scenario: str, rows: Path) -> dict:
    """The settings in force for one session (plan, section 4)."""
    inline = scenario in {"copilot-inline", "probe-word-accept", "probe-mouse-accept"}
    chat = scenario == "copilot-chat"
    return {
        "tern.session.id": session_id,
        "tern.output.directory": str(rows),
        # Only Copilot scenarios and acceptance probes enable built-in AI.
        "chat.disableAIFeatures": not (inline or chat),
        # Chat has no inline completions; next-edit suggestions stay off.
        "github.copilot.enable": {"*": inline},
        "github.copilot.nextEditSuggestions.enabled": False,
        "editor.formatOnSave": scenario in {"benign-formatter", "probe-format-large"},
        "[python]": {"editor.defaultFormatter": "charliermarsh.ruff"},
    }


def scenario_script(scenario: str, plan_text: str) -> str:
    """The scenario's numbered script, copied from plan section 8."""
    section = plan_text.split("## 8. Scenario scripts", 1)[-1].split("\n## 9.", 1)[0]
    match = re.search(
        rf"^\*\*{re.escape(scenario)}\*\*.*?(?=^\*\*[a-z-]+\*\*|\Z)",
        section,
        flags=re.S | re.M,
    )
    if not match:
        raise Refused(f"no script for {scenario!r} in plan section 8")
    return match.group(0).strip()


def read_labels(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != LABEL_HEADER:
            raise Refused(f"{path} must start with {','.join(LABEL_HEADER)}")
        return list(reader)


def append_label(path: Path, row: dict) -> None:
    validate_label(row["aiUsed"], row["exposed"], row["assisted"])
    labels = read_labels(path)
    if any(r["sessionId"] == row["sessionId"] for r in labels):
        raise Refused(f"{row['sessionId']} is already labelled; labels never change")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(",".join(LABEL_HEADER) + "\n")
    with path.open("a", newline="") as handle:
        csv.DictWriter(handle, LABEL_HEADER, lineterminator="\n").writerow(row)


def validate_label(ai_used: str, exposed: str, assisted: str) -> None:
    for name, value in (
        ("aiUsed", ai_used),
        ("exposed", exposed),
        ("assisted", assisted),
    ):
        if value not in {"true", "false"}:
            raise Refused(f"{name} must be true or false")
    if ai_used == "true" and (exposed != "true" or assisted != "true"):
        raise Refused("aiUsed=true requires exposed=true and assisted=true")
    if assisted == "true" and exposed != "true":
        raise Refused("assisted=true requires exposed=true")


def transcript_dir(work: Path) -> Path:
    """Where Claude Code keeps transcripts for sessions started in `work`."""
    return (
        Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(work))
    )


def installed_instrument(extensions_root: Path | None = None) -> dict[str, str]:
    """Hash the installed TERN files, including paths, and the source VSIX."""
    root = extensions_root if extensions_root is not None else EXTENSIONS_ROOT
    folders = sorted(p for p in root.glob("idreesrazak.tern-1.0.1*") if p.is_dir())
    if not folders:
        raise Refused(f"no installed TERN 1.0.1 in {root}; run setup first")
    digest = hashlib.sha256()
    files = sorted(
        (p for folder in folders for p in folder.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for path in files:
        if path.name == ".DS_Store":
            continue
        data = path.read_bytes()
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(str(len(data)).encode() + b"\0")
        digest.update(data)
    return {
        "installedSha256": digest.hexdigest(),
        "vsixSha256": hashlib.sha256(VSIX.read_bytes()).hexdigest(),
    }


def instrument_record(hashes: dict[str, str]) -> str:
    return "".join(f"TERN {name}={value}\n" for name, value in hashes.items())


# --- live hook capture --------------------------------------------------------


def serve_hooks(out: Path, port_file: Path) -> None:
    """Record batches locally until SIGTERM, completing any current request."""
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                length = int(self.headers["Content-Length"])
                if length < 0:
                    raise ValueError("negative Content-Length")
                body = json.loads(self.rfile.read(length))
            except (ValueError, TypeError):
                self.send_error(400, "expected a JSON body with Content-Length")
                return
            record = {"receivedAt": dt.datetime.now(dt.UTC).isoformat(), "body": body}
            with out.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
            events = body.get("events", []) if isinstance(body, dict) else []
            accepted = len(events) if isinstance(events, list) else 0
            response = json.dumps({"accepted": accepted}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    out.parent.mkdir(parents=True, exist_ok=True)
    port_file.parent.mkdir(parents=True, exist_ok=True)
    previous = signal.signal(signal.SIGTERM, stop)
    try:
        with HTTPServer(("127.0.0.1", 0), Handler) as server:
            server.timeout = 0.1
            port_file.write_text(str(server.server_port) + "\n")
            while not stopping:
                server.handle_request()
    finally:
        port_file.unlink(missing_ok=True)
        signal.signal(signal.SIGTERM, previous)


def start_hook_receiver(places: Places, session_id: str) -> int:
    port_file = places.rows / f"{session_id}.hook.port"
    pid_file = places.rows / f"{session_id}.hook.pid"
    if pid_file.exists():
        raise Refused(f"hook receiver already recorded for {session_id}; finish first")
    port_file.unlink(missing_ok=True)
    with (places.rows / f"{session_id}.hook.log").open("a") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "serve-hooks",
                "--out",
                str(places.rows / f"{session_id}.hook-batches.jsonl"),
                "--port-file",
                str(port_file),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    pid_file.write_text(str(process.pid) + "\n")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        if port_file.exists():
            port = port_file.read_text().strip()
            if port:
                return int(port)
        time.sleep(0.02)
    if process.poll() is None:
        process.terminate()
    process.wait(timeout=5)
    pid_file.unlink(missing_ok=True)
    raise Refused(f"hook receiver did not start; see {session_id}.hook.log")


def finish_hook_receiver(places: Places, session_id: str) -> None:
    pid_file = places.rows / f"{session_id}.hook.pid"
    port_file = places.rows / f"{session_id}.hook.port"
    if pid_file.exists():
        pid = int(pid_file.read_text())
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        else:
            deadline = time.monotonic() + 5
            while port_file.exists():
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                if time.monotonic() >= deadline:
                    raise Refused(f"hook receiver {pid} did not stop; retry finish")
                time.sleep(0.02)
        # Reap it when prepare and finish run in the same process (e.g. tests).
        with suppress(ChildProcessError):
            os.waitpid(pid, os.WNOHANG)
        pid_file.unlink()
    events = {}
    raw = places.rows / f"{session_id}.hook-batches.jsonl"
    if raw.exists():
        for number, line in enumerate(raw.read_text().splitlines(), start=1):
            batch = json.loads(line)["body"]
            if not isinstance(batch, dict):
                continue
            batch_events = batch.get("events", [])
            if not isinstance(batch_events, list):
                raise Refused(f"{raw} line {number}: events must be an array")
            for event in batch_events:
                if not isinstance(event, dict) or type(event.get("seq")) is not int:
                    raise Refused(
                        f"{raw} line {number}: expected events with integer seq"
                    )
                source = event.get("source") or batch.get("source")
                if not isinstance(source, str):
                    raise Refused(
                        f"{raw} line {number}: expected an event or batch source"
                    )
                events[(source, event["seq"])] = {**event, "source": source}
    rows = sorted(events.values(), key=lambda event: event["seq"])
    (places.rows / f"{session_id}.hook.json").write_text(
        json.dumps(rows, indent=2) + "\n"
    )
    if not rows:
        print(
            f"warning: no live hook events received for {session_id}", file=sys.stderr
        )


# --- preparing the workspace --------------------------------------------------


def fresh_workspace(places: Places, session_id: str, scenario: str) -> None:
    if not (places.home / "env.sh").is_file():
        raise Refused(f"{places.home} is not set up; run setup first")
    work = places.work.resolve()
    if places.home.resolve() not in work.parents:
        raise Refused(f"refusing to replace {work}: it is outside {places.home}")
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(
        TASK, work, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache")
    )
    places.rows.mkdir(parents=True, exist_ok=True)
    vscode = work / ".vscode"
    vscode.mkdir()
    settings = workspace_settings(session_id, scenario, places.rows)
    (vscode / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    (vscode / "calibration.code-snippets").write_text(
        json.dumps(TDEF_SNIPPET, indent=2) + "\n"
    )
    if scenario in HOOKED:
        hooks = subprocess.run(
            [
                UV,
                "run",
                "--no-sync",
                "protocol",
                "derive",
                "agent-hooks",
                str(HOOKS_PROTOCOL),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        (work / ".claude").mkdir()
        (work / ".claude" / "settings.json").write_text(hooks)
    session_sh = [
        f'source "{places.home / "env.sh"}"',
        f'source "{ROOT / ".venv" / "bin" / "activate"}"',
        f'cd "{work}"',
    ]
    if scenario in HOOKED:
        session_sh.append(
            "export STUDY_PARTICIPANT=operator STUDY_CONDITION=unspecified "
            f"STUDY_SESSION={session_id}"
        )
    (places.home / "session.sh").write_text("\n".join(session_sh) + "\n")


def code_cli() -> str:
    found = shutil.which("code")
    if found:
        return found
    if CODE_APP.exists():
        return str(CODE_APP)
    raise Refused("VS Code's `code` command was not found")


def record_environment(
    places: Places, session_id: str, scenario: str, hashes: dict[str, str]
) -> None:
    """Save the versions and settings in force (plan, section 6, step 3)."""
    code = code_cli()
    lines = [
        instrument_record(hashes),
        subprocess.run([code, "--version"], capture_output=True, text=True).stdout,
        subprocess.run(
            [code, "--list-extensions", "--show-versions", "--profile", PROFILE],
            capture_output=True,
            text=True,
        ).stdout,
    ]
    if BUILTIN_COPILOT.exists():
        version = json.loads(BUILTIN_COPILOT.read_text()).get("version")
        lines.append(f"built-in copilot@{version}\n")
    if scenario in AGENT:
        claude = shutil.which("claude")
        if claude:
            lines.append(
                subprocess.run(
                    [claude, "--version"], capture_output=True, text=True
                ).stdout
            )
    (places.rows / f"{session_id}.env.txt").write_text("".join(lines))
    shutil.copy(
        places.work / ".vscode" / "settings.json",
        places.rows / f"{session_id}.settings.json",
    )


# --- commands ----------------------------------------------------------------


def cmd_setup(
    places: Places, install: bool, extensions_root: Path | None = None
) -> None:
    for folder in (places.work, places.home / "rows", places.home / "dry" / "rows"):
        folder.mkdir(parents=True, exist_ok=True)
    (places.home / "env.sh").write_text(env_sh(places))
    print(f"set up {places.home}")
    if not install:
        return
    if not VSIX.exists():
        raise Refused(f"{VSIX} is missing; run: npm --prefix extension run package")
    code = code_cli()
    probe = subprocess.run(
        [code, "--list-extensions", "--profile", PROFILE],
        capture_output=True,
        text=True,
    )
    if "not found" in probe.stdout + probe.stderr:
        raise Refused(
            f"The VS Code profile {PROFILE!r} does not exist yet, and only VS Code\n"
            "itself can create one. Open it once, close that window, then rerun\n"
            "setup:\n"
            f'  "{code}" --profile {PROFILE} "{places.work}"'
        )
    for extension in (*PROFILE_EXTENSIONS, str(VSIX)):
        result = subprocess.run(
            [code, "--install-extension", extension, "--profile", PROFILE, "--force"]
        )
        if result.returncode:
            raise Refused(f"installing {extension} into {PROFILE!r} failed")
    (places.home / "tern-installed.sha256").write_text(
        json.dumps(installed_instrument(extensions_root), indent=2) + "\n"
    )
    print(f"extensions installed into the VS Code profile {PROFILE!r}")


def check_freeze() -> None:
    if not MANIFEST.exists():
        raise Refused(
            "not frozen yet: run scripts/freeze_calibration.py write and commit "
            "docs/calibration-freeze.json before session 1 (dry runs need no freeze)"
        )
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("freeze_calibration.py")),
            "check",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise Refused("the freeze check failed:\n" + result.stderr)


def cmd_prepare(
    places: Places,
    session_id: str,
    scenario: str,
    rep,
    open_code: bool,
    order: int | None,
    extensions_root: Path | None = None,
) -> None:
    if places.current.exists():
        raise Refused(
            "a previous session is pending; finish it first, labelling what "
            "actually happened (a crashed session is still labelled, with the "
            "crash in the note)"
        )
    if not places.dry:
        check_freeze()
        labelled = read_labels(places.labels)
        if any(r["sessionId"] == session_id for r in labelled):
            raise Refused(f"{session_id} is already labelled")
        if order is not None and len(labelled) != order - 1:
            raise Refused(
                f"labels.csv has {len(labelled)} rows, so the next session is "
                f"{len(labelled) + 1}, not {order}. Sessions run in the frozen order."
            )
    hashes = installed_instrument(extensions_root)
    places.rows.mkdir(parents=True, exist_ok=True)
    (places.rows / f"{session_id}.env.txt").write_text(instrument_record(hashes))
    if not places.dry:
        saved = places.home / "tern-installed.sha256"
        if not saved.is_file():
            raise Refused("no saved installed-instrument hash; run setup first")
        if (
            json.loads(saved.read_text()).get("installedSha256")
            != hashes["installedSha256"]
        ):
            raise Refused(
                "the installed TERN instrument differs from setup; restore it first"
            )
    fresh_workspace(places, session_id, scenario)
    record_environment(places, session_id, scenario, hashes)
    sheet = operator_sheet(places, session_id, scenario, order)
    if scenario in HOOKED:
        port = start_hook_receiver(places, session_id)
        with (places.home / "session.sh").open("a") as handle:
            handle.write(
                f"export STUDY_INGEST_ENDPOINT=http://127.0.0.1:{port}/ingest/events\n"
            )
    prepared = {
        "sessionId": session_id,
        "scenario": scenario,
        "rep": rep,
        "preparedAt": dt.datetime.now(dt.UTC).isoformat(),
        "preparedAtEpoch": dt.datetime.now(dt.UTC).timestamp(),
    }
    (places.rows / f"{session_id}.prepared.json").write_text(
        json.dumps(prepared, indent=2)
    )
    places.current.write_text(json.dumps(prepared))
    print(sheet)
    if open_code:
        subprocess.run(
            [code_cli(), "--profile", PROFILE, "--new-window", str(places.work)]
        )


def operator_sheet(places: Places, session_id: str, scenario: str, order) -> str:
    finish = "finish dry" if places.dry else f"finish {order}"
    script = scenario_script(scenario, PLAN.read_text())
    where = "dry run, not one of the 31" if places.dry else f"{order} of 31"
    return f"""
=== {session_id}  ({where})

Before
  1. VS Code opens {places.work} in the {PROFILE!r} profile. Close any older
     window on that folder first. Check the extensions view shows only the
     profile's extensions.
  2. In the integrated terminal, paste:   source "{places.home / "session.sh"}"
  3. Run "StudyLoop: Start Study Session": participant operator, condition
     Unspecified. The pre-flight must list edit bursts, AI lifecycle and
     clipboard as captured.

If TERN offers to resume an EARLIER session when the window opens: Discard.
If VS Code reloads or crashes mid-session: click "Resume session" (never x).

During (about 10 minutes)
{script}

After
  4. Run "StudyLoop: End Study Session", then close the "Study Debrief" tab;
     session_end is written only after that.
  5. Straight away:
     uv run --no-sync python scripts/calibration_session.py {finish} \\
       --ai-used true|false --exposed true|false --assisted true|false --note "..."
  6. Close the VS Code window. Do not open the rows folder.
"""


def cmd_finish(
    places: Places,
    ai_used: str,
    exposed: str,
    assisted: str,
    note: str,
    reviewer: str | None = None,
) -> int:
    reviewer = reviewer_choice(reviewer)
    validate_label(ai_used, exposed, assisted)
    current_file = places.current
    if not current_file.exists():
        raise Refused("no prepared session; run prepare first")
    current = json.loads(current_file.read_text())
    session_id, scenario = current["sessionId"], current["scenario"]
    if scenario in HOOKED:
        finish_hook_receiver(places, session_id)
    append_label(
        places.labels,
        {
            "sessionId": session_id,
            "scenario": scenario,
            "aiUsed": ai_used,
            "exposed": exposed,
            "assisted": assisted,
            "rep": current["rep"],
            "operatorNote": note,
        },
    )
    print(f"labelled {session_id}: aiUsed={ai_used}")
    current_file.unlink()
    save_task_evidence(places, session_id)
    import_error = None
    if scenario in AGENT:
        try:
            cmd_import_agent(places, session_id)
        except Refused as exc:
            import_error = exc
    result = cmd_verify(places, session_id, reviewer)
    if import_error:
        raise import_error
    return result


def cmd_import_agent(places: Places, session_id: str) -> None:
    """Archive every session transcript and rewrite only agent outputs."""
    retry = (
        f"import-agent dry {session_id}"
        if places.dry
        else (f"import-agent {session_id.split('-')[1].lstrip('0')}")
    )
    try:
        _import_agent(places, session_id)
    except (Refused, OSError, ValueError, subprocess.SubprocessError) as exc:
        raise Refused(
            f"agent import failed for {session_id}: {exc}. "
            f"The label is unchanged; run {retry} to retry."
        ) from None


def _import_agent(places: Places, session_id: str) -> None:
    if not any(r["sessionId"] == session_id for r in read_labels(places.labels)):
        raise Refused(f"{session_id} is not labelled; run finish first")
    prepared_file = places.rows / f"{session_id}.prepared.json"
    prepared = json.loads(prepared_file.read_text())
    scenario = prepared["scenario"]
    if scenario not in AGENT:
        raise Refused(f"{session_id} is not an agent scenario")
    folder = transcript_dir(places.work)
    transcripts = sorted(
        p
        for p in folder.glob("*.jsonl")
        if p.is_file() and p.stat().st_mtime >= prepared["preparedAtEpoch"]
    )
    if not transcripts:
        raise Refused(f"no Claude Code transcripts in {folder} since prepare")
    archive = places.rows / f"{session_id}.transcripts"
    archive.mkdir(exist_ok=True)
    for transcript in transcripts:
        shutil.copy2(transcript, archive / transcript.name)
    prepared["transcripts"] = [p.name for p in transcripts]
    prepared_file.write_text(json.dumps(prepared, indent=2) + "\n")
    if scenario not in HOOKED:
        print(f"archived {len(transcripts)} transcript(s) for {session_id}")
        return
    rows = []
    for transcript in transcripts:
        result = subprocess.run(
            [
                UV,
                "run",
                "--no-sync",
                "python",
                "-m",
                "agent_capture.import_transcript",
                str(archive / transcript.name),
                "--participant",
                "operator",
                "--condition",
                "unspecified",
                "--session",
                session_id,
                "--print",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise Refused(f"importing {transcript.name} exited {result.returncode}")
        imported = json.loads(result.stdout)
        if not isinstance(imported, list) or not all(
            isinstance(row, dict) and isinstance(row.get("seq"), int)
            for row in imported
        ):
            raise Refused(f"importing {transcript.name} did not return event rows")
        offset = len(rows)
        for row in imported:
            row["source"] = "agent-capture"
            row["seq"] += offset
        rows.extend(imported)
    out = places.rows / f"{session_id}.agent.json"
    temporary = out.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(rows, indent=2) + "\n")
    temporary.replace(out)
    print(f"imported {len(transcripts)} transcript(s) -> {out.name}")


# --- blinded post-session checks ---------------------------------------------


def save_task_evidence(places: Places, session_id: str) -> None:
    """Capture task evidence once at finish, never from TERN or agent rows."""
    try:
        before = (TASK / "inventory.py").read_text().splitlines(keepends=True)
        after = (places.work / "inventory.py").read_text().splitlines(keepends=True)
        lines = difflib.unified_diff(
            before, after, fromfile="task/inventory.py", tofile="work/inventory.py"
        )
        diff = "".join(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in lines
        )
    except (OSError, UnicodeError):
        diff = "Task diff unavailable: inventory.py could not be read.\n"
    (places.rows / f"{session_id}.inventory.diff").write_text(diff)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=places.work,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=300,
        )
        # Keep the summary only; test tracebacks are unnecessary for this check.
        counts = pytest_counts(result.stdout)
        summary = ", ".join(f"{count} {name}" for name, count in counts.items())
        text = (
            f"{summary or 'No pytest counts available'}\n"
            f"exit code: {result.returncode}\n"
        )
    except (OSError, UnicodeError, subprocess.SubprocessError):
        text = "Task pytest unavailable: could not complete within 300 seconds.\n"
    (places.rows / f"{session_id}.pytest.txt").write_text(text)


def pytest_counts(text: str) -> dict[str, int]:
    """Read pytest's summary, without inferring procedure or label correctness."""
    matches = re.findall(
        r"\b(\d+) "
        r"(passed|failed|skipped|deselected|xfailed|xpassed|errors?|warnings?)\b",
        text,
    )
    return {name: int(count) for count, name in matches}


def archived_transcripts(places: Places, session_id: str) -> list[Path]:
    return sorted(
        p
        for p in (places.rows / f"{session_id}.transcripts").glob("*.jsonl")
        if p.is_file() and not p.is_symlink()
    )


def blinded_review(
    places: Places,
    session_id: str,
    scenario: str,
    label: dict,
    report: dict,
    reviewer: str,
) -> tuple[str, str]:
    """The subprocess sees a fresh allowlisted bundle, never instrument files."""
    with tempfile.TemporaryDirectory(prefix="calibration-review-") as temporary:
        root = Path(temporary)
        bundle = root / "bundle"
        bundle.mkdir()
        try:
            script = scenario_script(scenario, PLAN.read_text())
            (bundle / "scenario.md").write_text(script + "\n")
            (bundle / "label.json").write_text(json.dumps(label, indent=2) + "\n")
            (bundle / "verify.json").write_text(json.dumps(report, indent=2) + "\n")
            for name in ("inventory.diff", "pytest.txt"):
                source = places.rows / f"{session_id}.{name}"
                text = source.read_text() if source.is_file() else "Unavailable.\n"
                (bundle / name).write_text(text)
            if scenario in AGENT:
                listing = "".join(
                    f"{path.name}\t{path.stat().st_size} bytes\n"
                    for path in archived_transcripts(places, session_id)
                )
                (bundle / "transcripts.txt").write_text(listing)
        except (Refused, OSError, ValueError):
            return "warn", "review bundle could not be prepared"
        out = root / "reply.json"
        executable = os.environ.get(f"CALIBRATION_{reviewer.upper()}", reviewer)
        if reviewer == "codex":
            command = [
                executable,
                "exec",
                "--skip-git-repo-check",
                "-s",
                "read-only",
                "-m",
                "gpt-6.1-sol",
                "-o",
                str(out),
                REVIEW_PROMPT,
            ]
        else:
            command = [executable, "-p", "--model", "sonnet", REVIEW_PROMPT]
        try:
            result = subprocess.run(
                command,
                cwd=bundle,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if reviewer == "claude":
                out.write_text(result.stdout)
            reply = out.read_text() if out.is_file() else ""
        except FileNotFoundError:
            return "warn", "reviewer executable unavailable"
        except subprocess.TimeoutExpired:
            return "warn", "reviewer timed out after 300 seconds"
        except (OSError, UnicodeError, subprocess.SubprocessError):
            return "warn", "reviewer could not complete"
        try:
            parsed = json.loads(reply)
        except ValueError:
            parsed = {"raw": reply}
        (places.rows / f"{session_id}.review.json").write_text(
            json.dumps(parsed, indent=2) + "\n"
        )
        if result.returncode:
            return "warn", f"reviewer exited {result.returncode}"
        if (
            not isinstance(parsed, dict)
            or parsed.get("verdict") not in ("ok", "concern")
            or not isinstance(parsed.get("concerns"), list)
            or not all(isinstance(item, str) for item in parsed["concerns"])
            or not isinstance(parsed.get("suggestedDeviation"), str | type(None))
            or "suggestedDeviation" not in parsed
        ):
            return "warn", "reviewer reply was not the requested JSON object"
        if parsed["verdict"] == "concern" or parsed["concerns"]:
            return "warn", "reviewer recorded a procedure or label concern"
        return "ok", "reviewer reported no concern"


def reviewer_choice(reviewer: str | None) -> str:
    reviewer = (
        reviewer
        if reviewer is not None
        else os.environ.get("CALIBRATION_REVIEWER", "none")
    )
    if reviewer not in {"none", "codex", "claude"}:
        raise Refused("reviewer must be none, codex or claude")
    return reviewer


HEALTH_TYPES = frozenset(
    {"session_start", "session_end", "environment_snapshot", "behavior_sensor_error"}
)
CAPTURE_FLAGS = ("aiLifecycle", "editBursts", "clipboard")


def capture_health(rows_dir: Path, session_id: str) -> list[dict]:
    """Infrastructure facts only. Every other event type is skipped unread, so no
    signal can reach the output (the plan forbids looking at signals mid-study)."""
    seqs: list[int] = []
    stamps: list[str] = []
    seen: set[str] = set()
    flags: dict = {}
    sensor_errors = foreign = files = 0
    for path in sorted(rows_dir.glob("operator_*.jsonl")):
        mine = other = 0
        with path.open(errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if row.get("sessionId") != session_id:
                    other += 1
                    continue
                mine += 1
                if isinstance(row.get("seq"), int):
                    seqs.append(row["seq"])
                if isinstance(row.get("ts"), str):
                    stamps.append(row["ts"])
                kind = row.get("type")
                if kind not in HEALTH_TYPES:
                    continue
                seen.add(kind)
                if kind == "environment_snapshot":
                    flags = (row.get("payload") or {}).get("auditCapture") or {}
                elif kind == "behavior_sensor_error":
                    sensor_errors += 1
        if mine:
            files += 1
            foreign += other
    if not files:
        return [{"check": "capture", "status": "fail", "detail": "no TERN rows"}]
    problems = [
        f"no {kind}"
        for kind in ("session_start", "session_end", "environment_snapshot")
        if kind not in seen
    ]
    problems += [f"capture switch {f} off" for f in CAPTURE_FLAGS if not flags.get(f)]
    ordered = sorted(seqs)
    gaps = sum(1 for a, b in itertools.pairwise(ordered) if b != a + 1)
    if gaps:
        problems.append(f"{gaps} sequence gap(s)")
    checks = [
        {
            "check": "capture",
            "status": "fail" if problems else "ok",
            "detail": "; ".join(problems) + " (the session will be an abstention)"
            if problems
            else "start, end, capture switches and sequence complete",
        }
    ]
    if stamps:
        span = dt.datetime.fromisoformat(max(stamps).replace("Z", "+00:00"))
        span -= dt.datetime.fromisoformat(min(stamps).replace("Z", "+00:00"))
        minutes = round(span.total_seconds() / 60, 1)
        checks.append(
            {
                "check": "duration",
                "status": "ok" if 5 <= minutes <= 20 else "warn",
                "detail": f"{minutes} minutes",
            }
        )
    checks.append(
        {
            "check": "sensors",
            "status": "warn" if sensor_errors else "ok",
            "detail": f"{sensor_errors} sensor error(s)",
        }
    )
    if foreign:
        checks.append(
            {
                "check": "files",
                "status": "warn",
                "detail": f"{foreign} row(s) of other sessions in the same file",
            }
        )
    return checks


def environment_drift(places: Places, session_id: str) -> list[dict]:
    """Compare this session's recorded versions with the earliest real session."""
    current = places.rows / f"{session_id}.env.txt"
    if not current.is_file():
        return [{"check": "drift", "status": "warn", "detail": "no env.txt"}]
    earlier = sorted(
        p
        for p in places.rows.glob("cal-*.env.txt")
        if p.name < current.name or places.dry
    )

    def facts(path: Path) -> set[str]:
        return {
            line.strip()
            for line in path.read_text().splitlines()
            if line.strip() and "(Claude Code)" not in line
        }

    checks = []
    if earlier and earlier[0] != current:
        changed = sorted(facts(current) ^ facts(earlier[0]))
        checks.append(
            {
                "check": "drift",
                "status": "warn" if changed else "ok",
                "detail": "versions differ from the first session: "
                + ", ".join(changed)
                if changed
                else "versions match the first session",
            }
        )
    else:
        checks.append({"check": "drift", "status": "ok", "detail": "first session"})
    saved = places.home / "tern-installed.sha256"
    if not places.dry and saved.is_file():
        expected = json.loads(saved.read_text()).get("installedSha256")
        ok = f"TERN installedSha256={expected}" in current.read_text()
        checks.append(
            {
                "check": "instrument",
                "status": "ok" if ok else "fail",
                "detail": "installed TERN matches setup"
                if ok
                else "installed TERN differs from setup",
            }
        )
    return checks


def settings_check(places: Places, session_id: str, scenario: str) -> dict:
    path = places.rows / f"{session_id}.settings.json"
    try:
        recorded = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"check": "settings", "status": "fail", "detail": "no settings record"}
    expected = workspace_settings(session_id, scenario, places.rows)
    differ = sorted(
        k
        for k in expected.keys() | recorded.keys()
        if expected.get(k) != recorded.get(k)
    )
    return {
        "check": "settings",
        "status": "fail" if differ else "ok",
        "detail": "differ: " + ", ".join(differ) if differ else "as the plan says",
    }


def cmd_verify(places: Places, session_id: str, reviewer: str | None = None) -> int:
    reviewer = reviewer_choice(reviewer)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", session_id):
        raise Refused("invalid session ID")
    places.rows.mkdir(parents=True, exist_ok=True)
    checks = []

    def add(name: str, status: str, detail: str, **facts):
        checks.append({"check": name, "status": status, "detail": detail, **facts})

    label = {}
    scenario = ""
    try:
        matches = [
            r for r in read_labels(places.labels) if r["sessionId"] == session_id
        ]
        if len(matches) != 1:
            raise Refused("expected exactly one label row")
        label = {key: matches[0].get(key) for key in LABEL_HEADER}
        if set(matches[0]) != set(LABEL_HEADER):
            raise Refused("unexpected label fields")
        if any(not isinstance(label.get(key), str) for key in LABEL_HEADER):
            raise Refused("label fields must all be present")
        scenario = label["scenario"]
        if scenario not in _load("calibration_order").SCENARIOS:
            raise Refused("unknown label scenario")
        validate_label(label["aiUsed"], label["exposed"], label["assisted"])
        if int(label["rep"]) < (0 if places.dry else 1):
            raise Refused("invalid label repetition")
        prepared = json.loads((places.rows / f"{session_id}.prepared.json").read_text())
        if not isinstance(prepared, dict) or any(
            str(prepared.get(key)) != label[key]
            for key in ("sessionId", "scenario", "rep")
        ):
            raise Refused("label does not match prepared session")
        if not places.dry:
            order = int(session_id.split("-")[1])
            if session_for(order) != (session_id, scenario, int(label["rep"])):
                raise Refused("label does not match frozen order")
    except (Refused, OSError, ValueError, KeyError, IndexError, TypeError, csv.Error):
        add("label", "fail", "label missing, inconsistent or mismatched to preparation")
    else:
        add("label", "ok", "label exists and is internally consistent")

    checks.extend(capture_health(places.rows, session_id))
    if scenario:
        checks.append(settings_check(places, session_id, scenario))
    checks.extend(environment_drift(places, session_id))

    if scenario in REQUIRED_NOTE:
        note = label.get("operatorNote")
        note = note if isinstance(note, str) else ""
        missing = not note.strip() or (
            scenario == "benign-stackoverflow-paste" and "http" not in note.lower()
        )
        add(
            "note",
            "warn" if missing else "ok",
            f"operator note requires {REQUIRED_NOTE[scenario]}",
        )
    else:
        add("note", "ok", "no scenario-specific note required")
    if scenario in HOOKED:
        batches = places.rows / f"{session_id}.hook-batches.jsonl"
        try:
            with batches.open() as handle:
                count = sum(1 for line in handle if line.strip())
        except (OSError, UnicodeError):
            count = 0
        add("hooks", "ok" if count else "warn", f"{count} hook batches", count=count)
    if scenario in AGENT:
        count = len(archived_transcripts(places, session_id))
        add(
            "transcripts",
            "ok" if count else "warn",
            f"{count} archived transcripts",
            count=count,
        )
    try:
        counts = pytest_counts((places.rows / f"{session_id}.pytest.txt").read_text())
    except (OSError, UnicodeError):
        counts = {}
    summary = ", ".join(f"{value} {name}" for name, value in counts.items())
    add(
        "task",
        "ok",
        f"pytest counts (informational): {summary or 'unavailable'}",
        counts=counts,
    )
    report = {"sessionId": session_id, "checks": checks}
    if reviewer != "none":
        try:
            (places.rows / f"{session_id}.review.json").unlink(missing_ok=True)
            status, detail = blinded_review(
                places, session_id, scenario, label, report, reviewer
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            status, detail = "warn", "reviewer could not complete"
        add("reviewer", status, detail)
    (places.rows / f"{session_id}.verify.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    for check in checks:
        print(f"{check['status']}: {check['check']}: {check['detail']}")
    print(DEVIATIONS)
    return int(any(check["status"] == "fail" for check in checks))


def cmd_check_dry(places: Places) -> int:
    out = places.home / "dry" / "matrix"
    rows = sorted(
        str(p)
        for p in places.rows.glob("*.jsonl")
        if not p.name.endswith(".hook-batches.jsonl")
    )
    hooks = sorted(places.rows.glob("*.hook.json"))
    live_sessions = {p.name.removesuffix(".hook.json") for p in hooks}
    # Imported transcripts overlap live events; they must not mask failed delivery.
    rows += sorted(
        str(p)
        for p in places.rows.glob("*.agent.json")
        if p.name.removesuffix(".agent.json") not in live_sessions
    )
    rows += [str(p) for p in hooks]
    if not rows:
        raise Refused(f"no dry-run rows in {places.rows}")
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("run_calibration.py")),
            "--rows",
            *rows,
            "--labels",
            str(places.labels),
            "--out",
            str(out),
        ],
        cwd=ROOT,
    )
    report = out / "report.json"
    if report.exists():
        print(f"dry-run report: {report}")
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="{setup,prepare,finish,verify,import-agent,check-dry}",
    )
    setup = sub.add_parser("setup")
    setup.add_argument("--no-install", action="store_true")
    prepare = sub.add_parser("prepare")
    prepare.add_argument("order", help="1..31, or 'dry'")
    prepare.add_argument("scenario", nargs="?", help="scenario, for a dry run")
    prepare.add_argument("--no-open", action="store_true")
    finish = sub.add_parser("finish")
    finish.add_argument("order", help="the session number, or 'dry'")
    finish.add_argument("--ai-used", required=True, choices=("true", "false"))
    finish.add_argument("--exposed", required=True, choices=("true", "false"))
    finish.add_argument("--assisted", required=True, choices=("true", "false"))
    finish.add_argument("--note", default="")
    verify = sub.add_parser("verify")
    verify.add_argument("order", help="the session number, or 'dry'")
    verify.add_argument("session_id", nargs="?", help="required for dry")
    for command in (finish, verify):
        command.add_argument("--reviewer", choices=("none", "codex", "claude"))
    agent_import = sub.add_parser("import-agent")
    agent_import.add_argument("order", help="the session number, or 'dry'")
    agent_import.add_argument("session_id", nargs="?", help="required for dry")
    sub.add_parser("check-dry")
    receiver = sub.add_parser("serve-hooks")
    receiver.add_argument("--out", required=True, type=Path)
    receiver.add_argument("--port-file", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "setup":
            cmd_setup(Places.default(), install=not args.no_install)
        elif args.command == "serve-hooks":
            serve_hooks(args.out, args.port_file)
        elif args.command == "prepare":
            if args.order == "dry":
                if not args.scenario:
                    raise Refused("a dry run names its scenario: prepare dry no-ai")
                places = Places.default(dry=True)
                sid = dry_session(args.scenario, dt.datetime.now())
                cmd_prepare(places, sid, args.scenario, 0, not args.no_open, None)
            else:
                order = int(args.order)
                sid, scenario, rep = session_for(order)
                cmd_prepare(
                    Places.default(), sid, scenario, rep, not args.no_open, order
                )
        elif args.command == "finish":
            dry = args.order == "dry"
            places = Places.default(dry=dry)
            if not dry:
                expected = session_for(int(args.order))[0]
                if not places.current.is_file():
                    raise Refused("no prepared session; run prepare first")
                current = json.loads(places.current.read_text())
                if current["sessionId"] != expected:
                    prepared = current["sessionId"]
                    raise Refused(f"the prepared session is {prepared}, not {expected}")
            return cmd_finish(
                places,
                args.ai_used,
                args.exposed,
                args.assisted,
                args.note,
                args.reviewer,
            )
        elif args.command in {"import-agent", "verify"}:
            dry = args.order == "dry"
            if dry:
                if not args.session_id:
                    raise Refused(f"use {args.command} dry SESSION_ID")
                sid = args.session_id
            else:
                if args.session_id:
                    raise Refused(f"{args.command} takes only its session number")
                sid = session_for(int(args.order))[0]
            if args.command == "verify":
                return cmd_verify(Places.default(dry=dry), sid, args.reviewer)
            cmd_import_agent(Places.default(dry=dry), sid)
        else:
            return cmd_check_dry(Places.default(dry=True))
    except (KeyError, IndexError, TypeError, csv.Error):
        print("invalid or incomplete session data", file=sys.stderr)
        return 1
    except (Refused, OSError, ValueError, subprocess.SubprocessError) as refusal:
        print(refusal, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
