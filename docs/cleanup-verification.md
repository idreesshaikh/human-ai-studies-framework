# Independent cleanup and delivery check

Checked 2026-10-05. Scope: local database metadata, GitHub delivery ancestry,
study deletion, chat/evidence/planning rehearsals, and frontend build checks.
No participant messages, source code, credentials, or download contents were
printed. Existing database records and downloads were not deleted.

## Findings and actions

- **P0 — Evidence delivery missing from main.** #101 merged at 10:09:06 UTC;
  #102 merged into its feature branch at 10:09:25 UTC. Main therefore lacked
  the evidence implementation despite both PRs saying merged. This follow-up
  reapplies that already-reviewed feature commit onto current main. Verify the
  follow-up's merge and deployed build before claiming delivery.
- **P1 — Incomplete study deletion.** The explicit cleanup list omitted
  `evidence_maps` and `session_blocks`; session-keyed events and metrics were
  not removed either. Fixed by resolving session ownership before removing
  mappings, deleting exclusively owned capture rows, and deleting scoped
  evidence and session mappings. Conflicting mappings belonging to another
  study preserve that study's capture. Regression tests cover study and project
  deletion, confirmation, other studies, corpus evidence, and unmapped capture.
- **P2 — Rehearsals accumulated test projects.** Both browser scripts now require
  explicit isolated-database acknowledgement, clean up only their own newly
  created synthetic project on success or failure, and verify its deletion.
  `REHEARSAL_KEEP=1` explicitly preserves a presentation/debug fixture.
- **P2 — Existing orphan mappings need review.** Read-only inspection found
  20 session-block mappings without matching study rows in the original local
  database. This alone does not establish their provenance or authorize a purge.
  No existing records were changed. The named `zz-audit-temp` and `zz-flow-test`
  projects were absent. Capture can also be legacy or deliberately synthetic;
  neither a missing study nor a test-like name is sufficient deletion authority.
- **Downloads are ignored, not merely untracked.** `.gitignore` already excludes
  `.playwright-mcp/`, `.study-data/`, and SQLite artifacts. Share exports remain
  local and may contain sensitive study data. Do not upload or blanket-delete
  them; review exact files before any requested cleanup.

## Scoped technical audit

These are heuristic implementation scores, not a human usability score or a
complete WCAG certification. They describe the checked chat/evidence/planning
surfaces, not the entire platform. Snapshot before the follow-up fixes:

| Dimension | Score / 4 | Evidence or remaining limit |
| --- | --- | --- |
| Accessibility | 3 | Keyboard flows and desktop/mobile Axe pass; full assistive-technology review remains |
| Performance | 3 | Route chunks; initial JS 113.40 kB gzip, study route 56.23 kB gzip; no field performance claim |
| Theming | 4 | Token/literal and configured light/dark contrast checks pass |
| Responsive | 3 | 1440px and 390px flows pass without horizontal overflow; all zoom/device combinations not tested |
| Implementation integrity | 1 | Release-blocking main ancestry gap and incomplete cleanup identified |
| Total | 14 / 20 | Aggregate does not override the P0 release blocker |

The bundled detector reported no findings on ConversationView, EvidencePanel,
and tokens. Positive practices to preserve: explicit evidence limitations,
human acceptance separate from protocol approval, recoverable outages, and
independent theme tokens. This check intentionally adds no more interface copy
or decorative complexity.

Recommended order: resolve the P0 delivery gate; retain the P1/P2 cleanup fixes;
use `$impeccable harden` for any verified remaining recovery gap and
`$impeccable polish` only after functional release gates pass. You can request
these separately or together; re-run `$impeccable audit` after delivery to
reassess the scoped score.

## Verification

Both actual browser rehearsals passed against a newly created, separate
loopback database. Afterwards it contained zero rehearsal projects, studies,
evidence maps, conversation turns, or enrollment tokens. Existing local demo
projects were not swept. The frontend check includes rehearsal helper tests;
backend deletion regressions are part of the normal Python suite.
