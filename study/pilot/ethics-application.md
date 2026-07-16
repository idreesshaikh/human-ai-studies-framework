# Ethics application text - pilot-2026

Section drafts for the University of Manchester Department of Computer
Science ethics application (low-risk route expected). Paste into the
university's current form; the protocol field `study.ethicsRef` tracks the
submission reference. **The approved PDF becomes the `ethics-approval.pdf`
gate artifact - data collection is mechanically blocked until it is
uploaded (FR-ETH-1).**

## 1. Aims

To pilot a study of how AI coding assistance affects developers' cognitive
load, working behavior, and code quality; and to evaluate the researcher's
study-instrumentation framework (the Masters project) end-to-end. Research
questions RQ-P1..P5 as specified in the study protocol
(`protocol/examples/pilot-study.yaml`, frozen v1.0).

## 2. Design and procedure

Within-subjects, two conditions (`ai-assisted` / `unassisted`), order and
task pairing counterbalanced. Each participant completes two 45-minute
programming sessions (maintenance work on two small, matched Python
programs supplied by the researcher), separated by a break or scheduled on
different days. Total participant time ≤ 2 hours including briefing,
consent, and debrief. Sessions take place on the researcher's laptop with
the researcher present but not intervening.

## 3. Participants

4-8 adult volunteers (6 planned) with basic Python familiarity, recruited
from the researcher's department network (posters/word of mouth). No
vulnerable groups; no incentive payments; participation or withdrawal has
no academic or professional consequence (no participants in a dependent
relationship with the researchers).

## 4. Data collected and minimization

By construction the instruments record **aggregates, sizes, timings, and
categories - not content**: self-reported fatigue/stuck/workload ratings;
edit timing/size/origin classes; visible-editor-region ranges; paste
*sizes* (never text); automatic code-complexity metrics; acceptance-test
outcomes. Two scoped, consent-itemized exceptions: (a) snapshots of the
researcher-provided task repository as the participant edits it (needed for
code-quality time series; it is not the participant's own code), and
(b) in the AI condition, the assistant conversation as **metadata only**
(turn timestamps, sizes, tool names - no conversation text; policy
`metadata-only` declared in the protocol and technically enforced).
No audio/video, no keystroke logging, no clipboard content, no personal
data beyond the consent paperwork.

## 5. Anonymity and storage

Participants appear in all stored data only as anonymous IDs (P01...). The
name↔ID mapping exists only on the paper consent forms, stored per
university policy and destroyed at study end. All study data remains on the
researcher's encrypted machine; no cloud services receive participant data
(the framework's only external API calls send literature metadata and
aggregate statistics, never participant-level rows - enforced server-side).
Data retained anonymized for the thesis examination period, then archived
per university policy.

## 6. Risks and mitigation

Minimal-risk: ordinary programming activity of bounded duration. Possible
mild fatigue or evaluation anxiety - mitigated by the info sheet's "not a
test of you" framing, the right to pause/stop at any time, breaks between
sessions, and the 45-minute cap. The in-editor fatigue probes are
single-keypress and dismissible.

## 7. Consent and withdrawal

Written informed consent (see `consent-form.md`) itemizing each data
stream, including the two content exceptions, before any session.
Participants may stop any session and may withdraw their data up to the
start of analysis; withdrawal deletes their rows from the store (the
deletion is logged in the study's findings file as a count only).
