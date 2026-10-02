"""Connect the supported checklist outcomes to capture and analysis."""

from analysis.core import REGISTRY, validate_plan
from analysis.dataset import Dataset
from protocol.capture import producer_capabilities

from analysis import recipes as _recipes  # noqa: F401 - register built-ins

MEASURES = {
    "task completion time": (
        "task-outcome-by-condition",
        "Time to the first observed passing acceptance-test run. Run the task "
        "harness with the session start time; editor activity is not task time.",
    ),
    "solution correctness": (
        "task-outcome-by-condition",
        "Pass/fail of the supplied acceptance tests at the final run. "
        "Prepare and review the tests before participants begin.",
    ),
    "cognitive load": (
        "tlx-debrief",
        "TERN end-of-session workload ratings, scored separately on 1–7 scales. "
        "These are self-reports, not a validated NASA-TLX total.",
    ),
    "code comprehension": (
        "tlx-debrief",
        "Self-reported comprehension in the TERN debrief (1–7). "
        "Objective comprehension requires a separate assessment.",
    ),
    "fatigue": (
        "fatigue-by-condition",
        "TERN fatigue ratings (1–7); participants must answer the probes.",
    ),
}


def configure_measures(protocol: dict, measures: list[str]) -> None:
    """Configure only a checklist template; ordinary protocols stay untouched."""
    unknown = sorted(set(measures) - MEASURES.keys())
    if unknown:
        raise ValueError("Unsupported checklist outcomes: " + ", ".join(unknown))
    recipe_ids = list(dict.fromkeys(MEASURES[name][0] for name in measures))
    rq = protocol["researchQuestions"][0]
    protocol["researchQuestions"] = [rq]
    protocol["analysisPlan"] = [{"rq": rq["id"], "recipes": recipe_ids}]
    protocol["measures"] = list(measures)
    instruments = protocol["instruments"]
    instruments.pop("metrics", None)
    if "task-outcome-by-condition" in recipe_ids:
        instruments["taskHarness"] = {"enabled": True, "required": True}


def measurement_report(protocol: dict, rows: list[dict]) -> dict:
    """Report configuration and observed data separately; never certify a study."""
    producers = producer_capabilities(protocol)
    dataset = Dataset(rows, study_id=protocol["study"]["id"])
    checks = validate_plan(protocol.get("analysisPlan", []), dataset)
    planned = []
    for check in checks:
        recipe = REGISTRY.get(check.recipe_id)
        requirements = []
        if recipe:
            for event in sorted(recipe.requires.events):
                if event == "task_outcome":
                    producer = "task-harness"
                elif event in {"agent_turn", "tool_call", "agent_session_meta"}:
                    producer = "agent-capture"
                elif event in {
                    "code_evolution",
                    "reliance_loop",
                    "edit_burst_annotation",
                }:
                    producer = "agent-derived"
                elif event == "workspace_snapshot":
                    producer = "workspace-snapshot"
                else:
                    producer = "tern"
                requirements.append(_requirement(event, producer, producers))
            for metric in sorted(recipe.requires.metrics):
                requirements.append(_requirement(metric, "metrics", producers))
        planned.append(
            {
                "rq": check.rq,
                "recipeId": check.recipe_id,
                "title": recipe.title if recipe else check.recipe_id,
                "known": check.known,
                "requirements": requirements,
                "missingData": list(check.missing),
                "dataPresent": check.ok,
            }
        )
    session_rows: dict[str, list[dict]] = {}
    for row in rows:
        session_rows.setdefault(row.get("sessionId", ""), []).append(row)
    sessions = []
    for sid, records in sorted(session_rows.items()):
        session_checks = validate_plan(
            protocol.get("analysisPlan", []), Dataset(records)
        )
        sessions.append(
            {
                "sessionId": sid,
                "synthetic": any(
                    r.get("payload", {}).get("synthetic") is True for r in records
                ),
                "missingData": [c.describe() for c in session_checks if not c.ok],
            }
        )
    measures = [
        {"name": name, "recipeId": MEASURES[name][0], "guidance": MEASURES[name][1]}
        if name in MEASURES
        else {
            "name": name,
            "recipeId": None,
            "guidance": "Custom measure: review its instrument and analysis mapping.",
        }
        for name in protocol.get("measures", [])
        if isinstance(name, str)
    ]
    return {"measures": measures, "recipes": planned, "sessions": sessions}


def _requirement(name: str, producer: str, producers: dict) -> dict:
    info = producers[producer]
    return {
        "name": name,
        "producer": producer,
        "state": info["state"],
        "guidance": info["reason"],
    }
