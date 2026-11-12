# StudyLoop end-to-end QA — 2026-11-11

## Result

The offline readiness gate passed all seven checks: Python lint, workspace
configuration, Python tests, metrics coverage, TERN, PHOENIX/browser regression,
and strict documentation build. The run used disposable synthetic data and
finished with **1,196 Python tests passed (87.20% coverage)**, **99% metrics
coverage**, and a passing extension/UI build and browser suite.

This verifies the implemented software workflows. It does not establish
empirical study validity or perfect classification of AI/paste behavior.

## Final campaign addendum — 2026-11-12

The follow-up ten-study campaign completed the longer linked workflow and
reran the final code gates. The combined Python suite now passes **1,359 tests**
with 1 expected xfail and 6 dependency deprecation warnings. Extension tests
(252), platform lint/build, the full browser regression, and a 30-rule WCAG 2.2
AA audit also passed. See [the ten-study campaign report](QA-10-STUDIES-2026-11-11.md)
for the agent-by-agent coverage, fixes, exclusions, and evidence.

The linked 30-minute TERN session ran in VS Code 1.145, reached 1,800,045 ms
active time, uploaded seven debrief responses, and produced 60 contiguous event
rows. It exposed a fatigue-prompt interruption race and a monotonic timestamp
regression; both were reproduced and fixed in the extension. The original and
30-minute P02 QA sessions are marked `exclude` because they contain pre-fix
incidents. The run is synthetic QA evidence, not human-participant data.

## Journeys exercised

- **Researcher setup and planning:** manual protocol entry, validation, review
  and approval; template/library paths; saved plans; capture configuration;
  participant link generation and redemption; chatbot recovery, retry, Stop,
  Unicode, and HTML-looking input.
- **Run and inspect:** synthetic event ingestion, capture-input checks, session
  paging/search, inclusion decisions, outcome/analysis views and charts.
- **Exports:** CSV/data bundle, design card, notebook and replication kit.
  Default research exports excluded all synthetic rows; explicit synthetic
  export included the seeded 622 events and marked the manifest accordingly.
- **TERN in VS Code 1.145:** installed TERN 1.0.1 in an isolated profile and
  opened a disposable copy of `extension/examples/tern-lab`. Completed
  preflight/consent, a real 15-minute local session, a synthetic edit/save,
  pause/resume, fatigue response and six-item debrief. The JSONL had 32 rows;
  its timer record showed 900,532 ms active and 63,495 ms paused. A follow-up
  short session verified the fixed participant label and that the sidebar
  event count advanced from 2 to 7 after the 15-second refresh interval.
- **Duration boundaries:** fake-clock extension tests covered 15-minute and
  30-minute session completion, fatigue prompt timing, and exclusion of a
  five-minute break from the 30-minute active study clock. Seeded PHOENIX data
  also covered both 15- and 30-minute fatigue schedules.
- **Accessibility and responsive behavior:** axe WCAG 2.2 AA reported zero
  violations across audited empty/populated researcher surfaces in light/dark
  themes and desktop/tablet/mobile sizes. Overflow, reachable scroll regions,
  keyboard focus and focus-ring scans passed.

## Defects fixed and rerun

1. AI-accept/paste correlation could relabel an edit burst in a different
   document. Correlation now includes the workspace-relative file; a regression
   test and multi-file validation cases cover it.
2. Scrolling with a parked caret could trigger a dwell-based stuck prompt.
   Recent viewport movement in that file now suppresses caret-only dwell while
   the separate scroll-thrash detector remains active. The scripted replay now
   reports zero false alarms across its non-stuck cases.
3. The active-session sidebar displayed the workspace participant default
   instead of the ID entered for the live session. It now reads the ID pinned
   to the session and matches the JSONL.
4. The event count in the TERN sidebar stayed stale during an active session.
   The sidebar now refreshes at the existing 15-second snapshot cadence; a
   live VS Code run verified the count update.
5. Analysis tests left Matplotlib figures registered between tests. An
   autouse test fixture now closes figures before and after each test; the
   analysis suite passed with `RuntimeWarning` treated as errors.

## Remaining limits

- The original 15-minute IDE run was local-only. The follow-up campaign did run
  a PHOENIX-linked 30-minute session end to end; both P02 QA sessions are
  excluded from analysis because they contain pre-fix incidents.
- The browser suite exercised chatbot success/recovery flows against its
  synthetic backend. A bounded live compatibility check attempted one synthetic
  brief, then the configured provider returned HTTP 429 (`limited`); the
  script stopped before the other two briefs. No proposal was approved or
  applied, and the provider reported no cost value. Live chatbot quality and
  literature responses therefore remain unverified.
- Scripted capture calibration retains documented observation gaps: AI recall
  was 75% and paste recall 64% in the labelled fixtures. Context-menu pastes,
  streamed edits without a discrete suggestion signal, and signals arriving
  outside their correlation windows can be missed or mislabeled. These are
  capture limits, not evidence that AI was or was not used.
- The final Python run emitted six dependency deprecation warnings (Starlette
  TestClient/httpx and PyMuPDF). They did not fail the gate. Node's experimental
  MockTimers and the MkDocs Material future-compatibility notice also appeared.

## Evidence

- Full readiness report and logs: `/tmp/studyloop-qa-final-readiness/`
- Extension validation replay: `/tmp/studyloop-extension-final-validate.log`
- Final VSIX: `extension/tern-1.0.1.vsix` (ignored build artifact)
- Researcher browser screenshots: `/tmp/studyloop-ui-qa/`
- VS Code session screenshots and disposable JSONL: `/tmp/studyloop-vscode-qa/`
  and `/tmp/studyloop-tern-lab/.study-data/`
