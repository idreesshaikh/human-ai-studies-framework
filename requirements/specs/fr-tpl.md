# FR-TPL — Study templates & statistical plans (detailed specification)

**SRS family:** FR-TPL. **Phase:** 15.
Relationship to FR-CONV: templates are the *knowledge* the design
conversation reasons over; the conversation is the primary surface that
instantiates them (FR-TPL-3 rev 2).

## 1. Context

Every empirical human-AI study re-derives its design from papers by hand:
which conditions, which measures, which instruments, and — the part
researchers most fear getting wrong — **which statistical formulation**.
A study template encodes one published, citable design as a parameterized,
machine-checkable object that instantiates into a valid protocol
(FR-PROT-1). The protocol layer is untouched: templates are **protocol
generators**, one level above study-as-code.

## 2. Template object model

A template is a versioned YAML document in the registry:

```yaml
templateId: metr-rct-v1          # stable, never renumbered
title: Randomized controlled trial of AI assistance on real tasks
source:                          # mandatory citation(s)
  - paperRef: arxiv:2507.09089   # METR RCT
designType: rct-within-subjects  # taxonomy, §3
dataPath: live                   # live | curated | either
parameters:                      # what the researcher decides
  - id: taskCount        {type: int, min: 2, rationale: counterbalancing}
  - id: sessionMinutes   {type: int, default: 45}
  - id: conditions       {fixed: [ai-assisted, unassisted]}
  - id: participantPlan  {type: participants, min: 4}
measures:                        # each maps to instruments + data elements
  - id: task-time        {leg: behavioral, elements: [session clock, task_outcome]}
  - id: perceived-speed  {leg: cognitive, elements: [debrief], caution: perception-gap}
instruments: {...}               # derived FR-PROT-4 configs per condition
statisticalPlan:                 # §4 — the differentiator
  unit: participant
  perRQ:
    - rq: primary
      outcome: task-time (continuous, paired)
      test: wilcoxon-signed-rank (exact)
      effectSize: matched-pairs rank-biserial
      smallN: hypothesis-generating framing (NFR-8)
threats:                         # named validity threats + mitigations
  - novelty-effect: {mitigation: task counterbalancing, cite: arxiv:2507.09089}
protocolSkeleton: {...}          # the YAML the compiler fills
```

## 3. Requirements detail

### FR-TPL-1 (M) — The template registry

Elaboration:
1. Registry = versioned template documents validated against a published
   template JSON Schema (sibling of the protocol schema; same
   `protocolVersion` discipline — `templateVersion`, consumers branch,
   never guess).
2. **Seed templates (the phase 15 deliverable), each fully encoding its
   source design:**
   - `metr-rct-v1` — within-subjects RCT on real tasks, speed +
     perception measures (`metr-early-2025-dev-productivity`); live path.
   - `ziegler-telemetry-survey-v1` — telemetry × self-report join,
     acceptance-rate and persistence measures
     (`copilot-productivity-ziegler`); live path; its recipe already
     exists (`ziegler-acceptance-rate`, FR-ANA-5) — template and recipe
     cite the same paper, closing the design→analysis loop.
   - `hai-eval-synergy-v1` — within-subject human-AI synergy comparison
     (`hai-eval-human-ai-synergy`); live path.
   - `cursor-mining-v1` — repository-mining velocity-vs-complexity
     design (`speed-at-cost-of-quality-cursor`); curated path (FR-CUR),
     exercising the dataset-exists branch.
3. Design-type taxonomy (the `designType` axis) follows Stol &
   Fitzgerald's ABC study-strategy vocabulary (field/lab/sample —
   corpus index §Not downloaded) so templates are classified in the
   field's own terms.
4. Instantiation = template + parameter values → protocol draft, via the
   same deterministic compiler as FR-CONV-3 (a template instantiation
   *is* a batch of design moves).

Fit criteria:
- F1.1 All four seed templates validate against the template schema and
  instantiate into protocols that pass `protocol validate` with zero
  hand edits.
