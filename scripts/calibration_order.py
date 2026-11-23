"""Print the frozen, shuffled session order for the AI-use calibration.

Prints a CSV `order,scenario,rep` shuffled with the fixed seed 20261112:
2 no-AI sessions, 2 sessions for each of 6 AI routes, 2 sessions for each of
5 benign look-alikes, and 1 session for each of 7 boundary probes, 31 in all.

`rep` counts up in session order within a scenario, so the first time a scenario
appears in the order it is rep 1.
"""

from __future__ import annotations

import csv
import random
import sys

SEED = 20261112

NO_AI = "no-ai"
AI_ROUTES = (
    "copilot-inline",
    "copilot-chat",
    "browser-paste",
    "retype",
    "cli-agent-hooks",
    "cli-agent-no-hooks",
)
BENIGN = (
    "benign-formatter",
    "benign-snippet",
    "benign-rename",
    "benign-own-paste",
    "benign-stackoverflow-paste",
)
PROBES = (
    "probe-menu-paste",
    "probe-word-accept",
    "probe-mouse-accept",
    "probe-agent-closed-file",
    "probe-agent-explain",
    "probe-format-large",
    "probe-rename-many",
)

# (scenario, repetitions), in canonical (unshuffled) order.
SESSION_PLAN: tuple[tuple[str, int], ...] = (
    (NO_AI, 2),
    *((route, 2) for route in AI_ROUTES),
    *((scenario, 2) for scenario in BENIGN),
    *((scenario, 1) for scenario in PROBES),
)
SCENARIOS: tuple[str, ...] = tuple(scenario for scenario, _ in SESSION_PLAN)
GROUP_OF: dict[str, str] = {
    NO_AI: "no AI",
    **dict.fromkeys(AI_ROUTES, "AI route"),
    **dict.fromkeys(BENIGN, "benign look-alike"),
    **dict.fromkeys(PROBES, "boundary probe"),
}


def build_order(seed: int = SEED) -> list[tuple[int, str, int]]:
    """Return `(order, scenario, rep)` for every session, shuffled by `seed`."""
    sessions = [scenario for scenario, reps in SESSION_PLAN for _ in range(reps)]
    random.Random(seed).shuffle(sessions)  # noqa: S311 - reproducible, not secret
    seen: dict[str, int] = {}
    order = []
    for position, scenario in enumerate(sessions, start=1):
        seen[scenario] = seen.get(scenario, 0) + 1
        order.append((position, scenario, seen[scenario]))
    return order


def main() -> int:
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["order", "scenario", "rep"])
    writer.writerows(build_order())
    return 0


if __name__ == "__main__":
    sys.exit(main())
