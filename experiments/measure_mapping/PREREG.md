# Proposed preregistration — unsigned

Owner signature/date: pending D15. This is a draft; no trained system has been
evaluated on human labels. Freeze the catalog (D13) and assign two independent
annotators (D14) before collecting or locking evaluation data.

Primary rule: a candidate is better only when its locked-test multiclass NLL is
lower than the best keyword/TF-IDF baseline, the 95% source-paper cluster bootstrap
interval for the NLL difference excludes zero, and its coverage at 5% selective
error is at least the baseline's. Otherwise report that a plain baseline is enough.
Do not draw comparative conclusions from fewer than 100 independent test items.

Choose temperatures and a confidence threshold using calibration only; the
threshold targets 5% selective error and always answers equal-confidence items
together. Record accuracy, macro-F1 (all classes and S/E groups), NLL, Brier,
equal-width and equal-mass ECE, risk/coverage at 5% and 10%, and confident-wrong
rate. Use source-paper cluster bootstrap intervals and seed 20261008.

Keep source papers, templates, paraphrase clusters and near-duplicate wording
disjoint across splits. Repository and model-generated phrases are training only.
Lock canonical test (id,text,label) triples by SHA-256 before fitting any model.
One read per frozen system revision is logged by final evaluation. Models and
thresholds are never changed after looking at test results. No participant data
or unreleased text is sent to hosted services; Jev is evaluation only, subject
to supervisor clearance of its terms.
