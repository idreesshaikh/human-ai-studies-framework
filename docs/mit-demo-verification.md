# MIT demo verification

6 October 2026. This verifies the local source and production build in an isolated
synthetic database. Existing studies and participant data were not used.

## Changes verified

Researcher forms share labelled controls, keyboard-accessible number steppers,
linked validation, readable hints, and scrolling dialogs with visible actions.
The protocol rail remains available across workspace layouts. Decision cards expose
named groups and preserve explicit acceptance, source inspection, and approval.
The workspace tour opens Plan when explaining the participant journey.

If project creation succeeds but its first study fails, the composer now retains
the name and opening brief, announces the failure, and retries in the saved project.
A browser regression confirms exactly one project and one study after recovery.

Assistant cleanup shortens citations without breaking parentheses, deduplicates
matching decisions across model and explicit proposals, and preserves distinct
measures sharing a number, research limitations, and concise streamed line breaks.
The source-map-js build dependency is updated to 1.2.2; both npm audits are clean.

## Validation

- Platform: lint, TypeScript, semantic/control verifiers, contrast checks, and
  production build pass. Landing and unknown-route Axe checks pass.
- Extension: typecheck, lint, format, and all 227 tests pass. The compiled debrief
  passes 12 keyboard/layout/Axe cases including forced colors.
- Full Python run: 962 passed; one stale source-location contract failed. That
  contract now checks the shared label map and its actual consumer. The affected
  assistant, streaming, vocabulary and design suites subsequently pass all 108
  cases, including restored regressions. CI must rerun the full final tree.
- Ruff, six-package configuration consistency, strict documentation build, and
  whitespace checks pass.
- Browser: 60 workspace tab/width/theme cases; 10 manual-form layout/theme/zoom
  cases; evidence review and approval; participant links, denied clipboard,
  reading position, Stop/retry, queued decisions and Undo; project recovery.
  Another 36 project/template/settings/member cases have zero Axe violations
  and document overflow after theme transitions settle.
- Synthetic integration smoke passes ingest idempotency, sequence-gap detection,
  live/synthetic separation, CSV join keys, all ten analysis recipes, report,
  notebook and dictionary generation. All four workspace exports download
  actual nonempty files.

## Remaining demo limits

These are bounded software and browser checks. Hosted deployment/sign-in,
external model availability, a physical VS Code capture session, and human
screen-reader/usability review are not certified by this pass. Keep an approved
local study and the manual protocol path ready as described in
[the demo runbook](demo-runbook.md). Synthetic results demonstrate integration,
not research findings. Merge remains subject to required CI and code-owner review.
