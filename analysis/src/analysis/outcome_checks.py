"""Inspect declared outcome inputs without scoring effects or changing records."""

import math
from collections import Counter, defaultdict

from protocol.assignment import tasks_of
from protocol.capture import (
    KNOWN_EVENT_SCHEMA_VERSIONS,
    capture_config_version,
    producer_capabilities,
)
from protocol.measures import (
    normalized_measures,
    score_survey,
    score_survey_scales,
    validated_responses,
)
from protocol.versioning import content_hash, version_record

LIMITATIONS = [
    "Coverage concerns observed sessions, including pilots, not planned recruitment.",
    "Observed inputs do not establish construct validity or appropriate analysis.",
    "Pair coverage does not check period, carryover, or other model assumptions.",
    (
        "A task that never passes needs a non-completion/censoring "
        "decision, not zero time."
    ),
]


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _contract(protocol, measure):
    fields = measure.get("fields") or []
    instrument = measure.get("instrument")
    recipe = measure.get("analysisRecipe")
    if not fields or not all(isinstance(f, str) for f in fields):
        return None, "No typed outcome fields are declared."
    if instrument == "taskHarness":
        known = {"task_outcome.firstGreenMs", "task_outcome.passed"}
        if not set(fields) <= known:
            return None, "A field is outside the built-in task harness contract."
        recipes = {"task-outcome-by-condition"}
        if fields == ["task_outcome.firstGreenMs"]:
            recipes.add(
                "paired-nonparametric"
                if protocol.get("participants", {}).get("design") == "within-subjects"
                else "two-group-nonparametric"
            )
        if (
            "task_outcome.passed" in fields
            and protocol.get("participants", {}).get("design") == "within-subjects"
        ):
            return None, "Paired pass/fail analysis needs a separate analysis review."
        if fields == ["task_outcome.passed"]:
            recipes.add("two-proportion")
        if recipe not in recipes:
            return None, "The declared analysis recipe is not covered by this check."
        return ("task-harness", "task_outcome", None), None
    survey = next(
        (
            i
            for i in protocol.get("instruments", {}).get("surveys", [])
            if i["id"] == instrument
        ),
        None,
    )
    if not survey or recipe != "typed-measures":
        return None, "This instrument/recipe needs a custom outcome check."
    # A pre-task score is a treatment-independent adjustment input, not a
    # repeated outcome to review for condition coverage.
    if survey.get("timing") == "pre-task" or any(
        field.startswith("pre_task_covariate.") for field in fields
    ):
        return None, "Baseline survey inputs are covariates, not outcome measures."
    event = "survey_response"
    known = {f"{event}.responses.{i['id']}" for i in survey["items"]}
    if survey.get("scoring") not in {"none", "scales"}:
        known.add(f"{event}.score")
    known.update(
        f"{event}.scoreGroups.{group['id']}" for group in survey.get("scales", [])
    )
    if not set(fields) <= known:
        return None, "A field or score is not defined by the declared survey."
    return ("tern", event, survey), None


def _input_problem(row, measure, survey):
    payload = row.get("payload") or {}
    if (
        type(row.get("schemaVersion")) is not int
        or row["schemaVersion"] not in KNOWN_EVENT_SCHEMA_VERSIONS
    ):
        return "schema", "An event uses an unsupported schema version."
    if survey:
        if (
            payload.get("instrumentVersion") != survey["version"]
            or payload.get("instrumentHash") != version_record(survey)["sha256"]
        ):
            return "survey-version", "Survey version or content hash does not match."
        responses = payload.get("responses")
        if (
            not isinstance(responses, dict)
            or not all(_number(responses.get(i["id"])) for i in survey["items"])
            or not validated_responses(survey, responses)
        ):
            return (
                "survey-response",
                "Survey items are missing, out of scale, or invalid.",
            )
        if (
            any(f.endswith(".score") for f in measure["fields"])
            and score_survey(survey, payload["responses"]) is None
        ):
            return "survey-score", "The declared survey cannot produce a score."
        if any(".scoreGroups." in f for f in measure["fields"]):
            scores = score_survey_scales(survey, payload["responses"])
            groups = {f.split(".scoreGroups.", 1)[1] for f in measure["fields"]}
            if groups - set(scores):
                return "survey-score", "The declared survey scale score is unavailable."
        return None
    passed, total, failed = (payload.get(k) for k in ("passed", "total", "failed"))
    if (
        type(passed) is not bool
        or type(total) is not int
        or total <= 0
        or type(failed) is not int
        or not 0 <= failed <= total
        or passed != (failed == 0)
    ):
        return "test-result", "No coherent, nonempty test run was recorded."
    if "task_outcome.firstGreenMs" in measure["fields"]:
        if not passed:
            return (
                "no-passing-run",
                "This run did not pass; first-green time is not observed.",
            )
        value = payload.get("firstGreenMs")
        if not _number(value) or value < 0:
            return (
                "first-green",
                "A passing run lacks a finite, nonnegative first-green time.",
            )
    return None


