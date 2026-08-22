"""Synthetic dry-run simulation (the "try a study on paper" path)."""

from __future__ import annotations

import logging
import random
import secrets
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from middleware.db import EnrollmentToken, SessionBlock

log = logging.getLogger(__name__)

PROFILES = ("fast", "struggling", "novice", "expert")

PROFILE_PARAMS: dict[str, dict[str, Any]] = {
    "fast": {
        "fatigue": (1, 2),
        "stuck_episodes": 0,
        "pastes": 1,
        "suggestion_accept": 0.15,
        "task_pass": 0.95,
        "first_green_ms": (8_000, 60_000),
        "agent_turns": 2,
        "focus_files": 1,
        "tlx": (1, 6),
    },
    "struggling": {
        "fatigue": (3, 5),
        "stuck_episodes": 3,
        "pastes": 6,
        "suggestion_accept": 0.7,
        "task_pass": 0.4,
        "first_green_ms": (60_000, 300_000),
        "agent_turns": 9,
        "focus_files": 3,
        "tlx": (10, 20),
    },
    "novice": {
        "fatigue": (2, 4),
        "stuck_episodes": 1,
        "pastes": 3,
        "suggestion_accept": 0.5,
        "task_pass": 0.7,
        "first_green_ms": (30_000, 120_000),
        "agent_turns": 5,
        "focus_files": 2,
        "tlx": (6, 12),
    },
    "expert": {
        "fatigue": (1, 3),
        "stuck_episodes": 0,
        "pastes": 2,
        "suggestion_accept": 0.35,
        "task_pass": 0.9,
        "first_green_ms": (5_000, 45_000),
        "agent_turns": 3,
        "focus_files": 2,
        "tlx": (2, 8),
    },
}


def profile_for(index: int, profile: str) -> str:
    """
    Resolve the profile label for a participant index; ``mixed`` cycles the four
    archetypes so a dry run sees every personality.
    """
    if profile == "mixed":
        return PROFILES[index % len(PROFILES)]
    return profile


def required_event_types(protocol: dict) -> set[str]:
    """The union of event types the protocol's planned recipes need."""
    import analysis.recipes  # noqa: F401 - registers the built-in recipes
    from analysis.core import REGISTRY

    types: set[str] = set()
    for entry in protocol.get("analysisPlan", []):
        for rid in entry.get("recipes", []):
            rec = REGISTRY.get(rid)
            if rec is not None:
                types |= rec.requires.events
    return types


def requires_metrics(protocol: dict) -> bool:
    import analysis.recipes  # noqa: F401 - registers the built-in recipes
    from analysis.core import REGISTRY

    return any(
        REGISTRY.get(rid) is not None and REGISTRY[rid].requires.metrics
        for entry in protocol.get("analysisPlan", [])
        for rid in entry.get("recipes", [])
    )


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def _payload(
    rng: random.Random, event_type: str, params: dict[str, Any], task_id: str, file: str
) -> dict:
    """One plausible payload for one event type."""
    if event_type == "fatigue_response":
        lo, hi = params["fatigue"]
        return {"score": rng.randint(lo, hi)}
    if event_type == "stuck_response":
        return {"evidenceMs": rng.randint(30_000, 4 * 60_000)}
    if event_type == "end_survey":
        lo, hi = params["tlx"]
        return {
            "mentalDemand": rng.randint(lo, hi),
            "effort": rng.randint(lo, hi),
            "frustration": rng.randint(lo, hi),
        }
    if event_type == "clipboard_paste":
        return {"charCount": rng.randint(5, 500)}
    if event_type == "task_outcome":
        passed = rng.random() < params["task_pass"]
        lo, hi = params["first_green_ms"]
        return {"passed": passed, "firstGreenMs": rng.randint(lo, hi)}
    if event_type == "agent_turn":
        return {
            "role": "assistant",
            "turnIndex": 0,
            "chars": rng.randint(100, 800),
            "responseChars": rng.randint(50, 600),
            "latencyMs": rng.randint(500, 9_000),
        }
    if event_type == "ai_suggestion":
        action = "shown"
        if rng.random() < params["suggestion_accept"]:
            action = "accepted"
        payload = {"action": action}
        if action == "accepted":
            payload["charCount"] = rng.randint(40, 2_000)
            payload["visibleMs"] = rng.randint(800, 120_000)
        return payload
    if event_type == "editor_focus":
        return {"file": file}
    return {}


