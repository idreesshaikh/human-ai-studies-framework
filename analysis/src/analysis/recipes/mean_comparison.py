"""Fixed normal-theory two-arm analysis with optional pre-treatment ANCOVA."""

import math

import numpy as np
import pandas as pd
from scipy import stats

from analysis.core import RecipeResult, recipe
from analysis.dataset import Dataset
from analysis.outcomes import participant_outcomes


@recipe(
    id="mean-comparison", answers=["RQ-P1"], title="Mean comparison (t-test or ANCOVA)"
)
def run(dataset: Dataset) -> RecipeResult:
    proto = dataset.meta.get("protocol", {})
    measures = [
        m
        for m in proto.get("measures", [])
        if isinstance(m, dict) and m["analysisRecipe"] == "mean-comparison"
    ]
    if not measures or len(proto.get("conditions", [])) != 2:
        return RecipeResult(summary="No declared typed two-arm mean comparison.")
    tests = []
    for measure in measures:
        for field in measure["fields"]:
            values = participant_outcomes(
                dataset.analysis_rows,
                proto,
                field,
                measure["instrument"],
                measure.get("analysisScale", "raw"),
            )
            a, b = proto["conditions"]
            if proto["participants"]["design"] == "within-subjects":
                ids = sorted(
                    {p for p, c in values if (p, a) in values and (p, b) in values}
                )
                if len(ids) < 2:
                    continue
                result = stats.ttest_rel(
                    [values[(p, a)] for p in ids], [values[(p, b)] for p in ids]
                )
                method = "paired-t"
                n = len(ids)
            elif proto.get("covariate"):
                cov = proto["covariate"]
                pre = participant_outcomes(
                    dataset.analysis_rows, proto, cov["field"], cov["instrument"]
                )
                covariates = {}
                for (pid, _), value in pre.items():
                    covariates.setdefault(pid, value)
                keys = sorted(
                    k for k in values if k[0] in covariates and k[1] in {a, b}
                )
                if len({p for p, _ in keys}) != len(keys):
                    raise ValueError(
                        "ANCOVA requires independent participants in the two arms"
                    )
                x = np.array(
                    [[1, int(c == b), covariates[p]] for p, c in keys], dtype=float
                )
                y = np.array([values[k] for k in keys])
                if len(keys) <= 3 or np.linalg.matrix_rank(x) < 3:
                    continue
                beta = np.linalg.lstsq(x, y, rcond=None)[0]
                residual = y - x @ beta
                se = math.sqrt(
                    float(
                        residual
                        @ residual
                        / (len(keys) - 3)
                        * np.linalg.inv(x.T @ x)[1, 1]
                    )
                )
                if not se:
                    continue
                statistic = float(beta[1] / se)
                result = type(
                    "OLS",
                    (),
                    {
                        "statistic": statistic,
                        "pvalue": float(2 * stats.t.sf(abs(statistic), len(keys) - 3)),
                    },
                )()
                method = "ancova"
                n = len(keys)
            else:
                aa = [v for (p, c), v in values.items() if c == a]
                bb = [v for (p, c), v in values.items() if c == b]
                if min(len(aa), len(bb)) < 2:
                    continue
                result = stats.ttest_ind(aa, bb, equal_var=True)
                method = "two-sample-t"
                n = len(aa) + len(bb)
            tests.append(
                {
                    "measureId": measure["id"],
                    "field": field,
                    "test": method,
                    "statistic": float(result.statistic),
                    "p": float(result.pvalue),
                    "n": n,
                }
            )
    return RecipeResult(
        tables={"tests": pd.DataFrame(tests)},
        summary=(
            f"{len(tests)} declared mean comparison(s); "
            "incomplete data are not imputed."
        ),
        methods="Two-sided pooled-variance independent or paired "
        "t-test. Declared pre-task covariate uses OLS ANCOVA "
        "with condition and covariate; no interactions.",
    )
