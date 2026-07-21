# Research questions

Three tiers. The framework RQs are the thesis; the pilot RQs exist to
*evaluate* the framework by exercising it end-to-end on a real study; the
demonstrator RQs exist to *prove the platform's distinctive capabilities* -
validation cases run by the facilitator, chosen because each needs a
capability only this platform has. They are not product content:
researchers design their own studies (FR-CONV/FR-TPL); these are ours.

## Tier 1 - Framework RQs (the thesis contribution)

**RQ-F1 - Specification.** Can an agent–human developer study be captured as
a machine-readable requirements specification (protocol) complete enough to
drive its instrumentation, phase gating, data validation, and analysis
without side-channel configuration?
*Answered by:* the protocol engine + instrument legs + analysis pipeline (construction); the dry run and pilot reveal every place the protocol was insufficient - each is a specification defect to report.

**RQ-F2 - Traceability.** Does maintaining the chain RQ → requirement →
instrument → data element → recipe → claim reduce study setup effort and
surface design defects before data collection?
*Answered by:* the recipe `requires`-check (defects caught at
plan-validation time), the lifecycle gates, and the framework post-mortem (setup time, defect log with RE classification).

**RQ-F3 - Replicability.** Can analyses be packaged as reusable recipes and
studies as replication kits such that a third party reproduces the report
from the kit alone?
*Answered by:* published algorithms implemented as cited recipes, and kit re-import reproducing `report.md` byte-for-byte.

**RQ-F4 - Conversational elicitation.**
Can a literature-grounded design conversation elicit a complete, valid,
statistically sound study protocol - and capture the elicitation trail as
a first-class traceability artifact - at least as completely as expert
hand-specification, with every AI-proposed design element either cited
into the corpus or visibly labeled unsourced?
*Answered by:* the FR-CONV-1 end-to-end walkthrough (the
FR-TPL-1 F1.2 retro-fit proof that our own pilot is expressible as a
template instance; the FR-CONV-6 chain export), evaluated against the
falsifier: any protocol section the conversation *cannot* elicit without
side-channel editing is a specification defect of the conversation layer,
logged via FR-META-1 exactly as RQ-F1 treats protocol leaks.

## Tier 2 - Pilot-study RQs (the evaluation case)

Within-subjects, conditions `ai-assisted` vs `unassisted`, comparable Python
tasks.

**RQ-P1 - Cognitive load.** How does AI assistance affect self-reported
fatigue trajectories, stuck-episode frequency/duration, and end-of-session
TLX-style workload?
*Data:* fatigue probes, stuck events, debrief (TERN).
*Recipes:* `fatigue-by-condition`, `stuck-episodes`, `tlx-debrief`.

**RQ-P2 - Code quality.** How does AI assistance affect the static
complexity of the code produced (parameter counts, nesting penalty,
identifier length, scope distance, Halstead effort, comment ratio,
indentation variance, line widths)?
*Data:* static-metrics leg. *Recipe:* `code-quality-by-condition`.

**RQ-P3 - Behavior.** How does AI assistance change working behavior -
paste size/frequency, paste-then-edit latency, file/tab switching, edit
burst patterns, and the human/AI/paste origin mix of the code produced?
*Data:* behavioral telemetry leg, esp. origin
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

## Tier 3 - demonstrator-study RQs

Two study designs frame the platform's distinctive capabilities -
chosen over straight METR/Cursor replications because each needs something
only this platform has: the per-chunk four-leg join (the comprehension-debt
design) and agent participants run by the harness (the context-ablation
design). The RQ sets below justify FR-INST-19 (comprehension probes) and
FR-PROT-9 (agent participants). The standalone draft protocols that once
carried them were pilot studies to prove the platform, since removed as
clutter; FR-PROT-9's fit criterion is now a neutral test fixture
(`protocol/tests/fixtures/agent-participant-v3.yaml`).

### Comprehension-debt study (human; conditions `ai-assisted` build sitting → `unassisted` maintenance sitting)

**RQ-C1 - Engagement.** How deeply do developers engage with agent-produced
code before accepting it - review time per changed line, scroll coverage,
files opened, edits to the agent's output - and how do accepted chunks
distribute across engagement levels?
*Data:* FR-INST-8/9/10 + visible ranges, agent leg. *Recipes:*
`ai-review-behavior`, `agent-interaction-dynamics`, `engagement-depth` (new).

**RQ-C2 - Immediate comprehension.** How does engagement depth relate to
comprehension of the accepted chunk (timeboxed predict-output /
locate-change probes)?
*Data:* comprehension probes (FR-INST-19) joined per chunk. *Recipe:*
`comprehension-by-engagement` (new).

**RQ-C3 - Comprehension debt.** In a maintenance sitting 5-7 days later,
how do time-to-localize, time-to-fix, and fix success on injected defects
differ between self-written code, deeply engaged agent chunks, and skimmed
agent chunks?
*Data:* task harness (FR-INST-16), behavioral leg, probe outcomes.
*Recipes:* `maintenance-transfer` (new), `task-outcome-by-condition`.

**RQ-C4 - Code-profile moderation.** Does the cognitive-load profile of an
accepted chunk (9-metric matrix) moderate the engagement → comprehension →
maintenance chain?
*Data:* metrics leg per chunk. *Recipes:* `code-quality-by-condition`,
`comprehension-by-engagement`.

### Context-ablation study (agent participants; conditions `no-context` / `hand-written-context` / `generated-context`)

**RQ-A1 - Success and cost.** How do harness pass rates,
time-to-first-green, and cost (tokens, tool calls, wall time) differ across
context conditions - including the platform's own generated context files
(FR-AGF-2)?
*Data:* task harness, agent leg. *Recipes:* `task-outcome-by-condition`,
`cost-effectiveness-frontier` (new).

**RQ-A2 - Output profile.** How does the cognitive-load profile of the
agent's diffs differ across context conditions?
*Data:* metrics leg over per-run diffs. *Recipe:*
`code-quality-by-condition`.

**RQ-A3 - Agent behavior.** How does the agent's working behavior differ
across context conditions - tool-call mix, exploration-vs-editing balance,
turn cadence, dead-end sequences?
*Data:* agent leg. *Recipe:* `agent-interaction-dynamics`.

## Expectations discipline

The pilot is small (4–8 participants). Pilot RQs are answered with exact
tests, effect sizes, and explicit n - as *demonstration of the pipeline and
hypothesis-generating results*, not confirmatory claims (NFR-8). The
framework RQs, by contrast, are answered decisively: the platform either
drove the study or it didn't, and every leak is evidence.
