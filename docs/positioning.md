# Positioning

Three published systems are close enough to PHOENIX that a reader should be
told exactly how it differs. Each is characterised from its own abstract and
paper; the citation keys match [the literature corpus](papers/README.md).

## The closest analogues

**Copilot Arena** (`copilot-arena`, Chi et al., 2025) integrates natively into
the developer's editor and collects pairwise preferences between model outputs
in the wild — over 4.5 million suggestions and 11k judgements across 10 models.
Its evaluation design is fixed by the platform: the question is always which of
two completions a developer prefers.

**RealHumanEval** (`realhumaneval`, Mozannar et al., 2024) is a web interface
measuring how well LLMs assist programmers through autocomplete or chat, used
for a study of 243 participants. The task set and instrumentation are fixed by
the platform, and work happens in the hosted interface rather than the
developer's own environment.

**Collaborative Gym** (`collaborative-gym`, Shao et al., 2024) is a framework
for developing and evaluating collaborative agents, with a simulated condition
driven by a user simulator and a real condition via a web application. Its unit
of evaluation is the agent; its task environments are general (travel planning,
related-work writing, tabular analysis) rather than software development in an
editor.

## What PHOENIX does differently

These systems answer a fixed question very well at scale. PHOENIX targets a
different job: letting a researcher specify *their own* question and have the
instrumentation and analysis follow from it automatically.

| | Copilot Arena | RealHumanEval | Collaborative Gym | PHOENIX / TERN |
| --- | --- | --- | --- | --- |
| Study design | fixed by platform | fixed by platform | fixed per environment | configured per study |
| Research question | model preference | LLM assistance effect | agent collaboration quality | the researcher's own |
| Capture site | developer's own editor | hosted web interface | hosted web application | developer's own editor |
| Conditions and assignment | n/a (paired outputs) | fixed arms | simulated vs real | derived from the protocol |
| Single source for capture *and* analysis | no | no | no | the versioned protocol |
| Plan refused when data uncaptured | n/a | n/a | n/a | yes, before collection |
| Consent surfaced in the capture tool | n/a | study-specific | n/a | yes |
| Analysis handoff | released dataset | released dataset | evaluation suite | notebook + replication kit |
| **Validated by real use** | **yes, at scale** | **yes, N=243** | **yes, benchmark study** | **not yet** |

## The contribution claim

Assembling a developer study today means wiring a protocol, participant
assignment, editor instrumentation, and analysis scripts separately. Those
pieces can disagree silently: a measure the design promises is never recorded,
or the exported dataset lacks the identifiers needed to compare conditions. The
failure surfaces at analysis time, when the sessions are gone.

PHOENIX derives capture configuration and the analysis plan from one versioned
protocol, so an analysis cannot be planned over data the study never collects.
The planner reports that mismatch as a specification defect *before* data
collection ends, when it is still fixable.

Baltes et al.'s guidelines for empirical studies involving LLMs
(`guidelines-empirical-llm-se`) treat this alignment as a methodological
requirement. PHOENIX's claim is that it can be enforced mechanically rather
than by reviewer discipline.

## The honest limitation

The last row of the table is the important one. The three comparison systems
have each been validated by real deployment. PHOENIX has not: no study has been
run with it, and it therefore makes no empirical claim about how developers work
with AI.

What can be demonstrated today is the mechanism — that a protocol drives
capture and analysis from one source, and that the mismatch it is designed to
catch is in fact caught. Whether that mechanism measurably reduces
design-to-analysis errors for working researchers is an open question and the
natural next study.
