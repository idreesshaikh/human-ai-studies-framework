# Phase 22: The Design Recommender & Archetype Library (from a spoken idea to a runnable, grounded study)

> Self-contained: execute this file in a fresh session at the repo root.
> Read first: `docs/VISION.md`, `docs/roadmap/README.md` (the walls + the
> autonomy charter, both bind this phase), `requirements/specs/fr-tpl.md`
> (the template object model + statistical-plan discipline this extends),
> `requirements/specs/fr-conv.md` (the design conversation this recommends
> into: grounding, cite-what-you-retrieved, deterministic compile),
> `requirements/specs/fr-lit.md` (the idea→paper matching ladder this
> mirrors for templates), `requirements/glossary.md`,
> `analysis/src/analysis/stats.py` + `figures.py` (the tested test/chart
> primitives every prescription must draw from; nothing is invented here),
> `analysis/src/analysis/recipes/` (the recipe contract FR-ANA-1),
> `middleware/src/middleware/design_assistant.py` +
> `matching.py` + `template_registry.py` (the surfaces this extends).

**Depends on:** Phase 08 (analysis recipes + `stats.py`/`figures.py`, the
tested primitives), Phase 09 / FR-LIT-9 (the idea→paper matching ladder this
mirrors for templates), Phase 15 / FR-TPL (the template registry, object
model, and statistical-plan discipline), Phase 15 / FR-CONV-1/2/3 (the
design conversation, grounding, and the deterministic compiler this
recommends into). No dependency on the conductor arc (19–21); this is the
*design* side of the platform, they are the *capture* side.
**Satisfies:** FR-TPL-6 (grow the registry to ~two dozen grounded archetype
templates), FR-TPL-7 (ranked template recommendation from plain-language
intent), FR-ANA-8 (the shared analysis toolkit: parameterized recipes that
make templates cheap and bespoke designs runnable), FR-ANA-7 (ranked figure
suggestion), and **completes** FR-TPL-2 (correct statistics by construction,
now for *bespoke* designs too) and FR-TPL-4 (templates as navigable,
grounded knowledge). Extends FR-CONV-3 (the chosen analysis + figures
compile into the protocol and actually run ("Level 3").
**Elicited:** owner, 2026-07-19: *"grow archetypes to a few dozen that
capture the type of study an individual wants to do and scientifically
ground them… fetch from the best papers, most citations, recognised labs, so
they won't go stale… give a choice of analysis and post-analysis and what
test to run (recommend as a ranked list by preference when more than one) and
creates them for you… merge many designs and create something extraordinary
without any hallucination… I need a couple dozen ready-made designs to make
this work in a live demo."*
**Status:** 🔶 built: Slice A (parameterised recipes + figure forms + meta
wiring to runner) + Slice C (analysisPlan compiler for prescription+figure
moves) + design_assistant wired for prescription/figure suggestions; Wave-1
archetypes in registry; `prescribe.py` + `suggest_figures.py` complete.
Remaining: Slice B platform UI (ranked shortlist cards), verify scripts,
Slice D Wave-2 fill, NFR-12 evidence. See the deviations log below.

## The idea

Today the platform can *design* a study conversationally, but the "which
design, which statistics, which figure" knowledge is **scripted**: the
assistant hard-codes "suggest the METR template" for developer-study keywords
(`design_assistant.py`), there are **two** registry templates (plus two
drafts), no engine ranks *templates* by design fit, no path prescribes
statistics for a design that isn't already a template, and nothing suggests
figures at all. A researcher whose idea doesn't happen to match the one
scripted branch falls off the grounded path.

This phase makes the design side **real, general, and runnable**. A
researcher says, in their own words, *"I want to test whether AI makes junior
developers write riskier code than seniors."* The platform:

1. **Works out the study's shape**: word-matches the idea against the
   registry to pull candidate designs fast, then confirms the *structural
   signature* (two separate groups vs. the same people twice; a number vs. a
   rating vs. a yes/no; live vs. curated data) with a couple of plain
   questions (or infers it from the corpus/LLM when a key is present, then
   confirms). This is the FR-LIT-9 matching ladder, lifted from papers to
   templates.
2. **Recommends a design, honestly.** If a registry archetype fits, it names
   it with its grounding papers. If none does, it says so and offers a
   **bespoke design** built from the nearest archetype's pieces as individual
   grounded moves, never a silent guess.
3. **Prescribes the statistics as a ranked shortlist**: best-first, each a
   real test from the tested `stats.py` catalogue, each with a plain-language
   *why* and a citation, the researcher picking (defaults to the top). "Two
   separate groups, a numeric outcome, small n → **Mann-Whitney U + Cliff's
   δ** (primary); *t*-test (alternative, only if the numbers are
   approximately normal and groups larger)."
4. **Suggests the figure the same way**: a ranked shortlist of chart forms
   from the tested `figures.py` primitives, best-first (small-n numeric,
   two groups → a dot/strip plot that shows every point; a box plot as the
   alternative).
5. **Makes it real (Level 3).** On acceptance, the chosen test and figure
   compile deterministically into the protocol's `analysisPlan` as concrete,
   **runnable** recipes drawn from the shared toolkit, so once data lands,
   one run produces the real numbers and the real figure. The novelty is in
   the *combination*; every part is a tested, cited primitive. That is how
   the platform delivers "something extraordinary, without hallucination".

And it grows the library to the **couple-dozen archetypes** the demo needs,
made affordable precisely because the shared analysis toolkit (below) lets
each new template reuse tested recipes instead of shipping its own.

Non-negotiable bounds, inherited verbatim:

- **The protocol (YAML) is the sole document of record** (wall #1). The
  recommendation, the prescription, the figure choice all become **design
  moves** that compile into the protocol; they never *are* the protocol, and
  the compile step is a **pure function, no LLM in it** (wall, FR-CONV-3.1).
  The LLM only *proposes* grounded moves; the compiler produces YAML.
- **Grounding is retrieved, then claimed** (FR-CONV-2.2, FR-ETH-4). Every
  template recommendation, stat prescription, and figure suggestion carries
  grounding resolved *only* against sources the tools returned this exchange
  (corpus rows via `matching.get_paper_metadata`, template `source` refs, the
  methodological floor `guidelines-empirical-llm-se`), or is labelled
  `unsourced: your judgment`. Grep-the-output is a test, not a hope (F2.1).
- **No statistics or charts are invented.** A prescription may only name a
  test that exists in `stats.py` and a figure form that exists in
  `figures.py`; the LLM never writes fresh analysis code. A design that would
  need a test the platform doesn't hold is surfaced as an honest gap, not a
  fabricated recipe (the drafts-folder discipline, F2.3).
- **A template cannot promise an analysis the platform can't run** (F2.3).
  Every archetype added here validates through `validate_registry()`: schema
  + mandatory citation + every named recipe exists + every skeleton
  placeholder is a declared parameter. Archetypes whose recipes aren't built
  yet wait in `templates/drafts/`, exactly as today.
- **Honest statistics** (NFR-8). Exact tests, effect sizes, per-cell n;
  small-n framed as hypothesis-generating; a bare *p* never ships. A
  researcher may override a prescription, but the override lands in the
  protocol flagged `deviatesFromTemplate: true` with a grounded caution
  (honesty over paternalism, FR-TPL-2.4).
- **Everything degrades** (wall #9, FR-CONV §5). With no LLM key the
  recommender still runs: word-match + the shape questions (asked as a short
  structured form) + the deterministic prescription/figure tables produce a
  ranked design, stat plan, and figure with zero AI. The LLM, when present,
  only *reranks and phrases*: it adds no template, test, or figure the
  deterministic path didn't already surface (the FR-LIT-9 rung-1 contract).

## §0: Traceability spine, do this first

The execution model puts the traceability spine first. Before any code:

1. **Add the four requirement rows** to `requirements/srs.md` (FR-TPL-6,
   FR-TPL-7, FR-ANA-8, FR-ANA-7; full text in § Requirements) and their
   `requirements/traceability.md` §1 rows (status ⬜ until verified). **Edit
   in place, and flip the two rows this phase completes** (FR-TPL-2 and
   FR-TPL-4) only when their verification steps below are green (golden
   rule 3). Do not renumber any existing ID (golden rule 2).

2. **Add the glossary terms** (`requirements/glossary.md`): *Design
   archetype*, *Design shape*, *Bespoke design*, *Statistical prescription*
   (definitions in § Glossary additions). Keep using the established terms in
   code and schema (`template`, `recipe`, `condition`, `designType`,
   `measure`, golden rule 4).

3. **Add the tracker rows**: a new **"Study designer (22)"** heading in the
   phase tracker of `docs/roadmap/README.md`, this phase's row, status
   `⬜ specced`.

**No `build-vs-adopt` adoption row is needed:** every test and chart is built
on `scipy` + `matplotlib`, already adopted for exactly this purpose (decision
**D20**). Nothing new is adopted (NFR-10 satisfied by using what's here). **No
decision-ledger entry is needed**: this phase invents no new source of truth;
it generalises the scripted design assistant into a grounded engine.

## Slices

Ordering serves the demo: **Slice A is the foundation everything reuses**;
Slices B–C are the machinery; Slice D fills the library. A live demo exists
after **A + B + C + the first ~8 archetypes of D** (Wave 1); the rest of D
(Wave 2) is independent template authoring that enriches the demo.

### Slice A: The shared analysis toolkit (FR-ANA-8)

Python only (`analysis/`); nothing else changes until it lands. This is the
load-bearing rung: it makes bespoke designs *runnable* and templates *cheap*.

1. **Parameterised recipes** in `analysis/src/analysis/recipes/`, each a
   normal FR-ANA-1 recipe (declares `id`, `answers`, `requires`; emits
   tables, figures, methods text) but **not bound to one study's measures**:
   it reads which outcome column, which grouping/pairing key, and which
   figure form from its `analysisPlan` parameters. Built on the existing
   tested `stats.py` functions (no new statistics):
   - `two-group-nonparametric`: Mann-Whitney U + Cliff's δ over a
     between-condition split (wraps `stats.mann_whitney` + `stats.cliffs_delta`).
   - `paired-nonparametric`: Wilcoxon signed-rank + matched-pairs
     rank-biserial over a within-participant pairing (wraps
     `stats.wilcoxon_paired`).
   - `two-proportion`: Fisher's exact 2×2 + effect (wraps `stats.fisher_2x2`).
   - `correlation`: Spearman ρ (wraps `stats.spearman`).
   Each declares its `requires` in terms of *parameters* (the named outcome +
   keys), so FR-ANA-2's pre-collection validation still fires: a plan that
   points a recipe at a data element the protocol won't produce fails loudly.

2. **Figure forms** as a small, declared vocabulary each recipe can emit,
   backed by `figures.py` primitives (extend it where a form is missing:
   `strip_by_condition` and `paired_dots` already exist; add `box_by_condition`,
   `grouped_bar_proportion`, `scatter_fit` as thin, dataviz-disciplined
   wrappers). A recipe exposes which forms it supports and a default; the
   chosen form is a plan parameter.

3. **Tests** (`analysis/tests/`): each parameterised recipe run on demo data
   reproduces the exact `stats.py` result (same test name, effect size,
   per-cell n present); the `requires`-check fails a plan pointing a recipe at
   a missing element; a golden-file test pins each figure form's output
   (headless Agg, as FR-ANA already does).

### Slice B: The design-shape recommender (FR-TPL-7) + the prescription (FR-TPL-2, FR-ANA-7)

Middleware (`middleware/`) + platform (`platform/`). Extends
`matching.py`, `design_assistant.py`, `template_registry.py`, and the
conversation UI: no new subsystem.

1. **The design-shape signature**: a small, explicit structure the
   recommender reasons over (autonomy charter: internals free, the shape
   vocabulary lives in one named place):
   - `comparisonStructure`: `within-subjects | between-subjects | mixed |
     single-group | correlational | repository-mining` (this is the
     `designType` axis, generalised; Stol & Fitzgerald ABC per FR-TPL-1.3).
   - `outcomeType`: `continuous | ordinal | count | proportion | time-to-event`.
   - `dataPath`: `live | curated | either` (the FR-CUR branch).
   Registry templates **declare their shape** (derive
   `comparisonStructure` from `designType`, `outcomeType` from `measures`,
   `dataPath` already exists), no new authoring burden on the two existing
   templates beyond a derived read.

2. **The template-matching ladder** (mirrors `matching.match_papers`, same
   degrade-never-block posture):
   - Rung 2 (floor): word-match the idea against each template's
     `title + description + designType + measure descriptions` (reuse the FTS
     term logic), producing candidate archetypes with matched-term reasons.
   - Shape confirm: the platform asks the shape questions as short,
     individually-answerable turns (or, with a key, infers the signature from
     the idea + candidates and asks the researcher to confirm, never assumes).
   - Rank: score candidates by shape distance to the confirmed signature;
     above a named threshold → **no fit → bespoke** (honest degradation, not a
     forced match).
   - Rung 1 (optional): LLM rerank/phrase over the *already-retrieved*
     candidates only, adds no template (the FR-LIT-9 contract).

3. **The statistical prescription** (`prescribe.py`, deterministic): a
   named lookup keyed by `(comparisonStructure, outcomeType)` → an **ordered**
   list of `{test, effectSize, why, grounding, caveat}`, best-first, each
   `test` a real `stats.py` function and each grounding a resolvable ref
   (`guidelines-empirical-llm-se` + the design's source paper). Examples:
   - between × continuous/ordinal → **Mann-Whitney U + Cliff's δ** (primary);
     *t*-test (alt, caveat: assumes approximate normality + larger groups).
   - within × continuous/ordinal → **Wilcoxon signed-rank + matched-pairs
     rank-biserial** (primary); paired *t* (alt, same caveat).
   - between × proportion → **Fisher's exact** (primary; exact, small-n safe).
   - correlational → **Spearman ρ** (primary); Pearson (alt, caveat:
     assumes linearity). small n is always framed hypothesis-generating
     (NFR-8). A design whose `(structure, outcome)` has no catalogue entry
     yields an **honest "no prescription: needs a test we don't hold"**, never
     a fabricated one.

4. **The figure suggestion** (`suggest_figures.py`, deterministic, FR-ANA-7):
   a named lookup keyed by `(comparisonStructure, outcomeType, smallN)` → an
   **ordered** list of figure forms from Slice A's vocabulary, best-first with
   a plain *why* (small-n numeric two-group → dot/strip-by-condition primary,
   "shows every point, honest when n is small"; box-by-condition alt).
   Grounded in the `dataviz` conventions (D20) and NFR-12's one-token-system.

5. **The platform turn shape.** `design_assistant.respond` returns, alongside
   today's `{text, moves, recommendations, retrievedRefs}`, the ranked
   `templateMatches`, and (carried on the relevant design moves) the ranked
   `prescription` and `figureSuggestions`, each item individually decidable.
   The scripted branches (`_over_trust_script` etc.) are **replaced** by this
   engine; the no-LLM path stays real (it *is* the deterministic engine).

6. **UI** (`platform/`, extends the conversation surface, NFR-12): the ranked
   shortlists render as accept/reject cards with the top option pre-selected,
   each carrying its grounding chips (or the `unsourced` label) and its plain
   *why*; a `bespoke` recommendation renders its "nearest archetype +
   grafted grounded moves" honestly. Both-theme, reduced-motion, axe-clean,
   keyboard-complete selection. Chunked into individually-decidable cards,
   never a prose wall (`im-not-reading-all-of-that`).

### Slice C: Level 3, the chosen analysis compiles in and runs (FR-CONV-3 ext)

Middleware compiler (`middleware/src/middleware/compiler.py`) + protocol.

1. **Compile the prescription.** An accepted stat-prescription move compiles
   deterministically into the protocol's `analysisPlan`: the picked test
   becomes a concrete entry naming a **Slice-A parameterised recipe** with its
   parameters (outcome column, grouping/pairing key, chosen figure form), plus
   the effect size and small-n framing. An override compiles with
   `deviatesFromTemplate: true` and the grounded caution in the methods text
   (FR-TPL-2.4). No LLM in the compile (wall, FR-CONV-3.1).
2. **Compile the figure.** The picked figure form rides the same
   `analysisPlan` entry as a `figure` parameter the recipe reads: figures are
   a property of the chosen recipe (FR-ANA-1 already emits figures), so this
   is a small parameter, **not a new protocol schema block**.
3. **Validate on compile** (FR-CONV-3.3): `protocol validate` + the FR-ANA-2
   `requires` pre-check run on every compile; a plan naming a recipe whose
   data the protocol won't produce bounces back into the thread as a platform
   turn naming the defect: a conversation cannot silently produce an
   un-runnable plan.
4. **It actually runs.** The end state: a bespoke study reaches a validating
   protocol whose `analysisPlan` the existing `analysis` runner executes to a
   real report + figure once data lands, the "magic", assembled entirely from
   tested, cited parts.
5. **Tests** (`middleware/tests/`): replaying accepted prescription+figure
   moves against a base draft yields a byte-identical protocol (determinism,
   F3.1); the compiled `analysisPlan` runs green on demo data producing the
   prescribed test's report lines + the chosen figure; an override lands the
   deviation flag in the methods text (F2.2); a prescription pointing at
   absent data bounces at compile (F3.2); grep-the-output: no move cites a ref
   absent from its exchange's `retrievedRefs` (F2.1).

### Slice D: The archetype library (FR-TPL-6, completes FR-TPL-4)

Template authoring (`templates/`) + knowledge-layer wiring. Independent,
parallelisable work; **Wave 1 = the first ~8** (the demo subset, **Must**),
**Wave 2 = up to ~24** (the fill, **Should**).

1. **Author ~two dozen archetype templates**, each encoding one *published*
   design, citing its paper(s), spanning the common shapes so the recommender
   almost always lands on a real archetype rather than bespoke. Wave-1 spread
   (one per dominant shape, so the demo covers the space): within-subjects
   RCT (exists: `metr-rct-v1`), between-subjects RCT, mixed-design, telemetry
   + survey (exists: `ziegler-telemetry-survey-v1`), repository-mining
   velocity/quality (draft: `cursor-mining-v1`), survey/self-report only,
   observational/field, benchmark + real-task. Wave-2 fills sub-variants
   (longitudinal, correlational, 2×2 factorial, single-group pre/post, …).
   Each **reuses Slice-A parameterised recipes** in its `analysisPlan`, that
   is what makes two dozen affordable, and each passes `validate_registry()`
   before entering `templates/registry/` (drafts wait in `templates/drafts/`
   per the F2.3 discipline).
2. **Quality-first sourcing** (owner elicitation; FR-LIT-8 posture): pick each
   archetype's source design from the corpus by the same quality signals the
   harvest already records: citations, influential citations, recognised
   venue/lab, freshness, so the library "won't go stale". This phase
   *consumes* those signals; the **standing self-updating harvest that keeps
   them fresh is deliberately out of scope here** (it is sub-project 1 of the
   owner's arc, its own future phase); Slice D is a curated authoring pass
   over the corpus as it stands, not a scheduler.
3. **Templates as navigable knowledge** (completes FR-TPL-4): wire template
   nodes into the literature graph linked to their `source` papers; the
   assistant answers "how would I replicate [paper]?" by retrieving the
   template (or the nearest-`designType` match, labelled *adaptation*, not
   replication). Fit: the graph renders template nodes with citation chips;
   the exchange for a seeded paper returns its template.

## API surface (additions / changes)

```
# design_assistant.respond return gains (same endpoint, richer payload):
#   templateMatches: [{templateId, title, score, designType, matchReason, grounding[]}]
#   prescription:    ordered [{test, effectSize, why, grounding[], caveat, unsourced?}]   (on stat moves)
#   figureSuggestions: ordered [{form, why, grounding[]}]                                  (on figure moves)
POST .../conversation/compile   now compiles accepted prescription+figure moves into analysisPlan (deterministic; validated)
GET  /studies/{id}/templates/match?idea=…   ranked archetype matches for an idea (the recommender, callable directly)
GET  /templates                              registry listing gains designType/shape + source grounding for graph wiring
# analysis: new parameterised recipes registered: two-group-nonparametric,
#           paired-nonparametric, two-proportion, correlation
```

## Requirements (added to `srs.md` + `traceability.md` in §0)

- **FR-TPL-6 (M for the demo subset; S for the full fill)**: The registry
  SHALL grow to **~two dozen archetype templates**, each encoding one
  *published* study design, citing its source paper(s), and spanning the
  common **design shapes** (comparison structure × outcome type × data path)
  so a researcher's idea usually maps to a real archetype. Each SHALL reuse
  the shared analysis toolkit (FR-ANA-8) in its analysis plan and SHALL pass
  `validate_registry()` before entering the registry (drafts wait per F2.3).
  Source designs SHALL be chosen by the corpus's recorded quality signals:
  citations, recognised venue/lab, freshness (FR-LIT-8), so the library does
  not go stale. *Traces to:* owner elicitation 2026-07-19; S7; RQ-F3.
- **FR-TPL-7 (M)**: The platform SHALL **recommend a design from
  plain-language intent**: word-match the idea against the registry to pull
  candidate archetypes, confirm the study's **design shape** (comparison
  structure, outcome type, data path) via short questions or LLM inference
  (researcher-confirmed), rank candidates by shape fit, and, when none fits
  above a threshold, offer a **bespoke design** from the nearest archetype's
  pieces as individually-grounded moves, never a silent guess. The recommender
  SHALL degrade to a fully deterministic path with no LLM key; the LLM, when
  present, reranks and phrases only, adding no template (FR-LIT-9 contract).
  *Traces to:* owner elicitation 2026-07-19; S7; RQ-F1/F3; FR-CONV-1/2;
  FR-LIT-9.
- **FR-ANA-8 (M)**: The framework SHALL provide a **shared analysis toolkit**:
  parameterised recipes (two-group nonparametric, paired nonparametric,
  two-proportion, correlation) built on the tested `stats.py` catalogue and
  the `figures.py` primitives, not bound to one study's measures but pointed
  at named outcome/grouping/pairing keys via the analysis plan, so any
  design, template or bespoke, gets a **runnable** analysis, and templates
  share tested recipes instead of each shipping its own. Each SHALL honour the
  FR-ANA-1 recipe contract and the FR-ANA-2 `requires` pre-check. *Traces to:*
  RQ-F3; S1,S4,S6; owner elicitation 2026-07-19 ("creates them for you").
- **FR-ANA-7 (S)**: The platform SHALL **suggest figures as a ranked
  shortlist** keyed by the design shape and sample-size posture, best-first
  with a plain rationale, drawn only from the tested `figures.py` vocabulary
  (dataviz conventions, NFR-12 one-token-system). The chosen form SHALL
  compile into the analysis plan as a recipe parameter (not a new schema
  block) and render in the report. *Traces to:* RQ-F2; owner elicitation
  2026-07-19 ("suggestion best figures to show their outcomes"); D20; NFR-12.

**Completed by this phase (flip on green, golden rule 3):**

- **FR-TPL-2** → correct statistics by construction now covers **bespoke**
  designs: the deterministic prescription table gives a ranked, grounded,
  overridable stat plan for any design shape, compiled into the protocol.
- **FR-TPL-4** → templates surface as navigable, grounded knowledge-graph
  nodes linked to their source papers; "replicate this paper" returns the
  template or a labelled adaptation.

## Glossary additions

| Term | Definition |
| ---- | ---------- |
| **Design archetype** | A study design *shape* that many papers share: the merge key that makes a finite template set cover an unbounded literature. Identified by its **design shape**; realised as a registry template. *(not: study type; an archetype is structural, a study is one instance.)* |
| **Design shape** | The structural signature the recommender matches on and the prescription is keyed by: **comparison structure** (within/between/mixed/single-group/correlational/repository-mining) × **outcome type** (continuous/ordinal/count/proportion/time-to-event) × **data path** (live/curated). Topic lives in the *parameters*, not the shape. |
| **Bespoke design** | A study design with no registry archetype fitting above threshold, built from the nearest archetype's pieces as individually-grounded design moves; still compiles to a valid, runnable protocol. *(not: custom study; "bespoke" names the no-template path specifically.)* |
| **Statistical prescription** | The ranked, best-first shortlist of tests (each a tested `stats.py` primitive, with effect size, plain rationale, grounding, and caveat) the platform recommends for a design shape; the researcher picks, overrides land flagged. *(not: the statistical plan; the *prescription* is the ranked recommendation, the *plan* is what compiles into the protocol.)* |

**Build-vs-adopt:** no adoption. `scipy` + `matplotlib` (D20), the existing
recipe/matching/compiler machinery, and Python built-ins only (NFR-10).

## Degrees of freedom

- **Shape-distance metric**: any explicit, testable scoring of a candidate
  archetype against the confirmed signature (weighted field agreement is
  fine); the no-fit threshold is a named constant in one place.
- **Shape-question flow**: number and order of the confirm questions, and
  whether the LLM pre-fills them; must never *assume* an unconfirmed shape.
- **Prescription/figure tables**: the exact catalogue rows, as long as every
  `test` resolves to a `stats.py` function, every `form` to a `figures.py`
  primitive, and every row carries grounding or is honestly unsourced.
- **Card layout** for the ranked shortlists, within NFR-12's registers;
  top option pre-selected, each individually decidable.
- **Archetype spread**: which published designs fill Wave-1's ~8 vs Wave-2,
  provided Wave-1 covers the dominant shapes end-to-end and each is grounded
  in a quality-signalled source paper.

## Acceptance (maps to fit criteria)

- FR-TPL-7: from an empty study, a plain-language idea reaches a ranked design
  recommendation (archetype or honest bespoke) **without leaving the
  conversation**; each option is an individually-decidable card carrying
  grounding or the `unsourced` label; with no LLM key the same idea still
  yields a ranked design via the deterministic path.
- FR-TPL-2 (bespoke): a between-groups numeric idea receives **Mann-Whitney +
  Cliff's δ** as the top prescription with a *t*-test alternative and its
  caveat, each grounded; overriding to *t* compiles with `deviatesFromTemplate`
  and the caution in the methods text.
- FR-ANA-8: each parameterised recipe run on demo data reproduces its
  `stats.py` result exactly (test name, effect size, per-cell n present); a
  plan pointing a recipe at a missing data element fails the FR-ANA-2 check.
- FR-ANA-7: a ranked figure shortlist appears for the design; the picked form
  compiles into the plan and the runner emits that figure in the report.
- FR-CONV-3 (Level 3): replaying accepted prescription+figure moves yields a
  byte-identical protocol; that protocol validates and the `analysis` runner
  executes its plan to a real report + figure on demo data.
- FR-TPL-6: ≥ 8 archetype templates (Wave 1) validate through
  `validate_registry()` and instantiate into protocols that pass
  `protocol validate` with zero hand edits, each citing a quality-signalled
  source paper; the recommender lands a representative idea on each.
- FR-TPL-4: the knowledge graph renders template nodes linked to their source
  papers; a seeded paper's "replicate this" returns its template.
- Grep-the-output (F2.1): no move in a recorded recommendation+compile session
  carries a citation absent from that exchange's `retrievedRefs`.
- NFR-12: both-theme + reduced-motion screenshots of the ranked-shortlist
  cards and the bespoke recommendation; axe clean; keyboard-only selection.

## Verification steps

1. `uv run pytest && uv run ruff check .`: parameterised-recipe result
   parity, `requires`-check failure, figure golden files, prescription/figure
   table coverage, compiler determinism + validate-on-compile + override flag,
   grep-the-output grounding test, `validate_registry()` for every new
   archetype.
2. `platform/`: `npm run check` green, covering ranked-shortlist cards, bespoke
   rendering, keyboard/axe checks; no-raw-literal rule green.
3. End-to-end walkthrough, recorded: a plain-language idea → ranked design
   (archetype and, on a deliberately unusual idea, honest bespoke) → ranked
   stat prescription (pick + override) → ranked figure → compile → the
   resulting protocol validates and the runner produces the prescribed report
   line + chosen figure on demo data.
3b. Re-run the walkthrough with `MISTRAL_API_KEY` unset: the deterministic
   path yields a ranked design, prescription, and figure with no AI (FR-CONV
   §5 degradation).
4. NFR-12 evidence archived for the new surfaces.
5. Confirm the four new traceability rows are added and the two completed
   rows (FR-TPL-2, FR-TPL-4) plus the Phase 22 tracker row are flipped only
   after 1–4 are green (golden rule 3).

## How this fits the platform (the anti-"side-feature" check)

Every piece is the *same* design conversation continuing, not a new
subsystem beside it:

- The **recommender** is the FR-LIT-9 matching ladder pointed at templates
  instead of papers, same rungs, same cite-what-you-retrieved, same
  degrade-never-block posture.
- The **prescription** and **figure suggestion** are deterministic tables over
  primitives that already exist and are already tested (`stats.py`,
  `figures.py`), the platform recommends only what it can actually run.
- The **compile** is the existing FR-CONV-3 pure function, now covering two
  more move kinds; the protocol stays the sole document of record, the LLM
  stays out of the compiler, "no hallucination" is structural.
- The **archetypes** grow the library the recommender reasons over, each a
  cited published design that reuses the shared toolkit, the finite template
  set covering the unbounded literature, exactly the owner's model.
- Remove the LLM, the network, the dashboard: the deterministic recommender +
  the CLI runner still take an idea to a runnable, grounded study (wall #9).

This phase is **the design half of the owner's three-part arc**
(recommender → composable designs → self-updating library): it ships the
recommendation-first surface and leaves the deep multi-design *merge* (one
composed statistical plan from two archetypes) and the *standing
self-updating harvest* to their own future phases, named here so they are not
mistaken for gaps.

## Deviations log

Record departures here and in `requirements/traceability.md` §3 as they
occur.
