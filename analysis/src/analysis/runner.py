"""Plan-driven analysis runner (FR-ANA-4).

Executes exactly the recipes the protocol's analysis plan names - results
are traceable to research questions by construction - and writes

    results/<study>/<recipe>/   tables (CSV), figures (PNG + SVG), summary.md
    results/<study>/report.md   per-RQ stitched report

Plan validation runs first and fails loudly (FR-ANA-2): every unsatisfied
requirement is printed and lands in the report's validation section naming
the missing event type / metric column. Recipe runs are best-effort
recorded to the middleware (`POST /studies/{id}/recipe-runs`) so the
platform's un-run-recipe cards clear themselves; an offline middleware
never blocks an analysis (NFR-1 discipline applies to researcher tools
too).
"""

from __future__ import annotations

import json
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib.pyplot as plt

from analysis.core import REGISTRY, PlanCheck, RecipeResult, validate_plan
from analysis.dataset import Dataset


@dataclass
class RunOutcome:
    """What one `analysis run` produced."""

    study_id: str
    out_dir: Path
    executed: list[str] = field(default_factory=list)
    failed_validation: list[PlanCheck] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.failed_validation and not self.errors


def _write_recipe_output(
    out: Path, rid: str, result: RecipeResult
) -> tuple[list[str], list[str]]:
    """Write one recipe's tables/figures/summary; returns their filenames."""
    rdir = out / rid
    rdir.mkdir(parents=True, exist_ok=True)
    tables = []
    for name, df in result.tables.items():
        df.to_csv(rdir / f"{name}.csv", index=False)
        tables.append(f"{name}.csv")
    figures = []
    for name, fig in result.figures.items():
        for ext in ("png", "svg"):
            fig.savefig(
                rdir / f"{name}.{ext}",
                dpi=150,
                facecolor=fig.get_facecolor(),
                bbox_inches="tight",
            )
        figures.append(f"{name}.png")
        plt.close(fig)
    (rdir / "summary.md").write_text(
        f"# {rid}\n\n{result.summary}\n\n## Methods\n\n{result.methods}\n\n"
        "## Files\n\n"
        + "".join(f"- `{t}`\n" for t in tables)
        + "".join(f"- `{f}` (+ .svg)\n" for f in figures)
    )
    return tables, figures


