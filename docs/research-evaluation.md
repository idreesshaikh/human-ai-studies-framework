# Evidence review and evaluation

Supports #47, #50, #90–98 without claiming that integration is scientific
evaluation. The reusable evaluator is `middleware.evaluation`; it is offline
and cannot modify a study, bypass approval, or promote a classifier.

## Curate before evaluating

For #91, select 20–30 empirical studies using a recorded query, date, inclusion
criteria, exclusions, and three design families. The executable compiler currently
supports within- and between-subjects comparisons; a third family needs a justified
execution contract, not a renamed comparison. Deduplicate underlying studies
before counting publications. Reserve entire study/report families for evaluation.

For each relation record a stable publication/version, exact passage and locator,
reported fact versus interpretation/recommendation, population, task, construct,
measurement, available capture, assumptions, and unknowns. A method being used is
not evidence that it is valid. Leave extracted entries **unreviewed** until a
second reviewer checks the source. Record both independent assessments,
disagreements, and adjudication; do not replace an unknown with a plausible guess.

Starting sources, not a completed systematic review:

- [SIGSOFT method-specific standards](https://www2.sigsoft.org/EmpiricalStandards/docs/standards)
  motivate explicit design alternatives, assumptions and validity threats.
- [Peng et al.](https://arxiv.org/abs/2302.06590) concern a controlled programming
  experiment. Population, task and outcome must remain attached to any inference.
- [Ziegler et al.](https://arxiv.org/abs/2205.06537) concern code-completion
  perceptions and telemetry. An association is not a causal outcome measure.

Our implementation implication: never promote a source from discovery to support
merely because it is topical. These notes are not independent annotations.

## Freeze a benchmark

`Benchmark` records a version, evidence digest, label provenance, two reviewer
identities and adjudication notes, and typed cases. Each case has a stable id,
scenario family, train/calibration/test split, source study ids, explicit context,
and expected statuses by candidate. Related studies/publications and scenario
paraphrases cannot cross splits; the conservative publication check may require
reserving an entire shared report. Do not train or fit thresholds on test cases.

The schema records a declared review, not reviewer authentication. Reviewers must
actually establish the labels. LLM-only labels are not accepted as ground truth.
Include missing context, topical-but-inapplicable evidence, conflicts, negation,
unsupported measurements, long passages, and a held-out population/task.

The synthetic software check is runnable now:

```bash
uv run --no-sync python scripts/evaluate_research.py \
  --allow-synthetic --system-version <commit>
```

Outputs go to ignored `.research-artifacts/`. To evaluate real reviewed cases:

```bash
uv run --no-sync python scripts/evaluate_research.py \
  --benchmark /path/to/frozen-benchmark.json --map /path/to/reviewed-map.json \
  --predictions /path/to/predictions.json --system-version <immutable-version>
```

Predictions provide case/candidate ids, status or explicit `null` abstention,
optional confidence, total latency including fallback, optional monetary cost,
and any failure. Missing/duplicate decisions fail validation. Unknown monetary
cost stays unknown. Reports include per-class confusion, unsafe recommendations,
automated coverage, error among automated decisions, confidence Brier score when
supplied, provider failures and p95 latency. Synthetic scores test software only.

## Compare fairly; promote conditionally

For #95/#98 freeze the same corpus and evidence digest, tool access, scenarios,
budgets, model versions, output rubric and promotion criteria before running a
general-assistant baseline, mapping-assisted workflow, and classifier condition.
Review outputs blind to system labels where practical. Independently score source
support, assumptions, executable protocol feasibility, correction effort,
time-to-approved-protocol, and uncertainty; these cannot be established by a
status-match score alone.

`reviewer_agreement` computes observed agreement, Cohen's kappa and disagreement
ids from two independently supplied annotation dictionaries. It does not create
reviewer judgments or replace adjudication.

The runner also supports experimental `--runner direct` and
`--runner propose-critic` with explicit `--live` and configurable `--model`.
Both receive the same evidence and context, never the expected labels. The second
stage critiques the first; malformed, missing or failed decisions become explicit
abstentions. Provider usage is recorded, monetary cost stays unknown. These
adapters are not production agents or evidence of improved research quality.

For #96 compare rules, a conventional classifier, an LLM, and an accessible typed
decision model. Calibrate abstention on calibration data only. For #97 do not add
a production classifier until it improves preset quality/coverage/cost criteria
without unsafe recommendations or invalid protocols. Missing model access or
reviewed data is a limitation, not a negative experiment. Current decision:
**no promotion pending evidence**; this is not a completed reject/adopt experiment.

For #50 compare current retrieval with an open-source propose/critic or delegated
retrieval candidate on the same frozen inputs. Count all calls, escalation,
latency, cost, failure and correction effort. Extra stages alone establish no
quality gain. Keep experiment runners separate from production orchestration;
the evaluator can score imported outputs from either architecture without adding
an unevaluated multi-agent runtime to the application.

## Bounded model compatibility check

The runner uses Mistral's [structured JSON interface](https://docs.mistral.ai/studio/conversations/structured-output)
through the application's real parser. It requires an explicit live flag and
uses synthetic briefs; it stops an inaccessible model after 401/403/429.

```bash
uv run --no-sync --env-file .env python scripts/check_design_models.py --live \
  --models ministral-14b-latest mistral-small-latest mistral-medium-latest
```

On 2026-10-05 Ministral produced usable parsed turns for three briefs in
1.01–1.79 seconds. Small and Medium each returned 429 on their first request.
No model was silently changed. Token usage is recorded; prices remain unknown
unless established for the actual account. The returned Ministral name remained
a `-latest` alias, so this is not a frozen-version research comparison. Retain the
working configurable route for the demo; expert design-quality review remains open.