def _session_events(
    rng: random.Random,
    types: set[str],
    params: dict[str, Any],
    task_id: str,
    file: str,
    session_id: str,
    participant_id: str,
    condition: str,
    start: datetime,
    source: str,
) -> list[dict]:
    """One session's event schedule, strictly ordered by timestamp."""
    session_events: list[dict] = []
    seq = 0
    t = start

    def emit(ts: datetime, type_: str, payload: dict) -> None:
        nonlocal seq
        session_events.append(
            {
                "session_id": session_id,
                "source": source,
                "seq": seq,
                "participant_id": participant_id,
                "condition": condition,
                "task_id": task_id,
                "v": 1,
                "ts": ts.isoformat(timespec="milliseconds"),
                "mono": 0,
                "type": type_,
                "payload": payload,
                "flags": [],
                "received_at": ts.isoformat(timespec="milliseconds"),
            }
        )
        seq += 1

    emit(t, "editor_focus", _payload(rng, "editor_focus", params, task_id, file))
    t += timedelta(seconds=rng.randint(20, 90))

    if "fatigue_response" in types:
        emit(
            t,
            "fatigue_response",
            _payload(rng, "fatigue_response", params, task_id, file),
        )
        t += timedelta(seconds=rng.randint(30, 120))

    for _ in range(params["stuck_episodes"]):
        emit(
            t,
            "stuck_response",
            _payload(rng, "stuck_response", params, task_id, file),
        )
        t += timedelta(seconds=rng.randint(120, 600))

    for _ in range(params["pastes"]):
        emit(
            t,
            "clipboard_paste",
            _payload(rng, "clipboard_paste", params, task_id, file),
        )
        t += timedelta(seconds=rng.randint(30, 240))

    for i in range(params["agent_turns"]):
        emit(
            t,
            "agent_turn",
            {
                "role": "assistant",
                "turnIndex": i,
                "chars": rng.randint(100, 800),
                "responseChars": rng.randint(50, 600),
                "latencyMs": rng.randint(500, 9_000),
            },
        )
        t += timedelta(seconds=rng.randint(45, 300))

    if "ai_suggestion" in types:
        emit(t, "ai_suggestion", _payload(rng, "ai_suggestion", params, task_id, file))
        t += timedelta(seconds=rng.randint(30, 120))

    if "task_outcome" in types:
        emit(t, "task_outcome", _payload(rng, "task_outcome", params, task_id, file))
        t += timedelta(seconds=rng.randint(15, 60))

    if "end_survey" in types:
        emit(t, "end_survey", _payload(rng, "end_survey", params, task_id, file))

    return session_events


def _session_metrics(
    rng: random.Random,
    session_id: str,
    participant_id: str,
    condition: str,
    task_id: str,
    t: datetime,
) -> list[dict]:
    """Per-session function metrics, mirroring what the harness emits."""
    rows = []
    for func in ("task_main", "agent_panel"):
        rows.append(
            {
                "sessionId": session_id,
                "participantId": participant_id,
                "condition": condition,
                "timestamp": t.isoformat(timespec="milliseconds"),
                "schemaVersion": 1,
                "function": func,
                "calls": rng.randint(1, 40),
                "nesting_penalty": round(rng.uniform(0.5, 2.0), 3),
                "lines": rng.randint(10, 400),
            }
        )
    return rows


