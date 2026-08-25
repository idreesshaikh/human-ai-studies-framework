import analysis.recipes  # noqa: F401 - register built-in recipes
from analysis.core import REGISTRY
from analysis.dataset import Dataset


def test_paired_recipe_reads_task_outcome_events():
    rows = []
    values = {
        "P01": {"ai-assisted": 900, "unassisted": 1200},
        "P02": {"ai-assisted": 1100, "unassisted": 1500},
        "P03": {"ai-assisted": 1300, "unassisted": 1800},
    }
    seq = 0
    for participant, by_condition in values.items():
        for condition, first_green_ms in by_condition.items():
            rows.append(
                {
                    "sessionId": f"s-{participant}-{condition}",
                    "participantId": participant,
                    "condition": condition,
                    "ts": f"2026-08-24T19:00:{seq:02d}.000Z",
                    "type": "task_outcome",
                    "seq": 0,
                    "source": "tern",
                    "flags": [],
                    "payload": {"passed": True, "firstGreenMs": first_green_ms},
                }
            )
            seq += 1

    result = REGISTRY["paired-nonparametric"].run(Dataset(rows))

    assert "test" in result.tables
    assert "Wilcoxon" in result.summary