- F1.2 `metr-rct-v1` instantiated with the maintenance-task pilot's
  parameters reproduces a protocol equivalent to that hand-written
  study's structure (the retro-fit proof: an already-run study can be
  described through a published-design template). The template is
  platform library content; the study is a separate protocol instance —
  a study never *is* a template.
- F1.3 Template versioning: instantiating `templateId@v1` after a `v2`
  exists still works and records which version produced the protocol.

### FR-TPL-2 (M) — Statistical plans: correct statistics by construction

Elaboration:
1. Each template's `statisticalPlan` binds, per RQ slot: outcome type
   (continuous/ordinal/count/proportion), pairing structure
   (within/between/mixed), the exact test (from the NFR-8-compliant
   `analysis/stats.py` catalogue — Wilcoxon, Mann-Whitney+Cliff's δ,
   Fisher, Spearman; extended as templates demand), the effect size, the
   aggregation unit (per-participant first, against pseudo-replication),
   multiple-comparison posture, and small-n framing.
2. The plan compiles into the protocol's `analysisPlan` naming concrete
   recipes; missing recipes fail loudly at plan validation (FR-ANA-2) —
   a template cannot promise an analysis the platform can't run.
3. A **plan explainer** renders each choice in plain language with its
   why ("paired ordinal outcome, n<15 → exact Wilcoxon; report matched
   rank-biserial; never a bare p" — NFR-11 tone), citing
   `guidelines-empirical-llm-se` and the source paper's own analysis.
4. Deviations are allowed but recorded: a researcher overriding the
   prescribed test gets a grounded caution and the override lands in the
   protocol with `deviatesFromTemplate: true` (honesty over paternalism).

Fit criteria:
- F2.1 For each seed template, instantiate → run on demo data → the
  report's statistics lines match the plan's prescription exactly
  (test name, effect size, per-cell n present).
- F2.2 An override compiles with the deviation flag and surfaces in the
  report's methods text.
- F2.3 A template referencing a nonexistent recipe fails registry
  validation (not instantiation time — earlier).

### FR-TPL-3 (S) — The designer as review surface

*Rev 2:* the guided form of rev 1 is re-scoped: **the design
conversation (FR-CONV-1) is the primary designer**; the structured form
is the synchronized review surface over the same draft (parameter grid,
dataset-exists branch, slot completeness meter). Both surfaces edit one
draft; edits in either reflect in the other. The form alone remains a
complete no-LLM path (degradation posture, FR-CONV §5).

Fit criteria:
- F3.1 A parameter changed in the form appears in the conversation as a
  researcher design move; a conversationally accepted move updates the
  form live.
- F3.2 With no LLM key configured, the form path instantiates
  `ziegler-telemetry-survey-v1` end-to-end.

### FR-TPL-4 (S) — Templates live in the knowledge layer

Templates surface as first-class nodes in the literature graph linked to
their source papers; the assistant answers "how would I replicate
[paper]?" by retrieving the template (or proposing the nearest
`designType` match, labeled as adaptation, not replication). Fit: the
graph renders template nodes linked to cited papers; the assistant
exchange for a seeded paper returns its template with citation chips.

### FR-TPL-5 (C) — Community templates

Third-party templates enter through the same schema validation +
mandatory citation + review gate. Deferred; the contract exists
the moment FR-TPL-1's schema is published.

## 4. Paper grounding

`metr-early-2025-dev-productivity`, `copilot-productivity-ziegler`,
`copilot-productivity-rct-peng`, `hai-eval-human-ai-synergy`,
`speed-at-cost-of-quality-cursor` (seed designs);
`guidelines-empirical-llm-se` (methodological floor);
`realhumaneval`, `ai-agents-that-matter` (what honest evaluation
requires); `insecure-code-with-ai-assistants` (controlled-study
pattern); Stol & Fitzgerald ABC (design taxonomy).
