"""Built-in analysis recipes (FR-ANA-3 + the FR-ANA-5 replication demo).

Importing this package registers every built-in recipe with
``analysis.core.REGISTRY`` (via the ``@recipe`` decorator).
"""

from analysis.recipes import (
    agent_interaction_dynamics,
    ai_review_behavior,
    code_quality_by_condition,
    fatigue_by_condition,
    meyer_fragmentation,
    paste_behavior,
    stuck_episodes,
    task_outcome_by_condition,
    tlx_debrief,
    ziegler_acceptance_rate,
)

__all__ = [
    "agent_interaction_dynamics",
    "ai_review_behavior",
    "code_quality_by_condition",
    "fatigue_by_condition",
    "meyer_fragmentation",
    "paste_behavior",
    "stuck_episodes",
    "task_outcome_by_condition",
    "tlx_debrief",
    "ziegler_acceptance_rate",
]
