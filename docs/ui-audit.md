# Demo workspace technical audit

5 October 2026. Scope: Setup, Evidence, Plan, Run and Data on the isolated built
app. This is a technical health score, not a measured researcher usability score.

Implementation integrity: pass for the tested workspace. Semantic tokens, shared
reading widths, explicit evidence decisions and protocol approval remain coherent.
The bundled detector returned no findings on the changed conversation/Plan code.
Code and screenshot review were independently checked; browser execution was not
duplicated by that reviewer.

| Dimension | Score / 4 | Evidence or limit |
| --- | --- | --- |
| Accessibility | 3 | 60 Axe-clean cases; keyboard review, decisions, seek and focus return; no screen-reader certification |
| Performance | 3 | Lazy route chunks, about 113 kB gzip entry JS and 57 kB study chunk; no field Web Vitals or load-test claim |
| Responsive design | 3 | 320–2048px, two themes, overflow and scroll checks; compact controls are below the 44px comfort target |
| Theming | 4 | Semantic tokens, contrast verifier and both-theme Axe checks passed in tested states |
| Implementation integrity | 4 | Source/approval truth preserved; stale-response gate and retained Plan state tested |
| Total | 17 / 20 | Good; remaining verification limits are explicit |

## Material findings and disposition

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
- P2, responsive comfort: dense small buttons use 36px height rather than the
  44px AAA comfort target. They retain the 24px AA floor; touch-device trials
  should determine whether larger targets are needed before participant rollout.

No reproducible P0/P1 remains in these tested flows. One intermediate layout
rehearsal reported `aria-prohibited-attr`; its diagnostic rerun passed without a
code change. Keep this transient observation visible rather than claiming it
was a diagnosed defect or silently discarding it.

## Positive findings and next verification

The named draft rail preserves discovery without crowding chat. Review has one
visible entry point per layout. Initial Plan loading cannot reveal calculations
before the run overview. Failures preserve an explicit recovery path; synthetic
data remains labelled and excluded from live exports by default.

For touch-target findings, use `$impeccable adapt`, then `$impeccable polish` after
device testing. Re-run `$impeccable audit` after fixes. No new dashboard, model,
or research claim is warranted by this audit. Hosted auth/deployment and physical
editor capture remain release checks, not verified local UI features.
