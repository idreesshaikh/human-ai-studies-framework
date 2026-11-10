# Evidence evaluation

The offline evaluator checks evidence-map decisions against a supplied
benchmark. It cannot modify studies, bypass approval, or promote a classifier.
Synthetic results verify software behavior, not methodological usefulness.

## Run

Exercise the runner with synthetic fixtures:

```bash
uv run --no-sync python scripts/evaluate_research.py \
  --allow-synthetic --system-version <commit>
```

For independently reviewed cases:

```bash
uv run --no-sync python scripts/evaluate_research.py \
  --benchmark /path/to/frozen-benchmark.json --map /path/to/reviewed-map.json \
  --predictions /path/to/predictions.json --system-version <immutable-version>
```

Outputs go to ignored `.research-artifacts/`. Reports include confusion counts,
unsafe recommendations, coverage, error among automated decisions, provider
failures, and latency. Unknown costs remain unknown. Missing or duplicate
decisions fail validation; explicit abstentions remain visible.

## Benchmark requirements

Record source versions, exact passages and locations, review provenance,
context, assumptions, and unresolved disagreements. Separate reported facts
from recommendations. A method's use does not establish its validity.

Keep related studies, publication versions, and paraphrases within one split.
Freeze labels and evaluation criteria before testing; calibrate thresholds on
calibration data only. Model-generated labels cannot substitute for independent
review. Reviewer-agreement calculations consume supplied judgments.

Optional `--runner direct` and `--runner propose-critic` adapters require
`--live` and accept `--model`. Both receive the same evidence and context,
without expected labels. Malformed or failed decisions become abstentions.
These are experimental evaluation adapters, separate from production authoring.

## Model compatibility

Use synthetic briefs to exercise the real model parser:

```bash
uv run --no-sync --env-file .env python scripts/check_design_models.py --live
```

This makes provider calls and checks parsing and compilation. It does not assess
advice quality. Record exact versions and retain failures; a mutable model alias
does not identify a reproducible research condition.
