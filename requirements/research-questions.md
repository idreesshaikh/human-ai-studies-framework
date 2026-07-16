# Research questions

Two tiers. The framework RQs are the thesis; the pilot RQs exist to
*evaluate* the framework by exercising it end-to-end on a real study.

## Tier 1 - Framework RQs (the thesis contribution)

**RQ-F1 - Specification.** Can an agent–human developer study be captured as
a machine-readable requirements specification (protocol) complete enough to
drive its instrumentation, phase gating, data validation, and analysis
without side-channel configuration?
*Answered by:* Mega-Prompts 02–07 (construction) + 08 (the dry run and pilot
reveal every place the protocol was insufficient - each is a specification
defect to report).

**RQ-F2 - Traceability.** Does maintaining the chain RQ → requirement →
instrument → data element → recipe → claim reduce study setup effort and
surface design defects before data collection?
*Answered by:* the recipe `requires`-check (defects caught at
plan-validation time), the lifecycle gates, and the framework post-mortem in
`study/pilot/findings.md` (setup time, defect log with RE classification).

**RQ-F3 - Replicability.** Can analyses be packaged as reusable recipes and
studies as replication kits such that a third party reproduces the report
from the kit alone?
*Answered by:* Mega-Prompt 07 (one published algorithm as a recipe) and
Mega-Prompt 09 item 2 (kit re-import reproduces `report.md`).

## Tier 2 - Pilot-study RQs (the evaluation case)

Within-subjects, conditions `ai-assisted` vs `unassisted`, comparable Python
tasks.

**RQ-P1 - Cognitive load.** How does AI assistance affect self-reported
fatigue trajectories, stuck-episode frequency/duration, and end-of-session
TLX-style workload?
*Data:* fatigue probes, stuck events, debrief (Cognitive Overlay).
*Recipes:* `fatigue-by-condition`, `stuck-episodes`, `tlx-debrief`.

**RQ-P2 - Code quality.** How does AI assistance affect the static
complexity of the code produced (parameter counts, nesting penalty,
identifier length, scope distance, Halstead effort, comment ratio,
indentation variance, line widths)?
*Data:* static-metrics leg. *Recipe:* `code-quality-by-condition`.

**RQ-P3 - Behavior.** How does AI assistance change working behavior -
paste size/frequency, paste-then-edit latency, file/tab switching, edit
burst patterns, and the human/AI/paste origin mix of the code produced?
*Data:* behavioral telemetry leg (Mega-Prompt 05), esp. origin
classification (FR-INST-10) and active/idle denominators (FR-INST-11).
*Recipe:* `paste-behavior`.

**RQ-P4 - AI review behavior.** How do developers review AI-generated code
before accepting it - review latency per suggestion, scroll coverage of
injected changes, accept/reject/dismiss rates, and how these vary with
suggestion size and session fatigue?
*Data:* AI-completion lifecycle events (FR-INST-8), visible-range tracking
(FR-INST-9), joined against fatigue probes on the shared timeline.
*Recipe:* `ai-review-behavior`. *This RQ is the framework's differentiator:
no off-the-shelf tool joins completion lifecycle, scroll coverage, and
self-reported fatigue on one timeline.*

**RQ-P5 - Human-agent interaction dynamics.** How does the conversation
with the agent unfold and relate to outcomes - prompting cadence and
prompt/response sizes, tool-call mix, **reliance loops** (error pasted to
agent → response → code pasted back), delegation-vs-verification balance,
and how these co-vary with fatigue, stuck episodes, and task outcome?
*Data:* agent leg (FR-AGENT-1/2/3) joined with behavioral events, fatigue
probes, and task-outcome events (FR-INST-16) on the shared timeline.
*Recipes:* `agent-interaction-dynamics`, `task-outcome-by-condition`.

Task outcome (FR-INST-16: acceptance-test pass rates, time-to-first-green)
serves as the ground-truth dependent variable across RQ-P1–P5: every
"how does AI assistance affect X" answer is interpreted against whether the
task was actually accomplished.

## Expectations discipline

The pilot is small (4–8 participants). Pilot RQs are answered with exact
tests, effect sizes, and explicit n - as *demonstration of the pipeline and
hypothesis-generating results*, not confirmatory claims (NFR-8). The
framework RQs, by contrast, are answered decisively: the platform either
drove the study or it didn't, and every leak is evidence.
