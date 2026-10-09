# Power re-measurement: search and implementation status

No empirical conclusion about the power of recent developer studies is supported
yet. Eligibility, full-text extraction and independent review remain incomplete.

Eligibility was recorded before an independent search for English quantitative
human-programmer studies of AI coding assistance, published/posted 2022-01-01
through 2026-10-01. Six Semantic Scholar queries and six corresponding arXiv
queries returned 110 records, reduced to 105 by DOI/title de-duplication. Three
Semantic Scholar queries failed with HTTP 429; failure records and raw results are
retained. This is an incomplete search, not an exhaustive sampling frame.

At the owner's request, model screening drafts propose 10 includes, 85 excludes
and 10 unclear cases. Every row records the basis and reason; title-only decisions
are distinguished from title/abstract review. All final decisions remain pending.
These counts are not the number of eligible studies. The search was not seeded
from the old 29-study reading list; overlap has not yet been assessed.

Full-text extractions: zero. Independent second-coder rows: zero. Reporting shares,
sample-size summaries, inter-rater kappas and their empirical intervals: not measured.
The indicator tables explicitly report extraction as pending. No values were filled
from abstracts. The historical 2006/2007 comparison is withheld until its original
tables and the new extraction are verified; the plan's historical numbers are not
treated as independently verified findings.

The new minimum-detectable-effect helper uses two-sided noncentral-t power at a
specified alpha and target power. Between-subject estimates assume independent,
equal-size arms; within-subject estimates use the paired-difference SD (d_z).
Retrospective sensitivity is conditional on these design/distribution assumptions,
not observed-effect power or proof that a study is underpowered. Crossover and
observational designs are skipped. Missingness and denominators are explicit.

The helper passes 18 numerical/validation tests; the indicator script passes three
hand-calculated synthetic fixtures, including exact binomial intervals. These
checks establish numerical behavior, not empirical findings. Before quoting a new
research figure, complete full-text extraction, independent recoding/adjudication
and the plan's ten-row source audit. If fewer than 40 eligible studies are found,
report the limited sample plainly.

Interviews, reviewer tasks and control-audit calibration have not run. Supervisor
ethics/consent guidance, participant selection and dedicated-laptop approval remain
pending in `APPROVALS.md`. No participants or observations were invented, and no
supervisor or prospective participant was contacted.