def simulate(
    protocol: dict,
    count: int,
    profile: str = "mixed",
    seed: int | None = None,
    start: datetime | None = None,
) -> list[dict]:
    """Generate ``count`` synthetic participants' sessions as plain dicts."""
    if profile not in PROFILES and profile != "mixed":
        raise ValueError(f"unknown profile {profile!r}; pick from {PROFILES}")
    # S311: determinism beats cryptographic strength here — a seeded dry run must be
    # reproducible; this generator is never used for secrets.
    rng = random.Random(seed)  # noqa: S311
    from protocol.assignment import assign

    types = required_event_types(protocol)
    want_metrics = requires_metrics(protocol)
    base = start or datetime.now(UTC)
    participants: list[dict] = []
    for index in range(count):
        pid = f"P{index + 1:02d}"
        blocks = assign(protocol, index)
        if not blocks:
            raise ValueError(
                f"protocol {protocol.get('study', {}).get('id', '?')} "
                "has no tasks to simulate"
            )
        params = PROFILE_PARAMS[profile_for(index, profile)]
        sessions = []
        metric_rows: list[dict] = []
        t = base + timedelta(days=index)
        for b in blocks:
            sid = f"{pid}-S{b.index + 1}"
            file = f"src/{b.task_id or 'task'}.py"
            start_t = t
            t += timedelta(minutes=45)
            events = _session_events(
                rng,
                types,
                params,
                b.task_id,
                file,
                sid,
                pid,
                b.condition,
                start_t,
                "tern",
            )
            sessions.append(
                {
                    "sessionId": sid,
                    "blockIndex": b.index,
                    "taskId": b.task_id,
                    "condition": b.condition,
                    "events": events,
                }
            )
            if want_metrics:
                metric_rows.extend(
                    _session_metrics(
                        rng,
                        sid,
                        pid,
                        b.condition,
                        b.task_id,
                        start_t + timedelta(minutes=44),
                    )
                )
        participants.append(
            {
                "participantId": pid,
                "condition": blocks[0].condition,
                "sessions": sessions,
                "metricRows": metric_rows,
            }
        )
    return participants


def simulate_into(
    s,
    protocol: dict,
    study_id: str,
    count: int,
    profile: str = "mixed",
    seed: int | None = None,
    base_url: str = "http://127.0.0.1:8000",
    now: Callable[[], str] | None = None,
    start: datetime | None = None,
) -> dict:
    """
    In-process dry run: mint tokens + record blocks + store events, all through the
    production code paths (the ``db`` dependency commits).
    """
    from middleware.ingest_core import store_events, store_metric_rows

    now = now or (lambda: datetime.now(UTC).isoformat(timespec="milliseconds"))
    received = now()
    run = secrets.token_hex(3)
    participants = simulate(protocol, count, profile, seed, start=start)
    token_rows = []
    session_blocks = []
    event_rows = []
    metric_rows = []
    for i, p in enumerate(participants):
        token = secrets.token_urlsafe(32)
        token_rows.append(
            EnrollmentToken(
                id=secrets.token_hex(8),
                study_id=study_id,
                participant_id=p["participantId"],
                participant_index=i,
                condition=p["condition"],
                grain="participant",
                token=token,
                credential=token,
                expires_at=(
                    datetime.now(UTC) + timedelta(days=30)
                ).isoformat(timespec="milliseconds"),
                redeemed_at=now(),
                created_at=received,
            )
        )
        for session in p["sessions"]:
            sid = f"{session['sessionId']}-{run}"
            for e in session["events"]:
                e["session_id"] = sid
            for m in p["metricRows"]:
                if m.get("sessionId") == session["sessionId"]:
                    m["sessionId"] = sid
            session_blocks.append(
                SessionBlock(
                    session_id=sid,
                    study_id=study_id,
                    participant_id=p["participantId"],
                    block_index=session["blockIndex"],
                    task_id=session["taskId"],
                    condition=session["condition"],
                    assigned_at=received,
                )
            )
            event_rows.extend(session["events"])
        metric_rows.extend(p["metricRows"])
    s.add_all(token_rows)
    s.add_all(session_blocks)
    inserted_events = store_events(s, event_rows, received)
    inserted_metrics = store_metric_rows(s, metric_rows, received) if metric_rows else 0
    return {
        "participants": count,
        "profile": profile,
        "seed": seed,
        "run": run,
        "sessions": len(session_blocks),
        "events": inserted_events,
        "metricRows": inserted_metrics,
        "tokensMinted": len(token_rows),
    }


