# Measure mapping experiment

The experiment tooling runs on synthetic fixtures. The product uses the 20-class software
catalog as read-only, uncalibrated proposals requiring researcher confirmation.
No empirical model comparison, independent human labels or real test split exists.

`catalog/catalog.v1.json` is a model-authored proposal with
source paths, descriptions and illustrative examples. Its hash records this draft
revision; it is not evidence of approval or an experimental freeze. Recipe lookup
by construct and design is proposed, rather than a validated product mapping.
S10 is an unvalidated covariate. Static code metrics and first-green timing must
not be interpreted as mental load, substantive correctness or total active time.

`scripts/build_seed.py` labels repository phrases with an explicit hand-authored
construct table. Output in `data/seed/` records `labelProvenance=llm-draft`, source
locations, reasons, review confidence and `adjudicated=false`. Every row is training
only. Confidence 1–3 is a subjective review aid, not a calibrated probability.
Generic/unsupported mentions remain `none` and appear in `unmapped.txt`. Recipe
titles naming only tests or designs are omitted under annotation rule 11.

Single-label kappa is undefined, as specified in the
[scikit-learn definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html).
Agreement reports return null for it; bootstrap intervals are withheld when a
resample makes the statistic undefined or there are fewer than two source clusters.

Pending for empirical research: an independent second annotator, recorded
preregistration, and at least 100 independent real test items. No trained decision
model has been selected for the product.
Repo and generated seed text is training only; calibration/test require human
provenance. A confidence threshold answers tied confidence values together.
Equal-mass ECE still splits ties by input order; use equal-width bins with ties.
Keyword scores still require calibration. `coverage_at_risk` describes the empirical
evaluation curve; it must not select a deployed threshold using test labels.

Run `PYTHONPATH=experiments/measure_mapping uv run --package analysis pytest
experiments/measure_mapping/tests -q -p no:cacheprovider` from the repository root.
This experiment adds no workspace dependencies. Product authoring lives separately
in `protocol.measure_catalog` and the existing compiler and setup dialog.
`scripts/make_splits.py` writes train/calibration files and a hash-locked test file
outside the working tree. `scripts/run_baseline.py` fits prior, keyword or optional
TF-IDF baselines, calibrates separately, and calls `eval/final_eval.py`. Evaluation
logs one read per frozen revision and rejects source, ID and wording overlap with
the frozen training/calibration metadata. TF-IDF is tested in a temporary sklearn
environment, without adding it to the workspace.
