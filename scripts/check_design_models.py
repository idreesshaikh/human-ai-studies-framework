"""Bounded live compatibility comparison; not an expert study-design benchmark."""

import argparse
import json
import urllib.error
from datetime import UTC, datetime
from time import perf_counter

from evaluate_research import save
from middleware.assistant import _post_json, make_design_client, model_name
from middleware.design_llm import propose_turn

BRIEFS = (
    "Compare AI-assisted and unassisted Python debugging for novice developers. "
    "Measure task completion time in a 45-minute session.",
    "Experienced developers repair two equivalent Python bugs, once with AI and "
    "once without. How should we handle order and carryover?",
    "We only collect timer metadata. Can we claim that generated code is correct? "
    "Identify the missing measurement, without inventing evidence.",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=[model_name(design=True)])
    parser.add_argument(
        "--live",
        action="store_true",
        help="Explicitly permit synthetic prompts to the configured model route",
    )
    parser.add_argument("--output", default=".research-artifacts/design-models.json")
    args = parser.parse_args()
    if not args.live or make_design_client() is None:
        parser.error("Use --live with a configured model route; prompts are synthetic")
    results = []
    for selected in dict.fromkeys(args.models):
        observations = {}

        def post(url, body, headers, observations=observations):
            try:
                response = _post_json(url, body, headers)
            except urllib.error.HTTPError as error:
                observations["httpStatus"] = error.code
                raise
            observations.update(
                usage=response.get("usage"), resolvedModel=response.get("model")
            )
            return response

        client = make_design_client()
        client.post = post
        client.model = selected
        for index, brief in enumerate(BRIEFS):
            observations.clear()
            started = perf_counter()
            turn = propose_turn(client, brief, [], [], [])
            results.append(
                {
                    "requestedModel": selected,
                    "brief": index,
                    "latencyMs": round((perf_counter() - started) * 1000, 2),
                    "usableParsedTurn": turn is not None,
                    "acceptedPatchCount": sum(bool(move.patch) for move in turn.moves)
                    if turn
                    else 0,
                    "costUsd": None,
                    **observations,
                }
            )
            if observations.get("httpStatus") in {401, 403, 429}:
                break  # Do not keep hammering an inaccessible model.
    report = {
        "checkedAt": datetime.now(UTC).isoformat(),
        "maxOutputTokens": 1200,
        "briefs": list(BRIEFS),
        "results": results,
        "decision": (
            "Retain the configured working route pending "
            "expert-reviewed quality comparison."
        ),
        "limits": (
            "Synthetic compatibility only. Parsing is not methodological quality. "
            "Alias versions may change; freeze returned versions for research. "
            "Missing cost is unknown, not zero. "
            "No classifier or model is silently promoted."
        ),
    }
    save(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
