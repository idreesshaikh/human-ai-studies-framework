"""Synthetic dataset builder with *constructed known answers* used by the
runner tests: every participant reports fatigue exactly one step class
higher unassisted (distinct paired differences -0.5, -1.0, -1.5, -2.0 ->
exact Wilcoxon two-sided p = 0.125, rank-biserial r = -1.0), and every
ai-assisted session shows two suggestions and accepts one (acceptance
rate = 0.5, the Ziegler et al. metric)."""

from __future__ import annotations

PARTICIPANTS = ["P01", "P02", "P03", "P04"]
#: (ai-assisted response pair, unassisted response pair) per participant -
#: paired mean differences: -0.5, -1.0, -1.5, -2.0 (distinct, all negative).
FATIGUE = {
    "P01": ((2, 2), (2, 3)),
    "P02": ((2, 3), (3, 4)),
    "P03": ((3, 3), (4, 5)),
    "P04": ((2, 4), (5, 5)),
}
TLX = {  # mentalDemand per (ai, unassisted)
    "P01": (9, 11),
    "P02": (10, 13),
    "P03": (11, 12),
    "P04": (8, 12),
}


def synthetic_rows() -> list[dict]:
    rows: list[dict] = []

    def ev(session, participant, condition, seq, minute, type_, payload):
        rows.append(
            {
                "source": "cognitive-overlay",
                "ts": f"2026-07-11T{10 + int(minute) // 60:02d}:"
                f"{int(minute) % 60:02d}:00.000Z",
                "sessionId": session,
                "participantId": participant,
                "condition": condition,
                "type": type_,
                "seq": seq,
                "flags": [],
                "payload": payload,
            }
        )

    def make_emitter(session, participant, condition):
        seq = 0

        def emit(minute, type_, payload):
            nonlocal seq
            ev(session, participant, condition, seq, minute, type_, payload)
            seq += 1

        return emit

    # ai-assisted sessions first so dataset.conditions order is stable.
    for cond_i, condition in enumerate(["ai-assisted", "unassisted"]):
        for participant in PARTICIPANTS:
            session = f"S-{participant}-{condition[:2]}"
            emit = make_emitter(session, participant, condition)

            emit(0, "session_start", {"plannedDurationMinutes": 60})
            f1, f2 = FATIGUE[participant][cond_i]
            emit(15, "fatigue_response", {"score": f1, "latencyMs": 3000})
            emit(40, "fatigue_response", {"score": f2, "latencyMs": 3500})
            if condition == "ai-assisted":
                emit(10, "ai_suggestion", {"suggestionId": "sg1", "action": "shown"})
                emit(
                    10.5,
                    "ai_suggestion",
                    {
                        "suggestionId": "sg1",
                        "action": "accepted",
                        "visibleMs": 2000,
                        "charCount": 120,
                    },
                )
                emit(30, "ai_suggestion", {"suggestionId": "sg2", "action": "shown"})
                emit(
                    30.5,
                    "ai_suggestion",
                    {
                        "suggestionId": "sg2",
                        "action": "dismissed",
                        "visibleMs": 9000,
                    },
                )
            emit(
                58,
                "end_survey",
                {"mentalDemand": TLX[participant][cond_i], "effort": 10 + cond_i},
            )
            emit(60, "session_end", {"reason": "completed"})

    return rows
