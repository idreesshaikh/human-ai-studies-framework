# StudyLoop planner

The Plan tab saves recruitment assumptions against an immutable protocol snapshot and hash. The Data tab records real pilot tags and control-arm inclusion decisions. Protocol v6 links outcomes to event fields and moves survey definitions into the capture configuration. Protocols v1–v5 continue to load unchanged, with legacy string measures explicitly untyped.

## Methods and supported combinations

| Design | Fixed recipe | Test | Distributions |
| --- | --- | --- | --- |
| Independent two arms | `two-group-nonparametric` | Mann–Whitney U | Normal, log-normal, ordinal |
| Paired two conditions | `paired-nonparametric` | Wilcoxon signed-rank | Normal, ordinal |
| Declared survey outcomes | `typed-measures` | Test fixed by protocol design | Same combinations above |
| Declared means | `mean-comparison` | Independent/paired t-test; independent ANCOVA with a declared pre-task covariate | Normal; log-normal only when a log transform is declared |

The planner checks the protocol design, counterbalancing, measure, and recipe before saving. It refuses unsupported combinations, binary/Fisher planning, crossover regression, mixed models, joint paired log-normal simulation, and more than two arms. Refusal includes a reason and produces no number. Independent covariate planning is an approximation using the residual variance factor `1 − rho²`; it is supported only alongside the ANCOVA recipe. A pre-task declaration does not validate the skill instrument.

- Normal effects are location differences in outcome units; SD uses the same units. For paired designs, SD is the SD of participant differences.
- Log-normal effects and SD are on the log scale. The independent rank test is invariant to exponentiation, so simulation can rank the logged draws without overflow.
- Ordinal effects are latent normal shifts, with equal-probability thresholds for the declared number of categories. They are **not observed Likert point differences**.
- T-test power uses the existing noncentral-t calculation. Simulation uses NumPy/SciPy and the same p-value selection as the recipes: small untied samples can use exact tests, while tied observations use the asymptotic tie correction. Tables include `p_value` and `p_method`; the legacy `p_exact` column is populated only for an actual exact test. Wilcoxon zero differences are dropped; all-zero differences have p=1.
- Paired simulation adds a signed period shift for the recorded order and an additional shift for the positive order. It models the consequences for the actual unadjusted rank analysis; it does not fit a period/carryover regression. The UI reports the null rejection estimate and warns when its interval exceeds nominal alpha. Fixed order can confound treatment and period.
- Simulation returns a seeded Monte Carlo estimate and a Wilson 95% interval. The curve and integer sample-size search are estimates and can fluctuate across sample sizes. The sensitivity table reports the smallest detectable effect at half, current, and double planned n. The explored range and effect search are bounded; an unreached target returns null.
- Required complete participants and dropout-adjusted recruitment are separate. Independent designs round recruitment separately in each arm. Attrition is a planning assumption; it does not model informative dropout.

Numerical tests pin d=0.5, alpha=0.05, power=0.8 to 64 participants per independent arm and 34 paired participants. For tested normal/ordinal null configurations, simulated alpha must be within 0.015 of nominal; normal rank-test power must agree with t-test power within 0.06. These tolerances are computational validation, not a claim that any assumed distribution fits a real study.

## Protocol v6 and instruments

[The complete example](../protocol/examples/planner-v6.yaml) declares tasks, typed measures, survey items, tool metadata, and a pre-task covariate. It is configuration, not evidence. Supply actual materials and tool versions before recruitment.

```yaml
protocolVersion: 6
measureSetVersion: '1.0'
measures:
  - id: completion-time
    construct: Task completion time
    instrument: taskHarness
    fields: [task_outcome.firstGreenMs]
    analysisRecipe: paired-nonparametric
    version: '1.0'
```

Each typed measure must name a declared instrument and a recipe in `analysisPlan`. Survey fields must refer to a captured item or score. IDs, scales, SUS reverse scoring, covariate timing, optional content hashes, and condition references are validated. Legacy documents are not silently upgraded and are not assigned invented event-field links. A researcher upgrading to v6 must supply those links.

`GET /instruments/surveys` returns the shipped definitions. Include the chosen definition in `instruments.surveys[]`:

