# Template Mining Guide

Phase 4: Growing the registry from 13 shapes to ~100 by mining the corpus for recurring design patterns.

## Overview

The mining process automatically discovers design shapes used in papers across the 15,000-paper corpus, generates draft templates, and validates them. It does NOT require manual curation  -  the automation ensures every template is valid, citable, and grounded.

## Running the Miner

```bash
python -m middleware mine-designs
```

This will:
1. Analyze titles and abstracts of every paper in the corpus
2. Extract design vocabulary (phrases like "between-subjects", "survey", "replicated")
3. Cluster papers by their design characteristics
4. For each cluster with 3+ papers, draft a template YAML
5. Validate each draft (schema, recipe existence, parameter consistency)
6. Write passing drafts to `templates/drafts/` as `.yaml` files
7. Report results: count by validity, and details per cluster

## Understanding the Output

Each mined design gets an ID like `mined-design-01-v1`, `mined-design-02-v1`, ranked by corpus frequency (most papers first).

**Sections in the report:**

- **Valid (✓):** Draft passes schema validation, recipes exist, and citations resolve.
- **Invalid (✗):** Draft has problems (usually missing recipe, or unresolved paper reference).

Each entry shows:
- Paper count (how many corpus papers use this design)
- Phrases (the design signatures discovered)
- Any validation problems (first 2 listed)

## What Happens After Mining

1. **Review drafts** in `templates/drafts/`: Each is a real design from real papers.
2. **Auto-promote valid drafts**:
   ```bash
   python -m middleware promote-templates
   ```
   This moves all passing drafts to `templates/registry/` and re-validates the full registry. Non-passing drafts stay in `drafts/` for manual review.
3. **Adjust analysis plans** if needed: A promoted template may have a recipe chosen conservatively (e.g., always `two-group-nonparametric` for between-subjects designs). Refine to a more specific recipe if the design warrants it.
4. **Re-validate** before shipping: `python -m middleware templates` must report zero problems.

## Design Signature Discovery

The miner looks for ~60 design keywords extracted from methodology literature:

- **Between-subjects designs:** "between-subjects", "control group", "treatment group", "randomly assigned"
- **Within-subjects designs:** "within-subjects", "counterbalanced", "crossover"
- **Study types:** "observational", "field study", "survey", "experiment"
- **Sample structures:** "single-arm", "benchmark", "multi-arm"
- **Measurement:** "behavioral", "telemetry", "self-report", "assessment"
- **Analysis:** "qualitative", "quantitative", "mixed-methods", "descriptive"
- **Data properties:** "longitudinal", "cross-sectional", "replicated"

A paper is included in a cluster if any of its discovered phrases are exact matches (whole-token, case-insensitive) in the title or abstract.

## Validation Gates

**Schema validation** ensures each draft is structurally sound:
- Required fields present
- Parameter types, defaults, bounds consistent
- Placeholders match declared parameters
- analysisPlan names existing recipes

**Citation resolution:** Every paper in a draft's `source[].paperRef` must exist in the corpus. If a paper is referenced but missing, the draft is rejected (not published with an unresolved citation).

**Admission thresholds** (post-validation, automatic ranking):
- Common: ≥100 papers
- Established: ≥25 papers
- Rare: 3–24 papers (admitted only if sourced well)

**Rare-design gates:** A rare design is admitted if:
- Backed by 3+ distinct corpus papers, OR
- The highest-confidence paper cites it at ≥0.75 confidence (high-quality match)

## Retuning Bands

The thresholds above (`COMMON_SUPPORT`, `ESTABLISHED_SUPPORT`, `RARE_SUPPORT_FLOOR`, `RARE_ADMISSION_CONFIDENCE`) are currently calibrated for a 13-template repertoire.

With ~100 templates, check if the distribution is sensible:
- Should Established move from 25 → 50 papers to keep that tier meaningful?
- Should RARE_ADMISSION_CONFIDENCE increase to raise the bar for dubious designs?

If so, edit `template_repertoire.py` and re-rank: `python -m middleware templates`.

## Troubleshooting

**"Recipe X does not exist"**
- The template names a recipe not in the analysis catalogue
- Either add the recipe to `analysis/src/analysis/recipes/`, or adjust the template's analysisPlan

**"Unresolved paperRef"**
- A template cites a paper (via DOI or arXiv ID) that isn't imported yet
- Either import more papers, or remove the citation from the template

**No drafts generated**
- The corpus may have no papers (did corpus-import run?)
- Or all clusters have <3 papers (increase `min_papers` threshold in `mine_and_draft()`)
- Check corpus size: `SELECT COUNT(*) FROM papers WHERE study_id = 'corpus'`

## Example: Promoting a Draft

1. Run `python -m middleware mine-designs`
2. See `mined-design-01-v1` is valid, 87 papers, covers "two-group-rct"
3. Review `templates/drafts/mined-design-01-v1.yaml`
4. Optionally adjust the template (e.g., pick a more specific recipe than the conservative default)
5. Move to registry: `mv templates/drafts/mined-design-01-v1.yaml templates/registry/`
6. Verify: `python -m middleware templates` (must show zero problems)
7. Stage and commit: `git add templates/registry/mined-design-01-v1.yaml`

## Cost & Scale

Mining the full 15,000-paper corpus runs in ~10s (one pass, regex on title + abstract). No API calls, no external services. Draft generation is instant (template creation is O(1) per cluster).

Validation happens offline (`validate_template()` is pure, uses only local data).

The process is safe to re-run anytime.
