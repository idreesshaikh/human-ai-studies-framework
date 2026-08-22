# Registry templates (15 so far, meant to keep growing)

A **template** encodes one proven, *generic* study design: a design
**shape** (its structure, its prescribed statistics, its required
instruments), so a researcher can instantiate it into a valid protocol
with zero hand edits.

A template is **not a replica of one paper**. The papers that used a shape
attach to it as ranked **references**: each template declares a curated
`designSignature` (the phrases a paper using this design says about itself),
and the repertoire counts how many corpus papers above the confidence gate
carry them. That count is the shape's **support**, and it ranks the registry
**common → rare**: the current corpus spans ~13 papers (2×2 factorial) to
~1,700 (benchmark evaluation). A shape too rare to be well-attested is
admitted only when its strongest reference clears the confidence gate, and
is shown with that reason rather than hidden. See
`middleware/src/middleware/template_repertoire.py`; the ranking is
deterministic (no LLM), so any number here is countable by hand.

Shapes compose: selecting two or more and merging produces one novel
protocol still grounded in every paper it draws from; that, not
replication, is the point of the registry.

The registry is designed as an **expandable library**: the published
literature holds hundreds of distinct designs, and each becomes a template
as its recipes and instruments come online. Thirteen templates ship today,
in four layers:

**The original two seeds** (Phase 15, proved the mechanism itself):
- **metr-rct-v1**: the METR early-2025 developer-productivity RCT
  (arxiv:2507.09089): within-subjects, objective outcomes + perception.
- **ziegler-telemetry-survey-v1**: the Ziegler acceptance-rate
  telemetry-plus-survey design (arxiv:2205.06537).

**Wave 1 of the design-archetype library** (Phase 22, FR-TPL-7, the
~8-archetype spread the design recommender's demo needs so a researcher's
idea usually maps to a real archetype rather than a bespoke design):
- **two-group-rct-v1**: two-group between-subjects RCT.
- **within-subjects-crossover-v1**: within-subjects crossover
  (arxiv:2507.09089).
- **paired-pre-post-v1**: paired pre/post intervention.
- **multi-arm-rct-v1**: multi-arm RCT.
- **factorial-2x2-v1**: 2×2 factorial design.
- **single-group-repeated-measures-v1**: single-group repeated measures
  (3+ time points).
- **two-proportion-mcnemar-v1**: two-proportion comparison.
- **single-arm-benchmark-v1**: single-arm benchmark evaluation.

**Promoted from `templates/drafts/`** (2026-07-21, its blocking recipes
now exist in the analysis catalogue):
- **hai-eval-synergy-v1**: the HAI-Eval within-subject human/AI/human-AI
  synergy comparison (arxiv:2507.09089).

**Wave 2, first fill** (2026-07-21, the two design shapes that were on
the *original* Wave-1 spread list but never actually got built):
- **survey-self-report-v1**: self-report-only design, no objective
  performance measure at all (`corpus:ai-assistants-in-practice`).
- **observational-field-v1**: single-condition, no-manipulation field
  study describing real in-situ AI-assisted work, purely descriptive
  (`arxiv:2506.12347` / `corpus:sharp-tools-agentic-ai`), distinct from
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

**Wave 2, second fill** (real corpus gaps, found by scanning for
methodology clusters no existing `designSignature` matched at all  -  see
`scripts/mine_templates.py` below for the systematic version of that
same search):
- **field-experiment-v1**: a real manipulation run inside participants'
  actual ongoing work rather than a controlled lab session  -  distinct
  from both `observational-field-v1` (no manipulation at all) and
  `two-group-rct-v1` (a controlled setting). Grounded in "The Cybernetic
  Teammate" field experiment (`doi:10.2139/ssrn.5207588`).
- **cognitive-load-comparison-v1**: the one existing analysis recipe no
  template had ever named (`fatigue-by-condition`)  -  for studies whose
  actual research question is cognitive load itself, not task outcome
  with workload as a side measure. Grounded in "When Help Hurts:
  Verification Load and Fatigue with AI Coding Assistants"
  (`corpus:when-help-hurts-verification-load-fatigue`).

Wave 1's archetypes are grounded in `corpus:guidelines-empirical-llm-se`
(the empirical-SE-with-LLMs guidance paper); each also carries its own
design-specific citation where one applies. **Wave 2** (up to ~24
archetypes total, per Phase 22's spec) is independent template-authoring
work that enriches the demo, in progress (15/~24). Beyond Wave 2,
`scripts/mine_templates.py` is the automated front half of growing the
registry past what the owner hand-authors alone:

- `--gaps` reports **methodology phrases the corpus uses that no template
  here claims**  -  the registry's blind-spot list, ranked by how many
  corpus papers use each. It anchors on the head noun of a phrase
  ("… *study*", "… *experiment*", "… *evaluation*") rather than on a list
  of known methods, which is what lets it surface archetypes nobody
  thought to name; a fixed keyword table can only re-find its own
  entries. This is the automated form of the manual scan that found
  `field-experiment-v1` and `cognitive-load-comparison-v1`. A row is
  evidence, **not** a template: read the papers behind a phrase, and
  judge whether it is genuinely distinct from the shapes already here
  before authoring one. (The current top row, "case study" at 78 papers,
  is exactly such a judgment call against `observational-field-v1`  -  do
  not simply bolt the phrase onto an existing signature, which would
  claim those papers for a design they did not use.)
- With no flag it clusters the corpus by recurring design vocabulary and
  reports what it found; with `--write` it writes the clusters with real
  support into `../drafts/` as YAML, never into this directory directly.
  Its drafting vocabulary is coarse by design  -  a mined draft is a
  proposal, and promoting one into this directory is a human decision made
  by reading the YAML and committing it. Nothing mined is promoted
  automatically.

A template enters this directory only once `validate_registry()` passes
for it (schema, mandatory citations, every recipe exists, and every
skeleton placeholder is a declared parameter). Designs whose dependencies
aren't built yet wait in `../drafts/`.

## A template is not a study

Templates are platform library content. A **study**, including the
owner's trial studies that prove the platform works, is a protocol
instance in `protocol/examples/`, authored via the design conversation.
A study *may* start from a template, but it does not have to, and it is
never itself a template. There is no template-per-study expectation: the
library grows with the *literature*, not with the studies run here.