| Instrument | Interpretation and reuse source |
| --- | --- |
| `raw-nasa-tlx` | Unweighted mean of six 0–100 ratings, step 5; performance runs Good → Poor. Wording/labels from the [NASA paper-and-pencil package](https://ntrs.nasa.gov/citations/20000021488). NASA [permits use and modification without permission](https://www.nasa.gov/human-systems-integration-division/nasa-task-load-index-tlx/). This electronic raw variant is not weighted TLX. |
| `sus` | Original ten 1–5 items; reverse even items, sum contributions × 2.5. [John Brooke (1996)](https://hci-studies.org/methods-and-measures/downloads/SUS_Brooke1996.pdf) permits usability assessment with source acknowledgement in published reports. Define the system under assessment in participant instructions. |
| `legacy-tlx-inspired` | Existing six items, 1–7. Subscales only; no validated aggregate, and not NASA-TLX. Repository MIT licence. |
| `pre-task-skill` | Three 1–5 items on relevant experience, debugging confidence and task familiarity. Experimental, unvalidated item set; researcher must pilot before treating it as a skill covariate. Repository MIT licence. |

The extension supports pre-task/post-task timing and explicit condition lists, including condition names defined by tool versions. v6 does not infer AI reliance from the literal `ai-assisted` name. v1–v5 retain their legacy survey behavior. v6 events carry `instrumentId`, `instrumentVersion`, `instrumentHash`, responses and score; the recipe independently checks/scorers responses instead of trusting the client score. Missing, invalid or mismatched responses have no aggregate.

The extension's event schema is v6. Middleware still accepts and recognizes versions 2–5; unknown versions are stored with an integrity flag. The environment snapshot records available editor/extension versions, capture coverage, protocol/task/measure provenance, date and a participant-confirmed model name (or explicitly unknown). The configured model identifier is kept separate from the participant confirmation.

## Pilot updates and inclusion

Mark sessions as pilot in Data with a reason. The tag is exported on every row of that session and an append-only decision record includes the researcher identity and date. Synthetic sessions cannot be tagged as real pilot data. Confirmatory datasets, notebooks and recipes omit entire pilot/synthetic/researcher-excluded sessions; raw exports preserve real pilot rows and decisions.

Pilot variance is estimated from participant summaries, never event counts. Independent designs use within-arm pooled variance and its chi-square interval; paired designs use complete participant differences. Log-normal pilots use logged outcomes. A pilot with fewer than eight independent participants is flagged as too uncertain to act on. The before/after plans retain the same effect assumption; endpoint-SD sensitivity shows recruitment under both ends of the variance interval.

Ordinal latent variance, pilot ANCOVA residual updates, and pilot period/order-adjusted variance are unsupported and refused. Normal-theory variance intervals assume normal participant summaries; they do not include uncertainty in the assumed effect. This is not an internal-pilot sequential stopping procedure. Sequential designs remain gated.

## Audit and calibration

Declare `controlConditions` explicitly in the protocol. The audit never guesses control arms from names. It counts AI suggestions, heuristic AI edit origins, agent turns and tool calls. Paste counts are ambiguous and do not establish AI origin. Missing extension coverage or incomplete session boundaries/sequences return `cannot-assess` unless positive AI signals are present. `no-evidence` never proves no AI use.

External CLI bulk reloads, drag-and-drop paste and activity outside the editor are known blind spots. Edit-origin heuristics and agent annotations are not independent ground truth. Decisions include a reason and retain their history. The audit never automatically excludes a session.

Real scripted calibration sessions with independent truth are still required. Submit labels through `POST /studies/{id}/audit-calibration` with `labels: {sessionId: true|false}` and a `source` describing the independent observation. The endpoint accepts only this study's real captured control sessions, records the supplied labels/source, and reports per-signal/combined sensitivity and specificity with exact binomial intervals and explicit abstentions. Unit-test labels validate computation; they are not audit accuracy evidence. Decision models remain gated until real labels exist.

## API and exports

All study routes retain project authorization. Calculations/tags/calibration require contribution permission; reading and exporting require view permission. A lineage comparison authorizes both studies.

| Route | Purpose |
| --- | --- |
| `GET /studies/{id}/plan` | Current protocol, latest saved plan, stale-hash flag and session decisions |
| `POST /studies/{id}/plan` | Validate assumptions against protocol, calculate and save immutable plan |
| `GET /studies/{id}/power` | Unsaved compatibility shape backed by the same planner; before a protocol exists, explicitly exploratory t-test assumptions |
| `POST /studies/{id}/pilot-variance` | Re-estimate variance from real tagged pilot rows and save before/after plan |
| `GET /studies/{id}/control-arm-audit` | Session signals, limits and recorded decisions/calibration |
| `POST /studies/{id}/sessions/{session}/annotation` | Record pilot/inclusion decision and required reason |
| `GET /studies/{id}/lineage` | Side-by-side original/re-run fields from `rerunOf` ID or recorded protocol hash |
| `GET /studies/{id}/design-card?format=json|markdown` | Factual standalone design card |

Planning uses snake-case inputs, for example:

```json
{
  "design": "within-subjects",
  "test": "wilcoxon",
  "measure_id": "completion-time",
  "distribution": "normal",
  "effect": 0.5,
  "sd": 1,
  "alpha": 0.05,
  "target_power": 0.8,
  "dropout": 0.1,
  "counterbalanced": true,
  "planned_n": 40,
  "max_n": 400,
  "simulations": 1000,
  "seed": 20261007
}
```

JSON and Markdown design cards are included in data bundles and replication kits. They record the saved plan and its pinned hash/version, analysis, instruments/wording/licences, task and measure hashes, declared and captured tool/model metadata, audit signals and decisions. Re-runs declare `rerunOf` and remain separate; nothing is automatically pooled and no validity score is generated.

## Validation

The automated checks exercise planning calculations, typed capture and analysis, protocol preservation, permissions, exports and responsive researcher workflows. They validate software behavior; real audit calibration, empirical validation of the skill form, literature remeasurement, researcher interviews and reviewer feedback remain study work. No decision model or sequential design is activated.
