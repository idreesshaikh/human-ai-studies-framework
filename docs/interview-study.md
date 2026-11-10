# Consolidate the interview study

Continue the existing interview study using its original consent arrangements,
research questions and analytic approach. The material below supports two or
three additional interviews and consolidation; it is not a new tool-effectiveness
experiment or a replacement analysis method.

## Inventory before interviewing

Locate the original guide, consent/use conditions, recordings or notes, any
transcripts, codebook, analytic memos and existing findings. Use stable pseudonyms
and source locations. Keep names, contact details, consent records and raw
interviews in approved private storage; Git is not the participant-data store.

For each existing interview record its source, usable material, consent reference,
analysis status and unresolved questions. An absent transcript is not an absent
interview. Notes, paraphrases and verbatim quotations must remain distinguishable.

## Forty-five-minute follow-up

Use existing questions wherever possible. Log additions to the guide so the
report can explain differences between earlier and later interviews. The
candidate topics below are prompts to adapt, not an approved instrument.

| Minutes | Topic | Neutral prompt |
| --- | --- | --- |
| 0–5 | Context and agreed participation | Confirm permitted note-taking/recording; ask about the participant's role and relevant study experience |
| 5–17 | A concrete recent or planned study | “Please walk me through how you prepared or are preparing that study.” |
| 17–27 | Difficulties and existing solutions | “Where did you spend the most effort? What happened? How did you handle it?” |
| 27–35 | Short demonstration | Show the same core example; record what was shown and any assistance provided |
| 35–42 | Fit, limitations and counterexamples | “Where would this fit, if anywhere? What would you continue doing with your current tools? What might make this unsuitable?” |
| 42–45 | Clarification and close | Summarize the interpretation, invite corrections and ask which issue matters most |

Optional probes only when relevant: defining outcomes, preparing tasks, assignment,
instrument setup, data inspection, analysis handoff, sharing study materials, and
reconstructing an earlier study. Ask for an example and consequence before
suggesting a solution. Include “none” and “already solved” as legitimate answers.

Keep existing-practice statements separate from reactions after the demonstration.
Do not introduce the proposed measurement-checking direction as an established
need. A hypothetical willingness to use a feature is a reaction, not evidence of
an experienced problem. Do not ask the participant to validate the developer's
preferred research contribution.

## Eight-hour budget

This is a maximum for the additional interviews and their consolidation,
including writing the interview findings. Maintain a time log and stop at
480 minutes. General software cleanup and the remainder of the final report
are separate project work.

| Activity | Minutes | Cumulative |
| --- | --- | --- |
| Inventory existing evidence and adapt the original guide | 45 | 45 |
| Logistics and preparation | 15 | 60 |
| Three interviews, at most 45 minutes each | 135 | 195 |
| Immediate memos, at most 15 minutes each | 45 | 240 |
| Verify selected excerpts and source locations | 45 | 285 |
| Consolidate with existing analysis and inspect counterexamples | 105 | 390 |
| Write findings and limitations for the report | 60 | 450 |
| Contingency | 30 | 480 |

With two interviews, retain the spare 45 minutes as contingency or source
verification; do not expand recruitment automatically. Prioritize existing notes
and targeted verification over producing full transcripts solely for presentation.
Follow the study's actual analysis requirements if they need different material;
adjust scope with the supervisor rather than silently exceeding the time box.

## Source-linked consolidation

Use the existing analytic method. Do not relabel it grounded theory or reflexive
thematic analysis without evidence of the actual procedure. Organizational tags
below do not establish a validated codebook or independent coding agreement.

A private register can use this header:

```csv
interview_id,source_ref,consent_ref,material_type,analysis_status,notes_ref
```

An evidence matrix can use:

```csv
interview_id,source_locator,excerpt,excerpt_type,stage,code,interpretation,design_implication,counterevidence,review_status
```

`excerpt_type` distinguishes verified quotation, paraphrase and analyst memo.
`stage` distinguishes before-demo needs from after-demo reactions. Source locators
can be timestamps or note paragraph numbers. Preserve the original wording when
quoting; do not silently turn a paraphrase into a quotation. A model may suggest
codes for review but cannot supply missing participant evidence.

For every proposed finding, retain:

1. Its meaning and scope in the participants' accounts.
2. Supporting source locations and contrasting or negative cases.
3. What is interpretation versus what the participant explicitly reported.
4. The resulting requirement or limitation and the relevant implemented behavior.
5. Unresolved uncertainty, including whether the finding preceded the demo.

Counting distinct interviewees mentioning a topic can be descriptive if the
denominator and prompting are reported. Do not count repeated excerpts as
independent participants or describe a small purposive sample as prevalence.
Do not claim saturation, intercoder reliability or participant confirmation
unless those procedures were actually conducted and documented.

## Report handoff

Complete the interview section of the [project report](project-report-draft.md)
with the verified sample, recruitment, dates, guide versions, procedure, actual
analysis approach, findings and limitations. Separate requirements elicitation
from product usability or effectiveness claims. Preserve findings that challenge
the implemented tool and explain any requirements that remain outside scope.

The private working folder can live under `.research-artifacts/interviews/`
when that location meets the team's existing storage arrangements. Templates
and an empty register are preparation, not completed data analysis.