def _unit_problem(rows, protocol, source):
    identities = {
        (r.get("participantId"), r.get("condition"), r.get("taskId")) for r in rows
    }
    if len(identities) != 1:
        return (
            "identity",
            (
                "A session contains conflicting participant, condition, or "
                "task identities."
            ),
        )
    participant, condition, task = next(iter(identities))
    tasks = {t["id"]: t for t in tasks_of(protocol)}
    if (
        not participant
        or condition not in protocol.get("conditions", [])
        or task not in tasks
        or condition not in (tasks[task].get("conditions") or [condition])
    ):
        return (
            "identity",
            "A session lacks valid attribution to a declared condition and task.",
        )
    if any(set(r.get("flags") or []) - {"pilot"} for r in rows):
        return (
            "integrity",
            "Session integrity flags need review before counting its inputs.",
        )
    if any(r.get("inclusionDecision") == "exclude" for r in rows):
        return "excluded", "The researcher excluded this session."
    sequences = [r.get("seq") for r in rows if r.get("source") == source]
    if sequences and (
        any(type(n) is not int or n < 0 for n in sequences)
        or len(set(sequences)) != len(sequences)
        or any(n != i for i, n in enumerate(sorted(sequences)))
    ):
        return (
            "sequence",
            (
                "The required producer has missing, duplicate, or invalid "
                "sequence numbers."
            ),
        )
    return None