def _record_runs(server: str, study_id: str, runs: list[dict]) -> bool:
    """Best-effort: tell the middleware which recipes ran (FR-DASH-7)."""
    try:
        for run in runs:
            req = urllib.request.Request(
                f"{server.rstrip('/')}/studies/{study_id}/recipe-runs",
                data=json.dumps(run).encode(),
                headers={"content-type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        return True
    except OSError:
        return False


def _record_findings(server: str, findings: list[dict]) -> None:
    """Best-effort: log recipe requires-failures to the operational-findings
    log (FR-META-1) so they surface as task-board cards and feed the
    retrospective. An offline middleware never blocks the analysis."""
    try:
        for finding in findings:
            req = urllib.request.Request(
                f"{server.rstrip('/')}/findings",
                data=json.dumps(finding).encode(),
                headers={"content-type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
    except OSError:
        pass


def run_plan(
    protocol: dict,
    dataset: Dataset,
    study_id: str,
    out_root: Path = Path("results"),
    server: str | None = None,
) -> RunOutcome:
    """Validate the protocol's analysis plan against the dataset, run every
    satisfiable recipe once, and stitch the per-RQ report."""
    plan = protocol.get("analysisPlan", [])
    rq_text = {
        rq["id"]: rq.get("text", "") for rq in protocol.get("researchQuestions", [])
    }
    checks = validate_plan(plan, dataset)
    outcome = RunOutcome(study_id=study_id, out_dir=out_root / study_id)
    outcome.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"plan validation ({len(checks)} entries):")
    for c in checks:
        marker = "ok " if c.ok else "FAIL"
        print(f"  [{marker}] {c.describe()}")
        if not c.ok:
            outcome.failed_validation.append(c)

    # Run each satisfiable recipe once, even when several RQs name it.
    runnable = []
    seen = set()
    for c in checks:
        if c.ok and c.recipe_id not in seen:
            seen.add(c.recipe_id)
            runnable.append(REGISTRY[c.recipe_id])

    # Build per-recipe params from the analysisPlan entries.
    plan_params: dict[str, dict] = {}
    for entry in plan:
        for rid in entry.get("recipes", []):
            if isinstance(rid, dict):
                plan_params[rid["id"]] = rid.get("params", {})
            elif rid not in plan_params:
                plan_params[rid] = {}

    results: dict[str, RecipeResult] = {}
    outputs: dict[str, tuple[list[str], list[str]]] = {}
    for rec in runnable:
        print(f"running {rec.id} ...", flush=True)
        try:
            # Inject per-recipe params into dataset.meta before running
            # (FR-ANA-8: parameterised recipes read from meta).
            recipe_params = plan_params.get(rec.id, {})
            dataset.meta = {**dataset.meta, **recipe_params}
            result = rec.run(dataset)
        except Exception as exc:  # noqa: BLE001 - recorded in outcome.errors below
            outcome.errors[rec.id] = f"{type(exc).__name__}: {exc}"
            print(f"  ERROR {rec.id}: {outcome.errors[rec.id]}", file=sys.stderr)
            continue
        results[rec.id] = result
        outputs[rec.id] = _write_recipe_output(outcome.out_dir, rec.id, result)
        outcome.executed.append(rec.id)

    _write_report(outcome, plan, rq_text, results, outputs)

    if server and outcome.failed_validation:
        _record_findings(
            server,
            [
                {
                    "source": "analysis/run",
                    "kind": "requires-fail",
                    "requirementId": "FR-ANA-2",
                    "message": c.describe(),
                    "context": {"recipe": c.recipe_id, "rq": c.rq},
                }
                for c in outcome.failed_validation
            ],
        )
    if server:
        runs = [
            {
                "recipeId": rid,
                "status": "ok",
                "answers": list(REGISTRY[rid].answers),
            }
            for rid in outcome.executed
        ]
        recorded = _record_runs(server, study_id, runs)
        print(
            "recipe runs recorded to middleware"
            if recorded
            else "middleware unreachable - recipe runs not recorded "
            "(report is complete)"
        )
    return outcome


def _write_report(
    outcome: RunOutcome,
    plan: list[dict],
    rq_text: dict[str, str],
    results: dict[str, RecipeResult],
    outputs: dict[str, tuple[list[str], list[str]]],
) -> None:
    """report.md: one section per research question (FR-ANA-4)."""
    lines = [
        f"# Analysis report - {outcome.study_id}",
        "",
        "Generated by `analysis run`; every section names the research "
        "question it answers (FR-DASH-6/FR-ANA-4 traceability).",
        "",
    ]
    if outcome.failed_validation or outcome.errors:
        lines += ["## Plan validation failures", ""]
        for c in outcome.failed_validation:
            lines.append(f"- **{c.describe()}**")
        for rid, err in outcome.errors.items():
            lines.append(f"- **{rid}: recipe raised {err}**")
        lines += [
            "",
            "These analyses did not run. A missing event type at this stage "
            "is an instrumentation/specification defect to fix *before* "
            "data collection ends (FR-ANA-2).",
            "",
        ]
    for entry in plan:
        rq = entry["rq"]
        lines += [f"## {rq}", ""]
        if rq_text.get(rq):
            lines += [f"> {rq_text[rq]}", ""]
        for rid in entry.get("recipes", []):
            lines += [f"### `{rid}` (answers {rq})", ""]
            if rid in results:
                lines += [results[rid].summary, ""]
                tables, figs = outputs[rid]
                for f in figs:
                    lines += [f"![{rid} {f}]({rid}/{f})", ""]
                if tables:
                    lines += [
                        "Tables: " + ", ".join(f"[`{t}`]({rid}/{t})" for t in tables),
                        "",
                    ]
            else:
                check = next(
                    (c for c in outcome.failed_validation if c.recipe_id == rid), None
                )
                reason = (
                    check.describe()
                    if check
                    else outcome.errors.get(rid, "not executed")
                )
                lines += [f"**Not run** - {reason}", ""]
    (outcome.out_dir / "report.md").write_text("\n".join(lines))
    print(f"report: {outcome.out_dir / 'report.md'}")