def run_plan_summary(protocol: dict, rows: list[dict], study_id: str) -> dict:
    """
    Run the protocol's analysis plan over ``rows`` and return a JSON-safe summary.

    This is the half of the dry run that matters. Storing synthetic events proves
    the capture path works; running the *prescribed* statistics over them proves
    the analysis plan is satisfiable before a single real participant sits down —
    which is the one thing a researcher cannot find out any other way, and the
    step they are most afraid of getting wrong.

    Deliberately not ``analysis.runner.run_plan``: that writes figures, tables and
    a stitched report to ``results/`` and prints as it goes, which is right for a
    CLI run and wrong inside a web request. Here the plan is validated, each
    satisfiable recipe is run once in-process, and only each recipe's own
    human-readable ``summary`` comes back. Figures are closed rather than
    written, so a dry run costs no disk and leaks no Matplotlib state.
    """
    import analysis.recipes  # noqa: F401 - registers the built-in recipes
    from analysis.core import REGISTRY, validate_plan
    from analysis.dataset import Dataset

    plan = protocol.get("analysisPlan") or []
    if not plan:
        return {
            "planned": 0,
            "ran": [],
            "blocked": [],
            "results": [],
            "note": (
                "This protocol has no analysis plan yet, so there was nothing to "
                "validate. Choose a design in the conversation — each one carries "
                "the statistics it requires."
            ),
        }

    dataset = Dataset(rows=rows, study_id=study_id)
    checks = validate_plan(plan, dataset)

    # One entry per (RQ, recipe) pair; a recipe named by two RQs runs once.
    rq_by_recipe: dict[str, list[str]] = {}
    for c in checks:
        rq_by_recipe.setdefault(c.recipe_id, []).append(c.rq)

    blocked = [
        {
            "recipeId": c.recipe_id,
            "rq": c.rq,
            "reason": (
                "not a registered recipe"
                if not c.known
                else "needs " + ", ".join(c.missing)
            ),
        }
        for c in checks
        if not c.ok
    ]

    # Per-recipe params ride on the plan entry, exactly as `run_plan` reads them.
    params: dict[str, dict] = {}
    for entry in plan:
        for rid in entry.get("recipes", []):
            if isinstance(rid, dict):
                params[rid["id"]] = rid.get("params", {})
            elif rid not in params:
                params[rid] = {}

    results: list[dict] = []
    ran: list[str] = []
    errors: dict[str, str] = {}
    for recipe_id in dict.fromkeys(c.recipe_id for c in checks if c.ok):
        recipe = REGISTRY[recipe_id]
        try:
            # Fresh per recipe, not merged onto whatever the previous recipe
            # left behind — `dataset` is one object reused across every
            # iteration of this loop, so an accumulating merge would leak a
            # param key set for an earlier recipe into a later one that never
            # specified it.
            dataset.meta = dict(params.get(recipe_id, {}))
            result = recipe.run(dataset)
        except Exception as exc:  # noqa: BLE001 - reported, never raised at the caller
            errors[recipe_id] = f"{type(exc).__name__}: {exc}"
            log.warning("dry-run recipe %s failed: %s", recipe_id, errors[recipe_id])
            continue
        _close_figures(result)
        ran.append(recipe_id)
        results.append(
            {
                "recipeId": recipe_id,
                "title": recipe.title or recipe_id,
                "rqs": sorted(set(rq_by_recipe.get(recipe_id, []))),
                "answers": list(recipe.answers),
                "summary": result.summary,
            }
        )

    return {
        "planned": len({c.recipe_id for c in checks}),
        "ran": ran,
        "blocked": blocked,
        "errors": errors,
        "results": results,
    }


def _close_figures(result) -> None:
    """Release a recipe's Matplotlib figures — nothing here is being written."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover - matplotlib ships with analysis
        return
    for fig in getattr(result, "figures", {}).values():
        with suppress(Exception):
            plt.close(fig)
