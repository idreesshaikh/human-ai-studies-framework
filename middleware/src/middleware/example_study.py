"""
``python -m middleware seed-example``: one clearly labelled SYNTHETIC study.

A fresh install has nothing in Run or Data. This seeds a single example study
so the whole loop is visible: a v6 protocol from the featured crossover
template, a saved recruitment plan, participant links, and simulated sessions.

Nothing here is a finding. Every event carries ``payload.synthetic = true``,
the marker the service already uses for simulated rows, so the sessions stay
out of data bundles, pilot estimates, analysis recipes and every default read.
The Data tab shows them only for this study, under a "synthetic example" notice
(``/studies/{id}/status`` reports ``syntheticExample``).

Apart from the study row and its protocol draft (written exactly as
``POST /projects/{slug}/studies`` writes them, but under a fixed id), all rows
are created by calling the real HTTP routes in-process: plan, mint, redeem,
capture-config and ingest. The stored rows are therefore shaped, stamped and
flagged exactly like captured data.
"""

from __future__ import annotations

import os
import random
import warnings
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import yaml

from middleware.settings import Settings

EXAMPLE_STUDY_ID = "example-copilot-and-bug-fixing-synthetic-data"
EXAMPLE_TITLE = "Example: Copilot and bug fixing (synthetic data)"
TEMPLATE_ID = "within-subjects-crossover-v2"
CONDITIONS = ["without-ai", "with-copilot"]
CONTROL, TREATMENT = CONDITIONS

SEED = 20261110
PLANNED_PARTICIPANTS = 24
# Participants with two finished sessions each; one more has an interrupted one.
COMPLETED_PARTICIPANTS = 12
INTERRUPTED_PARTICIPANT = COMPLETED_PARTICIPANTS + 1
# (participant, block) -> the imperfection that session shows.
TASK_MISMATCH = (7, 1)  # editor opened on the other task; one event lost
AI_IN_CONTROL = (5, CONTROL)  # assistant events captured in the control arm

EVENT_SCHEMA_VERSION = 6
FIRST_DAY = datetime(2026, 10, 5, tzinfo=UTC)  # a Monday
HARNESS_TESTS = 6


def is_example_study(study_id: str) -> bool:
    return study_id == EXAMPLE_STUDY_ID


def example_protocol() -> dict:
    """The featured crossover template, renamed for this example and validated."""
    from protocol.loader import validate_protocol

    from middleware import template_registry

    protocol = template_registry.instantiate_template(
        TEMPLATE_ID,
        {
            "studyId": EXAMPLE_STUDY_ID,
            "title": EXAMPLE_TITLE,
            "participantPlan": PLANNED_PARTICIPANTS,
            "researchQuestion": (
                "Does GitHub Copilot change the time developers take to reach a "
                "first passing test on a bug-fixing task?"
            ),
            "taskDescription": (
                "SYNTHETIC EXAMPLE. Two matched bug-fixing tasks, one without AI "
                "and one with Copilot, order counterbalanced. No participant "
                "took part; all sessions in this study are simulated."
            ),
            "researchers": ["StudyLoop example (synthetic data)"],
            "ethicsRef": "not applicable: synthetic example, no participants",
        },
    )["protocol"]
    renamed = dict(zip(protocol["conditions"], CONDITIONS, strict=True))
    protocol["conditions"] = list(CONDITIONS)
    protocol["controlConditions"] = [
        renamed[c] for c in protocol.get("controlConditions", [])
    ]
    for task, title in zip(
        protocol["tasks"], ("Bug-fixing task A", "Bug-fixing task B"), strict=True
    ):
        task["title"] = title
        task["description"] = "Synthetic example task; no materials exist."
    errors = validate_protocol(protocol)
    if errors:
        raise RuntimeError("example protocol is invalid: " + "; ".join(errors))
    return protocol


