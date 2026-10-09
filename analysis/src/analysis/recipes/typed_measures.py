"""Score declared instruments from captured responses, never trust a client score."""

import pandas as pd
from protocol.measures import normalized_measures, score_survey, validated_responses
from protocol.versioning import version_record

from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.stats import mann_whitney, wilcoxon_paired


@recipe(
    id="typed-measures", answers=["RQ-P1"], title="Protocol-declared survey measures"
)
def run(dataset: Dataset) -> RecipeResult:
    protocol = dataset.meta.get("protocol", {})
    instruments = {
        i["id"]: i for i in protocol.get("instruments", {}).get("surveys", [])
    }
    rows = []
    for event in dataset.analysis_rows:
        p = event.get("payload") or {}
        instrument = instruments.get(p.get("instrumentId"))
        if (
            event.get("type") not in {"survey_response", "pre_task_covariate"}
            or not instrument
        ):
            continue
        if (
            p.get("instrumentVersion") != instrument["version"]
            or p.get("instrumentHash") != version_record(instrument)["sha256"]
            or not validated_responses(instrument, p.get("responses", {}))
        ):
            continue
        score = score_survey(instrument, p.get("responses", {}))
        for measure in normalized_measures(protocol):
            if (
                measure["instrument"] != instrument["id"]
                or measure["analysisRecipe"] != "typed-measures"
            ):
                continue
            for field in measure["fields"]:
                if field.endswith(".score"):
                    value = score
                else:
                    value = p.get("responses", {}).get(field.split(".responses.")[-1])
                if value is not None:
                    rows.append(
                        {
                            "participantId": event["participantId"],
                            "condition": event["condition"],
                            "sessionId": event["sessionId"],
                            "measureId": measure["id"],
                            "field": field,
                            "value": value,
                        }
                    )
    frame = pd.DataFrame(rows)
    tests = []
    if not frame.empty and len(dataset.conditions) == 2:
        for (mid, field), group in frame.groupby(["measureId", "field"]):
            a, b = protocol["conditions"]
            per = (
                group.groupby(["participantId", "condition"])["value"].mean().unstack()
            )
            if a not in per or b not in per:
                continue
            if protocol["participants"]["design"] == "within-subjects":
                pairs = per.dropna(subset=[a, b])
                if len(pairs) < 2:
                    continue
                test = wilcoxon_paired(pairs[a].tolist(), pairs[b].tolist(), (a, b))
            else:
                if per[[a, b]].notna().all(axis=1).any():
                    raise ValueError(
                        "Between-subjects typed analysis requires independent "
                        "participants"
                    )
                test = mann_whitney(
                    per[a].dropna().tolist(), per[b].dropna().tolist(), (a, b)
                )
            tests.append({"measureId": mid, "field": field, **test.row()})
    return RecipeResult(
        tables={"scores": frame, "tests": pd.DataFrame(tests)},
        summary=(
            f"{len(frame)} observed typed measure values; "
            "missing or version-mismatched responses are not scored."
        ),
        methods="Protocol item scales/reverse scoring and declared "
        "scoring rule; per-participant means, Wilcoxon for "
        "paired data or Mann-Whitney for independent cells.",
    )
