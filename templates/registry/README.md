# Registry templates (13 so far, meant to keep growing)

A **template** encodes one proven, *generic* study design — a design
**shape** (its structure, its prescribed statistics, its required
instruments) — so a researcher can instantiate it into a valid protocol
with zero hand edits.

A template is **not a replica of one paper**. The papers that used a shape
attach to it as ranked **references**: each template declares a curated
`designSignature` (the phrases a paper using this design says about itself),
and the repertoire counts how many corpus papers above the confidence gate
carry them. That count is the shape's **support**, and it ranks the registry
**common → rare** — the current corpus spans ~13 papers (2×2 factorial) to
~1,700 (benchmark evaluation). A shape too rare to be well-attested is
admitted only when its strongest reference clears the confidence gate, and
is shown with that reason rather than hidden. See
`middleware/src/middleware/template_repertoire.py`; the ranking is
deterministic (no LLM), so any number here is countable by hand.

Shapes compose: selecting two or more and merging produces one novel
protocol still grounded in every paper it draws from — that, not
replication, is the point of the registry.

The registry is designed as an **expandable library**: the published
literature holds hundreds of distinct designs, and each becomes a template
as its recipes and instruments come online. Thirteen templates ship today,
in four layers:

**The original two seeds** (Phase 15 — proved the mechanism itself):
- **metr-rct-v1** — the METR early-2025 developer-productivity RCT
  (arxiv:2507.09089): within-subjects, objective outcomes + perception.
- **ziegler-telemetry-survey-v1** — the Ziegler acceptance-rate
  telemetry-plus-survey design (arxiv:2205.06537).

**Wave 1 of the design-archetype library** (Phase 22,
`docs/roadmap/22-design-recommender.md`, FR-TPL-7 — the ~8-archetype
spread the design recommender's demo needs so a researcher's idea usually
maps to a real archetype rather than a bespoke design):
- **two-group-rct-v1** — two-group between-subjects RCT.
- **within-subjects-crossover-v1** — within-subjects crossover
  (arxiv:2507.09089).
- **paired-pre-post-v1** — paired pre/post intervention.
- **multi-arm-rct-v1** — multi-arm RCT.
- **factorial-2x2-v1** — 2×2 factorial design.
- **single-group-repeated-measures-v1** — single-group repeated measures
  (3+ time points).
- **two-proportion-mcnemar-v1** — two-proportion comparison.
- **single-arm-benchmark-v1** — single-arm benchmark evaluation.

**Promoted from `templates/drafts/`** (2026-07-21 — its blocking recipes
now exist in the analysis catalogue):
- **hai-eval-synergy-v1** — the HAI-Eval within-subject human/AI/human-AI
  synergy comparison (arxiv:2507.09089).

**Wave 2, first fill** (2026-07-21 — the two design shapes that were on
the *original* Wave-1 spread list but never actually got built; see
`docs/roadmap/22-design-recommender.md` §Slice D):
- **survey-self-report-v1** — self-report-only design, no objective
  performance measure at all (`corpus:ai-assistants-in-practice`).
- **observational-field-v1** — single-condition, no-manipulation field
  study describing real in-situ AI-assisted work, purely descriptive
  (`arxiv:2506.12347` / `corpus:sharp-tools-agentic-ai`) — distinct from
  `single-arm-benchmark-v1`, which evaluates its single arm against an
  external benchmark rather than just describing behavior.

Every other Wave-1 gap item (mixed-design, repository-mining
velocity/quality, benchmark + real-task) turned out to already be covered
or blocked on something other than template-authoring: `quasi-experiment`
is already served by `paired-pre-post-v1` /
`single-group-repeated-measures-v1`; "mixed-design" has no matching
`designType` enum value yet (a schema change, not a template-authoring
task); repository-mining (`cursor-mining-v1`) is blocked on real
repository-trend recipes, not on template YAML (see
`templates/drafts/README.md`). Two honest additions, not a padded count.

Wave 1's archetypes are grounded in `corpus:guidelines-empirical-llm-se`
(the empirical-SE-with-LLMs guidance paper); each also carries its own
design-specific citation where one applies. **Wave 2** (up to ~24
archetypes total, per Phase 22's spec) is independent template-authoring
work that enriches the demo — in progress (13/~24). Beyond Wave 2,
FR-TPL-5 (community template contribution,
`docs/roadmap/24-import-extensibility-tail.md`) is the intended path for
growing the registry past what the owner hand-authors alone.

A template enters this directory only once `validate_registry()` passes
for it (schema, mandatory citations, every recipe exists, and every
skeleton placeholder is a declared parameter). Designs whose dependencies
aren't built yet wait in `../drafts/`.

## A template is not a study

Templates are platform library content. A **study** — including the
owner's trial studies that prove the platform works — is a protocol
instance in `protocol/examples/`, authored via the design conversation.
A study *may* start from a template, but it does not have to, and it is
never itself a template. There is no template-per-study expectation: the
library grows with the *literature*, not with the studies run here.