def check_outcome_capture(
    protocol: dict, rows: list[dict], *, include_synthetic=False
) -> dict:
    """Return a deterministic, bounded report for supported observed input contracts."""
    synthetic = {
        r.get("sessionId") for r in rows if (r.get("payload") or {}).get("synthetic")
    }
    groups = defaultdict(list)
    for row in rows:
        if not include_synthetic and row.get("sessionId") in synthetic:
            continue
        groups[row.get("sessionId") or ""].append(row)
    conditions = protocol.get("conditions", [])
    producers = producer_capabilities(protocol)
    results = []
    for measure in normalized_measures(protocol):
        result = {
            "measureId": measure.get("id"),
            "outcome": measure.get("construct"),
            "instrument": measure.get("instrument"),
            "fields": list(measure.get("fields", [])),
            "recipe": measure.get("analysisRecipe"),
            "checkedUnits": len(groups),
            "observedUnits": 0,
            "participantsByCondition": dict.fromkeys(conditions, 0),
            "pairedParticipants": None,
            "issues": [],
            "evidence": [],
        }
        contract, reason = _contract(protocol, measure)
        if contract is None:
            result.update(status="unverified", observedUnits=None)
            result["issues"] = [
                {
                    "code": "unverified-contract",
                    "message": reason,
                    "action": "Review this mapping or supply a custom check.",
                    "units": 0,
                    "sessionIds": [],
                }
            ]
            results.append(result)
            continue
        source, event_type, survey = contract
        result["producer"] = source
        result["producerState"] = producers[source]["state"]
        issues = {}

        def issue(code, message, sid=None, records=issues):
            entry = records.setdefault(
                code,
                {
                    "code": code,
                    "message": message,
                    "action": _ACTIONS[code],
                    "sessions": set(),
                },
            )
            if sid is not None:
                entry["sessions"].add(sid)

        configured = producers[source]["state"] in {"enabled", "external-required"}
        if not configured:
            issue("producer-config", "The required producer is absent or disabled.")
        coverage = {c: set() for c in conditions}
        for sid, unit in sorted(groups.items()):
            problem = _unit_problem(unit, protocol, source)
            if not sid:
                problem = ("identity", "Events lack a session identity.")
            if problem:
                issue(*problem, sid)
                continue
            candidates = [
                r
                for r in unit
                if r.get("type") == event_type
                and r.get("source") == source
                and (
                    not survey
                    or (r.get("payload") or {}).get("instrumentId") == survey["id"]
                )
            ]
            if not candidates:
                issue(
                    "missing-input",
                    "No event from the required instrument was observed.",
                    sid,
                )
                continue
            valid = []
            failures = []
            for row in candidates:
                problem = _input_problem(row, measure, survey)
                if problem:
                    failures.append(problem)
                else:
                    valid.append(row)
            # Failed intermediate test runs are expected before a first green.
            for problem in failures:
                if problem[0] != "no-passing-run" or not valid:
                    issue(*problem, sid)
            if valid and configured:
                result["observedUnits"] += 1
                row = valid[0]
                coverage[row["condition"]].add(row["participantId"])
                if len(result["evidence"]) < 5:
                    result["evidence"].append(
                        {
                            k: row.get(k)
                            for k in ("sessionId", "source", "seq", "schemaVersion")
                        }
                    )
        result["participantsByCondition"] = {c: len(ids) for c, ids in coverage.items()}
        if groups and any(not ids for ids in coverage.values()):
            issue(
                "condition-coverage",
                "At least one declared condition has no observed outcome inputs.",
            )
        if len(conditions) == 2:
            overlap = len(set.intersection(*coverage.values()))
            if protocol.get("participants", {}).get("design") == "within-subjects":
                result["pairedParticipants"] = overlap
                if groups and not overlap:
                    issue(
                        "pair-coverage",
                        "No participant has observed inputs in both conditions.",
                    )
            elif overlap:
                issue(
                    "independence",
                    "A participant appears in both between-subjects conditions.",
                )
        result["issues"] = [
            {k: v for k, v in entry.items() if k != "sessions"}
            | {
                "units": len(entry["sessions"]),
                "sessionIds": sorted(entry["sessions"])[:5],
            }
            for entry in issues.values()
        ]
        result["status"] = (
            "configuration"
            if not configured
            else "not-observed"
            if not groups
            else "missing"
            if not result["observedUnits"]
            else "incomplete"
            if result["observedUnits"] < len(groups)
            else "review"
            if issues
            else "observed"
        )
        results.append(result)
    return {
        "reportVersion": 1,
        "protocolHash": content_hash(protocol),
        "dataHash": content_hash(rows),
        "captureConfigVersion": capture_config_version(protocol),
        "synthetic": bool(include_synthetic and synthetic),
        "scope": "Observed sessions, including pilots. Records are unchanged.",
        "sessionUnits": len(groups),
        "outcomes": results,
        "summary": dict(Counter(r["status"] for r in results)),
        "limitations": list(LIMITATIONS),
    }


_ACTIONS = {
    "producer-config": "Configure and run this producer, then check again.",
    "identity": "Check session attribution against the protocol.",
    "integrity": "Inspect the flags and resolve capture failures.",
    "excluded": "Review the recorded exclusion; this report does not reverse it.",
    "sequence": "Recover missing events or investigate producer sequence identity.",
    "missing-input": "Run the declared instrument in a rehearsal and verify delivery.",
    "schema": "Use a supported event schema and review ingestion flags.",
    "survey-version": "Use the declared version and hash; retain the response.",
    "survey-response": "Check completion, scales, and the response mapping.",
    "survey-score": "Review the declared scoring rule and required responses.",
    "test-result": "Verify the harness ran tests and reported counts.",
    "no-passing-run": "Retain non-completion; review censoring, not zero time.",
    "first-green": "Emit firstGreenMs in milliseconds on a passing run.",
    "condition-coverage": "Rehearse every condition; retain missing measurements.",
    "pair-coverage": "Check each participant across both conditions.",
    "independence": "Review assignment and participant independence.",
}
