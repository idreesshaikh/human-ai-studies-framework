# Demo workspace technical audit

5 October 2026. Scope: Setup, Evidence, Plan, Run and Data on the isolated built
app. This is a technical health score, not a measured researcher usability score.

Implementation integrity: pass for the tested workspace. Semantic tokens, shared
reading widths, explicit evidence decisions and protocol approval remain coherent.
The bundled detector returned no findings on the changed conversation/Plan code.
The earlier merged-main code and screenshot review was independently checked;
that reviewer did not duplicate browser execution. The combined Claude delivery
has a fresh automated audit, documented in `demo-readiness.md`.

| Dimension | Score / 4 | Evidence or limit |
| --- | --- | --- |
| Accessibility | 3 | 60 Axe-clean cases; keyboard review, decisions, seek and focus return; no screen-reader certification |
| Performance | 3 | Lazy route chunks, about 116 kB gzip entry JS and 60 kB study chunk; no field Web Vitals or load-test claim |
| Responsive design | 3 | 320–2048px, two themes, overflow/scroll, 200% text and coarse-pointer 44px button checks; no human usability-study claim |
| Theming | 4 | Semantic tokens, contrast verifier and both-theme Axe checks passed in tested states |
| Implementation integrity | 4 | Source/approval truth preserved; stale-response gate and retained Plan state tested |
| Total | 17 / 20 | Good; remaining verification limits are explicit |

## Material findings and disposition

Combined-version regressions fixed and browser-tested: Evidence loading-list
semantics; hidden copy failure after link creation; connection strings that could
not be selected manually; completion forcing the chat reader to the bottom;
Stop changing into Send and accidentally resubmitting; stale cancellation
callbacks altering a newer reply; tab aliases and typed study-name display;
inconsistent review/Run labels. Backend count/name/PDF validation and plain lookup
errors have route-level regression tests. Claude's existing changes are retained.

- P1, responsive: desktop-expanded preference removed mobile Review draft.
  Fixed in `ConversationView.tsx`; regression covers resizing with that preference.
- P1, integrity: an older valid compilation could be applied while the latest
  compilation was in flight, yielding HTTP 409. Fixed by sequencing compile
  responses and disabling application while compiling in `ConversationView.tsx`
  and `FinishReview.tsx`. A held-response regression verifies eventual HTTP 200.
- P1, responsive: project switcher overflowed the 320px header. Fixed in
  `ProjectSwitcher.tsx` with an accessible icon-only narrow-screen control.
- P2, accessibility: Evidence titles skipped from h1 to h3. Fixed in
  `LibraryTab.tsx` with coherent heading levels.
- P2, responsive comfort: narrow windows and coarse pointers now use 44px
  controls, including navigation and fields. The resulting 320px header overflow
  was measured and fixed by adjusting mobile spacing, not shrinking targets.
- P2, accessibility: the conversation-loading label lacked a compatible role.
  Fixed with a named status region; the final 60-case matrix passed.

No reproducible P0/P1 remains in these tested flows. The later loading-state
regression reproduced `aria-prohibited-attr`, identified its source and verified
the fix; transient states remain part of the accessibility checks.

## Positive findings and next verification

Latest form pass: shared input/select/textarea styling now consumes the existing
control tokens rather than separate heights, shadows and unit borders. The manual
form and link dialog retain fixed headings/actions with one scrolling body; tested
states include narrow phones, landscape, both themes, 200% text, validation and
outages. State-driven dialogs restore focus to their stable opener rather than
a removed menu item or Radix focus guard. Ten manual and eight link-dialog cases
passed alongside the 60-case workspace matrix. The score remains technical and
does not certify screen-reader operation or measured researcher usability.

Accessibility follow-up: the source-confirmation focus loss was reproduced in a
browser before fixing it. A delayed-response regression now verifies retained
focus and disabled stale proposals. Modified decision shortcuts and keys inside
nested controls leave the protocol unchanged; radio-group arrows/Home/End move
focus with selection. These paths pass the evidence and human-workflow rehearsals.
The compiled participant debrief also passes 12 keyboard/layout/Axe cases across
light, dark and forced colors. Its previously invisible radio focus and unnamed
comments field are fixed, and its privacy wording now reflects participant-ID
linkage. Evidence details expose claim type, unknown quality and review notes.

Multi-card decision testing also verifies focus moves to the next choice, the
last decision waits for an active reply before requesting exactly one follow-up,
and Undo restores focus without sending another message. Reopening a completed
manual draft restores all seven sections and its ready-to-review state.

The named draft rail preserves discovery without crowding chat. Review has one
visible entry point per layout. Initial Plan loading cannot reveal calculations
before the run overview. Failures preserve an explicit recovery path; synthetic
data remains labelled and excluded from live exports by default.

For touch-target findings, use `$impeccable adapt`, then `$impeccable polish` after
device testing. Re-run `$impeccable audit` after fixes. No new dashboard, model,
or research claim is warranted by this audit. Hosted auth/deployment and physical
editor capture remain release checks, not verified local UI features.
