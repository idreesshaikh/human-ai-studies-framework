# Draft annotation guidelines

The owner has requested model-assisted labeling. These rules and the catalog are
proposals pending D13–D15. Model drafts and repository seeds are training only;
neither is an independent human annotation or a locked-test judgment.

Label the quantity the researcher wants to measure, rather than the tool, design
or statistical method. Use the descriptions and source paths in
`../catalog/catalog.v1.json`. A class specifies a construct and possible capture
fields; it does not prove capture compatibility or validate an instrument.
For multiple quantities, record the first explicit construct as primary and the
other as `secondary_label`. Mark uncertain interpretations for review and give a
reason. A confidence rating of 1–3 is a subjective review aid.

1. Mental demand is S1; effort is S2; the raw six-item workload mean is S8.
   Bare “cognitive load” is ambiguous: inspect questionnaire, fatigue probe or
   static-code context before choosing S8, E3 or E10. Do not resolve it silently.
2. Periodic fatigue ratings are E3. Frustration questionnaire ratings are S3.
3. Time until the first passing test is E1; binary test success is E2. General
   task duration needs a capture-compatibility note. E2 has no supported paired
   inference in the proposed lookup.
4. Perceived speed/productivity and the perception gap are `none`: no declared
   instrument currently supports them. Never relabel perception as objective time.
5. Static code characteristics are E10. Substantive defect counts are `none`;
   test pass/fail is E2. Static complexity does not establish measured mental load.
6. Suggestion review actions/timing are E7; acceptance share is E8. Review quality
   or “carefulness” without an observable timing/action quantity is `none`.
7. Stuck/struggle episodes are E4; file/focus switching is E6. Neither inactivity
   nor generic interruptions alone establish these constructs.
8. Paste amounts/provenance are E5; captured agent turn cadence/response sizes are
   E9. Pasting does not by itself establish AI assistance.
9. Self-rated comprehension is S6; an objective comprehension quiz is `none`.
   Bare “comprehension” needs clarification.
10. SUS usability is S9. Prior self-rated skill is S10, a draft covariate requiring
    piloting. Trust, satisfaction, PR size and review comments are `none` in this
    proposed catalog. Individual SUS items do not independently establish usability.
11. Method/design phrases such as “Wilcoxon” or “between-subjects” are not measure
    mentions. Exclude them rather than fabricating a construct.

Annotators A and B receive blank sheets and do not see model labels or each other's
labels. Retain their raw sheets, adjudicate disagreements separately, and record
the winning rule. Unresolved items are excluded from the test split and counted.
Without a second independent human annotator, do not claim inter-rater reliability
or an independently validated test set. The proposed pilot gate is 100 items and
kappa ≥0.6, pending owner approval; undefined kappa cannot pass it.
