"""Recipe contract and registry (FR-ANA-1/2, roadmap/07-analysis-recipes.md).

A *recipe* is a pluggable analysis module that consumes the unified study
dataset and emits tables, figures, a plain-language summary, and the exact
statistical procedure text for a methods section.

Each recipe declares:

- ``id`` - kebab-case identifier (also its output directory name),
- ``answers`` - the research-question ids it answers (e.g. ``"RQ-P1"``),
- ``requires`` - the event types and/or metric columns it needs,
- ``run(dataset) -> RecipeResult``.

The ``requires`` check is requirements validation (FR-ANA-2, RQ-F2): a
protocol's analysis plan is validated against the dataset *before* recipes
run, and a recipe whose data is missing fails loudly at plan-validation
time - naming the missing event type or metric column - instead of
producing an empty or misleading result at analysis time.

Statistical honesty (NFR-8): every recipe's summary must report the exact
test name, an effect size, and per-cell n - never a bare p-value - and must
frame small samples as hypothesis-generating (``analysis.stats`` does this
by construction).
"""

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
        out = [
            f"event type '{t}'"
            for t in sorted(self.events - dataset.event_types)
        ]
        out += [
            f"metric column '{c}'"
            for c in sorted(self.metrics - dataset.metric_columns)
        ]
        return out


@dataclass(frozen=True)
class RecipeResult:
    """What a recipe emits.

    tables: named DataFrames (name -> table; names become CSV filenames).
    figures: named matplotlib Figures (name -> figure; saved as PNG + SVG).
    summary: plain-language findings, honest about n and test used (NFR-8).
    methods: exact statistical procedure text for the paper's methods section.
    """

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
    #: One-line description for report headers and `analysis list`.
    title: str = ""


#: Global recipe registry, populated by the ``@recipe`` decorator at import
#: time (importing ``analysis.recipes`` registers all built-in recipes).
REGISTRY: dict[str, Recipe] = {}


def recipe(
    id: str,  # noqa: A002 - mirrors the contract field name
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


# --------------------------------------------------------- plan validation


@dataclass(frozen=True)
class PlanCheck:
    """Validation outcome for one (RQ, recipe) pair of the analysis plan."""

    rq: str
    recipe_id: str
    #: False when the plan names a recipe the registry doesn't know.
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


def validate_plan(
    analysis_plan: Sequence[dict], dataset: Dataset
) -> list[PlanCheck]:
    """Check every recipe the protocol's analysis plan names (FR-ANA-2).

    ``analysis_plan`` is the protocol's ``analysisPlan`` list
    (``[{rq, recipes: [...]}]``). Returns one check per (RQ, recipe) pair;
    callers fail loudly on any ``not ok`` entry *before* running anything.
    """
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
