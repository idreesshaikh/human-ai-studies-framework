# Final validation

Validated locally on 11 September 2026. Changes remain uncommitted.

The implementation preserves the existing researcher workflow and design tokens.
The source detector reports no findings. The remaining limitations below are
separate from functional test failures.

## Results

| Check | Result |
| --- | --- |
| Python workspace | 726 tests passed |
| Workspace coverage | 82.83%, above the 82% CI floor |
| Static-metrics coverage | 98.92%, above the 95% floor |
| Extension | Typecheck, lint, formatting and 141 tests passed |
| Platform | Lint, typecheck, verification scripts and production build passed |
| Accessibility smoke | Both required routes passed |
| Browser route scan | 20 routes at 390px and 1440px, in light and dark themes |
| Browser errors and overflow | None observed in the route scans |
| Source detector | No findings |
| Python lint and source formatting | Passed |
| Whitespace and workspace configuration | Passed |
| End-to-end smoke | Synthetic capture, replay, export, analysis and notebook passed |

The initial light-theme scan sampled two conversation entrance animations before
text settled. Explicitly waiting for the loaded conversation and finite animations
resolved those contrast reports. The final conversation and draft checks passed
Axe at both widths and in both themes. Dark-theme route checks also exercised
reduced-motion preferences. Automated checks do not constitute full WCAG certification.

## Feature verification

| Feature | Verification |
| --- | --- |
| Project listing | Browser request failure, retry and successful recovery |
| Project and first study creation | Browser failure between writes, preserved input, retry without duplicate project |
| Quick start | Browser creation of two studies in the same personal workspace |
| Setup conversation | Browser rendering; automated turn, streaming, decision and compiler tests |
| Protocol review | Mobile draft access, review dialog, Escape dismissal and return to conversation |
| Evidence library | Browser viewer restrictions and failed addition preserving the identifier; API graph/link tests |
| Planning | Browser rendering and offline recovery; prescription, simulation and power tests |
| Enrollment and capture | Browser Run tab; token, assignment, consent, capture and ingestion tests |
| Data | Empty live view, cross-study stale responses, failed rehearsal and offline monitoring checks |
| Demo isolation | Demo rows excluded from live study; simulated rows excluded from default dataset and live sessions |
| Exports | Browser elicitation download; replication-kit and notebook tests; smoke-generated report and notebook |
| Membership and permissions | Browser role restrictions; authentication, invitation and authorization tests |
| Loading races | Browser overlapping reloads ignore stale success and stale failure |
| Navigation | Direct sign-in, friendly 404 recovery, project switcher focus restoration, mobile toggle and Escape |

## Issues resolved

- **P1:** Mobile users could not reach the protocol draft to review or apply it.
  A mobile conversation/draft switch now exposes the existing review controls.
- **P1:** The mobile navigation covered its own toggle. It now opens below the
  header and supports Escape with focus restoration and an expanded-state label.
- **P1:** Accepted move labels and literature labels lost contrast through opacity.
  Their text now retains the theme's readable foreground.
- **P1:** Direct sign-in links returned a server 404. The server now serves the
  sign-in route. Unknown HTML pages render the application's recovery page while
  retaining HTTP 404; missing assets and JSON requests remain errors.
- **P1:** Creation retries could repeat project creation. The first successful
  project is reused, and quick start reuses the personal workspace.
- **P1:** Overlapping reloads could overwrite current data. Only the latest request
  may update loading, data and error state.
- **P2:** Library failures cleared identifiers and viewer controls invited rejected
  writes. Failed additions preserve input; write controls respect the role.
- **P2:** Failed project listing had no retry control. Retry now reloads the list.

## Audit assessment

| Dimension | Score | Evidence or limit |
| --- | --- | --- |
| Accessibility | 3/4 | Axe and targeted keyboard checks pass; no assistive-technology user study |
| Performance | 3/4 | Lazy routes; initial JS about 113 kB gzip; no device CPU profiling |
| Responsive design | 3/4 | Draft and navigation work at 390px; some compact icon controls remain |
| Theming | 4/4 | Light and dark checks use the existing tokens |
| Implementation integrity | 4/4 | No detector findings; explicit provenance, errors and server-backed writes |
| Total | 17/20 | Good within the tested scope |

No unresolved P0/P1 issue was observed in these checks. A remaining **P2** refinement
is enlarging compact shell icon targets toward 44px for easier touch use; this is
an ergonomic recommendation, not a claim that every smaller target violates WCAG.
An optional follow-up is `impeccable adapt` for those controls, followed by
`impeccable polish`.

The tests use local temporary databases and offline provider fixtures. Live model
and literature-provider credentials, deployed authentication, Docker image builds,
and a full interactive VS Code host session were not exercised in this pass.
The existing Impeccable design sidecar is stale; `impeccable document` can refresh it
without changing the design direction.
