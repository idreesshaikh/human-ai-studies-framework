"""Supported measurement choices; suggestions are proposals, never calibrated claims."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from importlib import resources

from protocol.measures import shipped_instruments

CATALOG_VERSION = "1.0"


def measure_catalog() -> list[dict]:
    return json.loads(
        resources.files("protocol")
        .joinpath("schema/measure-catalog.json")
        .read_text("utf-8")
    )


def catalog_digest() -> str:
    return hashlib.sha256(
        json.dumps(measure_catalog(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def catalog_entry(ident: str) -> dict | None:
    return next((row for row in measure_catalog() if row["id"] == ident), None)


def _words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def suggest_measures(text: str, design: str, *, top_k: int = 3) -> dict:
    phrase = _words(text)
    suggestions = []
    for row in measure_catalog():
        if row["id"] == "E1" and any(
            f" {cue} " in f" {phrase} "
            for cue in ("perceived", "perception", "felt", "self reported")
        ):
            continue
        aliases = [_words(alias) for alias in [row["construct"], *row["aliases"]]]
        matches = [
            alias for alias in aliases if alias and f" {alias} " in f" {phrase} "
        ]
        if not matches:
            continue
        match = max(matches, key=len)
        suggestions.append(
            {
                **row,
                "matchedAlias": match,
                "designCompatible": row["recipeByDesign"].get(design) is not None,
            }
        )
    suggestions.sort(key=lambda row: (-len(row["matchedAlias"]), row["id"]))
    suggestions = suggestions[:top_k]
    return {
        "catalogVersion": CATALOG_VERSION,
        "catalogDigest": catalog_digest(),
        "method": "catalog-aliases",
        "calibrated": False,
        "abstain": not any(row["designCompatible"] for row in suggestions),
        "suggestions": suggestions,
    }


def apply_catalog_measures(protocol: dict) -> list[str]:
    """Resolve confirmed catalog ids atomically, preserving typed declarations."""
    if not any(
        isinstance(row, dict) and "catalogId" in row
        for row in protocol.get("measures", [])
    ):
        return []
    draft = copy.deepcopy(protocol)
    design = draft.get("participants", {}).get("design")
    catalog = measure_catalog()
    by_id = {row["id"]: row for row in catalog}
    surveys = {row["id"]: row for row in shipped_instruments()}
    outcomes = []
    problems = []
    instruments = draft.setdefault("instruments", {})
    for value in draft["measures"]:
        if isinstance(value, dict) and "catalogId" not in value:
            outcomes.append(value)
            continue
        if isinstance(value, str):
            entry = next(
                (
                    row
                    for row in catalog
                    if _words(value)
                    in [_words(row["construct"]), *map(_words, row["aliases"])]
                ),
                None,
            )
        else:
            ident = value.get("catalogId") if isinstance(value, dict) else None
            entry = by_id.get(ident) if isinstance(ident, str) else None
        if entry is None:
            problems.append(
                "An outcome has no supported capture mapping; "
                "choose a catalog measure or describe its instrument."
            )
            continue
        recipe = entry["recipeByDesign"].get(design)
        if recipe is None and entry["id"] != "S10":
            problems.append(
                f"{entry['construct']} has no supported analysis for this design."
            )
            continue
        instrument = entry["instrument"]
        if instruments.get(instrument, {}).get("enabled") is False:
            problems.append(
                f"{entry['construct']} requires {instrument}, which is disabled."
            )
            continue
        if instrument in surveys:
            declared = instruments.setdefault("surveys", [])
            if not any(row["id"] == instrument for row in declared):
                declared.append(copy.deepcopy(surveys[instrument]))
        elif instrument == "taskHarness":
            instruments.setdefault(instrument, {"enabled": True})
        elif instrument == "metrics":
            instruments.setdefault(
                instrument,
                {
                    "enabled": True,
                    "cadence": "end-of-session",
                    "metricSet": "code-quality-5",
                },
            )
        elif instrument == "agentCapture":
            instruments.setdefault(
                instrument,
                {
                    "enabled": True,
                    "adapter": "generic-json",
                    "contentPolicy": "metadata-only",
                },
            )
        elif instrument == "tern" and "tern" not in instruments:
            problems.append(
                "Editor outcomes require a declared TERN capture configuration."
            )
            continue
        if entry["id"] == "S10":
            draft["covariate"] = {
                "instrument": instrument,
                "field": "pre_task_covariate.score",
                "timing": "pre-task",
            }
            continue
        measure = {
            "id": entry["id"],
            "construct": entry["construct"],
            "instrument": instrument,
            "fields": entry["fields"],
            "analysisRecipe": recipe,
            "version": CATALOG_VERSION,
        }
        if not any(row.get("id") == measure["id"] for row in outcomes):
            outcomes.append(measure)
        plan = draft.setdefault("analysisPlan", [])
        rq = next(iter(draft.get("researchQuestions", [])), {}).get("id", "RQ-1")
        entry_plan = next((row for row in plan if row["rq"] == rq), None)
        if entry_plan is None:
            entry_plan = {"rq": rq, "recipes": []}
            plan.append(entry_plan)
        if recipe not in entry_plan["recipes"]:
            entry_plan["recipes"].append(recipe)
    if problems:
        return list(dict.fromkeys(problems))
    draft.update(
        protocolVersion=6, measureSetVersion=CATALOG_VERSION, measures=outcomes
    )
    protocol.clear()
    protocol.update(draft)
    return []
