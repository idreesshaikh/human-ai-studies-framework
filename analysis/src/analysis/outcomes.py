"""Participant summaries for typed outcomes, paired analysis and pilot variance."""

import math
from collections import defaultdict

from protocol.measures import score_survey, validated_responses
from protocol.versioning import version_record


def participant_outcomes(
    rows: list[dict],
    protocol: dict,
    field: str,
    instrument_id: str | None = None,
    scale: str = "raw",
) -> dict:
    event_type, path = field.split(".", 1)
    instruments = {
        i["id"]: i for i in protocol.get("instruments", {}).get("surveys", [])
    }
    values = defaultdict(list)
    for row in rows:
        if row.get("type") != event_type or (row.get("payload") or {}).get("synthetic"):
            continue
        payload = row.get("payload") or {}
        if event_type in {"survey_response", "pre_task_covariate"}:
            inst = instruments.get(payload.get("instrumentId"))
            if (
                not inst
                or inst["id"] != instrument_id
                or payload.get("instrumentVersion") != inst["version"]
                or payload.get("instrumentHash") != version_record(inst)["sha256"]
                or not validated_responses(inst, payload.get("responses", {}))
            ):
                continue
            if path == "score":
                value = score_survey(inst, payload.get("responses", {}))
            else:
                value = payload
                for key in path.split("."):
                    value = value.get(key) if isinstance(value, dict) else None
        else:
            value = payload
            for key in path.split("."):
                value = value.get(key) if isinstance(value, dict) else None
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            continue
        if scale == "log":
            if value <= 0:
                continue
            value = math.log(value)
        values[(row.get("participantId"), row.get("condition"))].append(value)
    return {key: sum(vals) / len(vals) for key, vals in values.items() if key[0]}
