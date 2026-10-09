# Systematic search log

Question: how do recent quantitative studies of human developers using AI coding
tools report sample sizes, power, uncertainty and reproducibility?

Eligibility fixed before searching: English empirical reports posted/published
2022-01-01 through 2026-10-01; human programmers/developers; AI coding assistant
or LLM-based tool as an experimental/observed condition; quantitative outcome.
Exclude model-only benchmarks, qualitative-only reports, tutorials, position
papers, and duplicate analyses of the same dataset (retain the original).

The repository reading list is not used to seed searches. Deduplicate first by
DOI, then normalized title. Model draft screening records reasons and coder; final eligibility is pending review.
Raw responses and failure records are private research artifacts; they are not
an export of Semantic Scholar abstracts. Metadata includes Semantic Scholar and
arXiv data. No papers are accepted into the application's corpus by this script.

| UTC run | Source | Query | Reported hits | Retrieved | Raw files | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-10-08T13:03:26.134444+00:00 | s2 | "AI coding assistant" developers controlled experiment | unknown | 0 | s2-q01-failure.json | failed: 429 |
| 2026-10-08T13:03:26.134444+00:00 | arxiv | "AI coding assistant" developers controlled experiment | 3 | 3 | arxiv-q01-p0000.xml | ok |
| 2026-10-08T13:03:26.134444+00:00 | s2 | Copilot randomized controlled trial programmers | 0 | 0 | s2-q02-p0000.json | ok |
| 2026-10-08T13:03:26.134444+00:00 | arxiv | Copilot randomized controlled trial programmers | 0 | 0 | arxiv-q02-p0000.xml | ok |
| 2026-10-08T13:03:26.134444+00:00 | s2 | LLM-assisted programming user study productivity | unknown | 0 | s2-q03-failure.json | failed: 429 |
| 2026-10-08T13:03:26.134444+00:00 | arxiv | LLM-assisted programming user study productivity | 2 | 2 | arxiv-q03-p0000.xml | ok |
| 2026-10-08T13:03:26.134444+00:00 | s2 | large language model developers field experiment | 36 | 36 | s2-q04-p0000.json | ok |
| 2026-10-08T13:03:26.134444+00:00 | arxiv | large language model developers field experiment | 59 | 59 | arxiv-q04-p0000.xml | ok |
| 2026-10-08T13:03:26.134444+00:00 | s2 | AI pair programming empirical study participants | unknown | 0 | s2-q05-failure.json | failed: 429 |
| 2026-10-08T13:03:26.134444+00:00 | arxiv | AI pair programming empirical study participants | 1 | 1 | arxiv-q05-p0000.xml | ok |
| 2026-10-08T13:03:26.134444+00:00 | s2 | generative AI software engineers task completion time experiment | 0 | 0 | s2-q06-p0000.json | ok |
| 2026-10-08T13:03:26.134444+00:00 | arxiv | generative AI software engineers task completion time experiment | 9 | 9 | arxiv-q06-p0000.xml | ok |

Retrieved records: 110. After DOI/title de-duplication: 105. Eligibility, independent double coding and overlap with the earlier 29-study reading list have not yet been determined.

At the owner's request, all 105 records have a model-drafted eligibility label in
`screening.csv`: 10 proposed includes, 85 proposed excludes, and 10 unclear.
`draft_basis` distinguishes title-only screening from title/abstract review.
`decision` remains pending for every record; `review_status` is unreviewed, and
`coder` explicitly identifies the model. Draft inclusion is not full-text
eligibility. No sample sizes, effects or reporting indicators were extracted
from abstracts. Three failed source queries make this an incomplete search;
these draft counts cannot establish the prevalence of underpowered studies.
Independent review, full-text extraction and overlap analysis remain pending.
