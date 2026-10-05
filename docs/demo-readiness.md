# Demo delivery: 6 October 2026

## The story to demonstrate

One executable specification connects researcher decisions, participant tasks,
consented capture and reproducible analysis handoff. Demonstrate that connection
through a working study, not a list of future features.

Use the [five-minute runbook](demo-runbook.md). Keep a prepared approved study
and the local VSIX ready if the hosted service or model is unavailable. Never
project participant credentials or real participant data.

## Implemented in this delivery

- #37: Plan previews the actual assignment, tasks, timing and capture contract.
  Accepted changes are distinct from enrollment's current protocol. Previewing
  creates no link or approval. Refresh and assignment selection are explicit.
- Usability: named mobile tabs; “Create participant links”; link counts do not
  claim participation; retryable reads; stale requests cannot replace newer ones.
- #55/#62: updated runbook, API behavior and [canonical terminology](terminology.md).
- #56: [standards assessment](methodology-readiness.md), with prioritized gaps.

## Open-ticket boundaries

| Tickets | What remains; do not claim completion |
| --- | --- |
| #47 | PR #100 checks model availability; independent quality/cost evaluation remains |
| #49 | Event replay exists; understandable code diffs require explicit source capture policy |
| #50 | Comparative subagent experiment; do not add an unevaluated agent layer before a demo |
| #54/#58–61 | Final submission requirements, actual outcomes and author-reviewed contributions |
| #57 | Protected-branch checks, review and public-release verification |
| #62/#63 | Historical schema/template terminology and a fuller literature synthesis |
| #65 | Consented human pilot, feasibility observations and deviations |
| #89–94 | Evidence contract exists; independently reviewed map and evidence-to-choice workflow remain |
| #95–98 | Expert-adjudicated benchmark, classifier comparison and workflow evaluation |

The reviewed map needs real sources and a second reviewer. Synthetic examples
cannot satisfy it. Integration checks are not a usability study or evidence of
model superiority. No tickets were deleted or silently declared unnecessary.

## Release gate

The checked-in browser rehearsal creates synthetic projects and links on a local
server. Use a separate database, build the platform, install Chromium, then run:

```bash
REHEARSAL_URL=http://127.0.0.1:8011 npm --prefix platform run rehearse:run-plan
```

It checks manual setup, unapplied preview, approval, keyboard selection, privacy,
desktop/mobile accessibility, failure recovery and enrollment. Screenshots go to
the OS temporary directory. It refuses non-local targets to avoid touching a
hosted participant deployment.

The change must pass the full Python coverage floor, frontend check/build,
accessibility and a browser rehearsal before merge. Use normal required review;
do not bypass branch protection. After merge, verify the deployed build before
claiming hosted readiness. Also rehearse one physical TERN session in VS Code;
automated web tests do not verify that editor launch on the presentation machine.