@contextmanager
def _quiet_app_env():
    """Building the app must not start the corpus import or refresh threads."""
    patch = {"MIDDLEWARE_CORPUS_BOOTSTRAP": "0", "MIDDLEWARE_REFRESH_INTERVAL_H": ""}
    before = {k: os.environ.get(k) for k in patch}
    os.environ.update(patch)
    try:
        yield
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class _Clock:
    """The server clock while seeding, so stored receive times are fixed too."""

    def __init__(self) -> None:
        self.now = FIRST_DAY

    def __call__(self) -> datetime:
        return self.now


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _session_start(participant: int, block: int) -> datetime:
    """Two participants per weekday; the second block starts an hour later."""
    day = (participant - 1) // 2
    start = FIRST_DAY + timedelta(days=day + 2 * (day // 5))
    hour = 9.5 if participant % 2 else 14
    return start + timedelta(hours=hour + block)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _traits(rng: random.Random) -> dict:
    """One simulated participant: a baseline and a personal response to the tool."""
    return {
        "baselineMin": _clamp(rng.gauss(22, 5), 11, 34),
        "copilotDeltaMin": rng.gauss(-3.5, 4.5),
        "workload": rng.gauss(55, 12),
        "workloadDelta": rng.gauss(-7, 9),
    }


def _tlx(rng: random.Random, survey: dict, level: float) -> dict:
    offsets = {"physical_demand": -35, "performance": -15, "frustration": -8}
    out = {}
    for item in survey["items"]:
        scale = item["scale"]
        raw = level + offsets.get(item["id"], 0) + rng.gauss(0, 8)
        step = scale.get("step", 1)
        out[item["id"]] = int(
            _clamp(round(raw / step) * step, scale["min"], scale["max"])
        )
    return out


def _session_events(
    rng: random.Random,
    protocol: dict,
    config: dict,
    *,
    participant: int,
    block: int,
    condition: str,
    traits: dict,
    start: datetime,
    interrupted: bool,
) -> tuple[list[dict], list[dict], datetime]:
    """One session as (editor payloads, harness payloads, end time)."""
    from protocol.measures import score_survey
    from protocol.versioning import version_record

    minutes = traits["baselineMin"] + rng.gauss(0, 2.5) - 1.0 * block
    workload = traits["workload"] + rng.gauss(0, 5)
    if condition == TREATMENT:
        minutes += traits["copilotDeltaMin"]
        workload += traits["workloadDelta"]
    first_green_ms = int(_clamp(minutes, 7, 41) * 60_000)
    if interrupted:
        first_green_ms = 19 * 60_000  # never reached: the session stops before it
    ai_events = condition == TREATMENT or (participant, condition) == AI_IN_CONTROL

    timeline: list[tuple[int, str, dict]] = [
        (
            0,
            "session_start",
            {
                "plannedDurationMin": protocol["session"]["durationMinutes"],
                "fatigueIntervalMin": 15,
                "fatigueJitterPercent": 20,
                "ide": "vscode",
                "ideVersion": "1.105.0",
                "extensionVersion": "synthetic",
                "platform": "synthetic",
                "workspace": None,
            },
        ),
        (
            400,
            "environment_snapshot",
            {
                "recordedAt": _iso(start),
                "declaredTool": "GitHub Copilot" if condition == TREATMENT else "none",
                "modelName": None,
                "modelNameSource": "unknown",
                "provenance": config["settings"].get("tern.provenance", {}),
                "auditCapture": {
                    "aiLifecycle": True,
                    "editBursts": True,
                    "clipboard": True,
                },
                "captureConfigVersion": config["captureConfigVersion"],
            },
        ),
    ]
    work_ms = first_green_ms if not interrupted else 9 * 60_000
    bursts = rng.randint(9, 14) if not interrupted else 4
    suggestion = 0
    for at in sorted(rng.randint(20_000, work_ms - 5_000) for _ in range(bursts)):
        roll = rng.random()
        if condition == TREATMENT and roll < 0.38:
            origin = "ai"
        elif roll > 0.93:
            origin = "paste"
        else:
            origin = "human"
        chars = rng.randint(90, 420) if origin == "ai" else rng.randint(15, 170)
        if origin == "ai":
            suggestion += 1
            sid = f"sg-{suggestion}"
            timeline.append(
                (at - 1_800, "ai_suggestion", {"suggestionId": sid, "action": "shown"})
            )
            timeline.append(
                (
                    at - 200,
                    "ai_suggestion",
                    {
                        "suggestionId": sid,
                        "action": "accepted",
                        "visibleMs": 1_600,
                        "charCount": chars,
                        "lineCount": max(1, chars // 45),
                    },
                )
            )
        timeline.append(
            (
                at,
                "edit_burst",
                {
                    "file": f"src/module_{rng.randint(1, 3)}.py",
                    "charsAdded": chars,
                    "charsDeleted": rng.randint(0, 40),
                    "linesTouched": max(1, chars // 45 + rng.randint(0, 2)),
                    "durationMs": 40 if origin == "ai" else rng.randint(900, 9_000),
                    "origin": origin,
                },
            )
        )
    if ai_events and condition == CONTROL:
        for n, at in enumerate((6 * 60_000, 6 * 60_000 + 2_500), start=1):
            timeline.append(
                (
                    at,
                    "ai_suggestion",
                    {
                        "suggestionId": f"sg-{n}",
                        "action": "shown" if n == 1 else "dismissed",
                        **({"visibleMs": 2_500} if n == 2 else {}),
                    },
                )
            )
    for mark in (15, 30):
        if mark * 60_000 < work_ms:
            level = 2 + mark // 15 + rng.choice((-1, 0, 0, 1))
            timeline.append(
                (
                    mark * 60_000 + rng.randint(5_000, 60_000),
                    "fatigue_response",
                    {
                        "trigger": "timer",
                        "scaleId": "fatigue",
                        "points": 7,
                        "value": int(_clamp(level, 1, 7)),
                        "skipped": False,
                        "cancelled": False,
                        "msToAnswer": rng.randint(1_800, 6_500),
                        "deferralMs": 0,
                        "minutesIntoSession": mark,
                    },
                )
            )

    harness: list[tuple[int, dict]] = []
    failing = HARNESS_TESTS
    for at in sorted(
        rng.randint(90_000, work_ms - 20_000) for _ in range(rng.randint(2, 4))
    ):
        failing = max(1, failing - rng.randint(1, 2))
        harness.append(
            (
                at,
                {
                    "trigger": "save",
                    "passed": False,
                    "failed": failing,
                    "total": HARNESS_TESTS,
                },
            )
        )
    end_ms = work_ms + rng.randint(120_000, 240_000)
    if not interrupted:
        green = {
            "passed": True,
            "failed": 0,
            "total": HARNESS_TESTS,
            "firstGreenMs": first_green_ms,
        }
        harness.append((first_green_ms, {"trigger": "save", **green}))
        harness.append((end_ms - 500, {"trigger": "session-end", **green}))
        survey = protocol["instruments"]["surveys"][0]
        responses = _tlx(rng, survey, workload)
        timeline.append(
            (
                end_ms - 60_000,
                "survey_response",
                {
                    "instrumentId": survey["id"],
                    "instrumentVersion": survey["version"],
                    "instrumentHash": version_record(survey)["sha256"],
                    "timing": survey["timing"],
                    "responses": responses,
                    "msToComplete": rng.randint(35_000, 80_000),
                    "score": score_survey(survey, responses),
                },
            )
        )
        timeline.append((end_ms, "session_end", {"reason": "completed"}))

    def stamped(at: int, kind: str, payload: dict) -> dict:
        return {
            "v": EVENT_SCHEMA_VERSION,
            "ts": _iso(start + timedelta(milliseconds=at)),
            "mono": at,
            "type": kind,
            # The marker every reader already honours for simulated rows.
            "payload": {**payload, "synthetic": True},
        }

    timeline.sort(key=lambda item: item[0])
    editor = [stamped(*item) for item in timeline]
    outcomes = [stamped(at, "task_outcome", payload) for at, payload in harness]
    return editor, outcomes, start + timedelta(milliseconds=end_ms)


def _ok(response):
    if response.status_code >= 400:
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path} -> "
            f"{response.status_code}: {response.text[:400]}"
        )
    return response.json()


def seed_example(settings: Settings | None = None) -> dict:
    """Create the example study once; a second call changes nothing."""
    from middleware.db import (
        IMPLICIT_PROJECT_ID,
        ProtocolDraftRow,
        Study,
        make_session_factory,
    )

    settings = settings or Settings()
    factory = make_session_factory(settings.db_url)
    with factory() as s:
        if s.get(Study, EXAMPLE_STUDY_ID) is not None:
            return {"studyId": EXAMPLE_STUDY_ID, "created": False}

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from fastapi.testclient import TestClient
    except (ImportError, RuntimeError) as exc:  # httpx is a development dependency
        raise RuntimeError(
            "seed-example drives the service in-process and needs httpx; "
            "run `uv sync --all-packages` first"
        ) from exc
    from protocol.assignment import assign

    from middleware.app import create_app

    protocol = example_protocol()
    clock = _Clock()
    with factory() as s:
        s.add(Study(id=EXAMPLE_STUDY_ID, project_id=IMPLICIT_PROJECT_ID))
        s.add(
            ProtocolDraftRow(
                study_id=EXAMPLE_STUDY_ID,
                yaml=yaml.safe_dump(
                    protocol, sort_keys=False, default_flow_style=False
                ),
                compilation_id="",
                updated_at=_iso(clock()),
            )
        )
        s.commit()

    # Local single-user access: the seed is an operator command with the database
    # in hand, so it does not need (or have) a signed-in identity.
    local = replace(
        settings, auth="none", token=None, protocol_path=None, spa_required=False
    )
    with _quiet_app_env():
        app = create_app(local, clock=clock)
    # Only this temporary in-process app can mint/redeem the illustrative
    # links while building fixtures. A running service never enables this.
    app.state.seeding_example = True
    base = f"/studies/{EXAMPLE_STUDY_ID}"
    # A fixed simulation, not a secret.
    rng = random.Random(SEED)  # noqa: S311
    sessions = events = flagged = 0
    with TestClient(app) as client:
        try:
            _ok(
                client.post(
                    f"{base}/plan",
                    json={
                        "design": "within-subjects",
                        "test": "paired-t",
                        "distribution": "normal",
                        "effect": 0.6,
                        "sd": 1.0,
                        "alpha": 0.05,
                        "target_power": 0.8,
                        "dropout": 0.0,
                        "counterbalanced": True,
                        "planned_n": PLANNED_PARTICIPANTS,
                        "measure_id": "first-green-time",
                    },
                )
            )
            links = _ok(
                client.post(
                    f"{base}/enrollment/tokens",
                    json={"count": PLANNED_PARTICIPANTS, "grain": "participant"},
                )
            )
            for participant in range(1, INTERRUPTED_PARTICIPANT + 1):
                link = links[participant - 1]
                traits = _traits(rng)
                interrupted_participant = participant == INTERRUPTED_PARTICIPANT
                blocks = assign(protocol, participant - 1)
                for block in blocks[: 1 if interrupted_participant else None]:
                    start = _session_start(participant, block.index)
                    clock.now = start
                    if block.index == 0:
                        token = link["connectionString"].rsplit("#", 1)[-1]
                        credential = _ok(
                            client.post("/pair/redeem", json={"token": token})
                        )["sessionCredential"]
                    bearer = {"Authorization": f"Bearer {credential}"}
                    session_id = (
                        f"example-synthetic-{link['participantId']}-{block.index + 1}"
                    )
                    config = _ok(
                        client.get(
                            f"{base}/capture-config",
                            params={"sessionId": session_id},
                            headers=bearer,
                        )
                    )
                    editor, outcomes, end = _session_events(
                        rng,
                        protocol,
                        config,
                        participant=participant,
                        block=block.index,
                        condition=block.condition,
                        traits=traits,
                        start=start,
                        interrupted=interrupted_participant,
                    )
                    mismatch = (participant, block.index) == TASK_MISMATCH
                    other_task = next(
                        b.task_id for b in blocks if b.task_id != block.task_id
                    )
                    keys = {
                        "sessionId": session_id,
                        "participantId": link["participantId"],
                        "condition": block.condition,
                    }
                    editor = [
                        {
                            **keys,
                            "taskId": other_task if mismatch else block.task_id,
                            "seq": seq,
                            **event,
                        }
                        for seq, event in enumerate(editor)
                    ]
                    # Lost events are reported as gaps, never hidden.
                    lost = (
                        {3, 4} if interrupted_participant else {6} if mismatch else ()
                    )
                    editor = [e for e in editor if e["seq"] not in lost]
                    outcomes = [
                        {**keys, "taskId": block.task_id, "seq": seq, **event}
                        for seq, event in enumerate(outcomes)
                    ]
                    clock.now = end + timedelta(seconds=2)
                    for source, batch in (("tern", editor), ("task-harness", outcomes)):
                        stored = _ok(
                            client.post(
                                "/ingest/events",
                                json={"source": source, "events": batch},
                                headers=bearer,
                            )
                        )
                        events += stored["inserted"]
                        flagged += stored["flagged"]
                    sessions += 1
        except Exception:
            # Leave nothing half-seeded: a rerun must start from an empty study.
            client.delete(base)
            raise
    return {
        "studyId": EXAMPLE_STUDY_ID,
        "created": True,
        "title": EXAMPLE_TITLE,
        "participantLinks": len(links),
        "sessions": sessions,
        "events": events,
        "flaggedEvents": flagged,
    }
