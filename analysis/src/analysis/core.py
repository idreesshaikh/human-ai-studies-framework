"""Recipe contract and registry (FR-ANA-1/2)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

import pandas as pd
from matplotlib.figure import Figure

from analysis.dataset import Dataset

RunFn = Callable[[Dataset], "RecipeResult"]


@dataclass(frozen=True)
class Requires:
    """A recipe's declared data requirements (FR-ANA-2)."""

    events: frozenset[str] = frozenset()
    metrics: frozenset[str] = frozenset()

    def missing(self, dataset: Dataset) -> list[str]:
        """Human-readable list of unmet requirements, empty when satisfied."""
        out = [f"event type '{t}'" for t in sorted(self.events - dataset.event_types)]
        out += [
            f"metric column '{c}'"
            for c in sorted(self.metrics - dataset.metric_columns)
        ]
        return out


@dataclass(frozen=True)
class RecipeResult:
    """What a recipe emits."""

    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    figures: dict[str, Figure] = field(default_factory=dict)
    summary: str = ""
    methods: str = ""


@dataclass(frozen=True)
class Recipe:
    """A registered analysis recipe (see module docstring for the contract)."""

    id: str
    answers: tuple[str, ...]
    requires: Requires
    run: RunFn
    title: str = ""


REGISTRY: dict[str, Recipe] = {}


def recipe(
    id: str,
    answers: Sequence[str],
    requires_events: Iterable[str] = (),
    requires_metrics: Iterable[str] = (),
    title: str = "",
) -> Callable[[RunFn], RunFn]:
    """Decorator registering a ``run`` function as a Recipe."""

    def register(fn: RunFn) -> RunFn:
        if id in REGISTRY:
            raise ValueError(f"duplicate recipe id: {id!r}")
        REGISTRY[id] = Recipe(
            id=id,
            answers=tuple(answers),
            requires=Requires(
                events=frozenset(requires_events),
                metrics=frozenset(requires_metrics),
            ),
            run=fn,
            title=title,
        )
        return fn

    return register


@dataclass(frozen=True)
class PlanCheck:
    """Validation outcome for one (RQ, recipe) pair of the analysis plan."""

    rq: str
    recipe_id: str
    known: bool
    missing: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.known and not self.missing

    def describe(self) -> str:
        if not self.known:
            return (
                f"{self.recipe_id} ({self.rq}): UNKNOWN RECIPE - the analysis "
                "plan names a recipe that is not registered"
            )
        if self.missing:
            return (
                f"{self.recipe_id} ({self.rq}): MISSING DATA - requires "
                + ", ".join(self.missing)
            )
        return f"{self.recipe_id} ({self.rq}): ok"


def validate_plan(analysis_plan: Sequence[dict], dataset: Dataset) -> list[PlanCheck]:
    """Check every recipe the protocol's analysis plan names (FR-ANA-2)."""
    checks = []
    for entry in analysis_plan:
        for rid in entry.get("recipes", []):
            rec = REGISTRY.get(rid)
            checks.append(
                PlanCheck(
                    rq=entry["rq"],
                    recipe_id=rid,
                    known=rec is not None,
                    missing=tuple(rec.requires.missing(dataset)) if rec else (),
                )
            )
    return checks
