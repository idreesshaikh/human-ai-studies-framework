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
- #92–94: [evidence-to-choice software slice](evidence-workflow.md): imported
  immutable maps, explicit constraints, supporting passages, atomic design/analysis
  choices, researcher approval and provenance exports. Chat is the primary surface;
  examples, fixed-detail forms and protocol panels use progressive disclosure.
- Researcher chat: one welcome prompt and a prominent composer; research tools
  are in a keyboard-accessible menu. Recorded decisions fold away but retain
  source inspection and Undo. Protocol review remains an explicit approval step.
- #49: chronological session replay; optional code patches require an explicitly
  selected task file and the approved raw-code policy. No diffs are inferred.

## Open-ticket boundaries

| Tickets | What remains; do not claim completion |
| --- | --- |
| #47 | PR #100 checks model availability; independent quality/cost evaluation remains |
| #49 | Replay and opt-in diffs implemented; physical editor capture rehearsal and merge remain |
| #50 | Comparative subagent experiment; do not add an unevaluated agent layer before a demo |
| #54/#58–61 | Final submission requirements, actual outcomes and author-reviewed contributions |
| #57 | Protected-branch checks, review and public-release verification |
| #62/#63 | Historical schema/template terminology and a fuller literature synthesis |
| #65 | Consented human pilot, feasibility observations and deviations |
| #89–94 | Software slice exists; independent literature review, third-family execution and full capture integration remain |
| #95–98 | Expert-adjudicated benchmark, classifier comparison and workflow evaluation |

The reviewed map needs real sources and a second reviewer. Synthetic examples
cannot satisfy it. Integration checks are not a usability study or evidence of
model superiority. No tickets were deleted or silently declared unnecessary.

## Release gate

The checked-in browser rehearsal creates synthetic projects and links on a local
server. Use a separate database, build the platform, install Chromium, then run:

```bash
REHEARSAL_ISOLATED=1 REHEARSAL_URL=http://127.0.0.1:8011 npm --prefix platform run rehearse:run-plan
REHEARSAL_ISOLATED=1 REHEARSAL_URL=http://127.0.0.1:8011 npm --prefix platform run rehearse:evidence-chat
REHEARSAL_ISOLATED=1 REHEARSAL_URL=http://127.0.0.1:8011 npm --prefix platform run rehearse:session-replay
REHEARSAL_ISOLATED=1 REHEARSAL_URL=http://127.0.0.1:8011 npm --prefix platform run rehearse:workspace-layout
REHEARSAL_ISOLATED=1 REHEARSAL_URL=http://127.0.0.1:8011 npm --prefix platform run rehearse:demo-readiness
```

It checks manual setup, unapplied preview, approval, keyboard selection, privacy,
desktop/mobile accessibility, failure recovery and enrollment. Screenshots go to
the OS temporary directory. It refuses non-local targets to avoid touching a
hosted participant deployment.

`REHEARSAL_ISOLATED=1` confirms that you started this server with a separate
synthetic database; loopback alone does not prove isolation. Each rehearsal
removes only its own newly created project in a `finally` block, including after
failure. Add `REHEARSAL_KEEP=1` to retain a synthetic fixture for presentation or
debugging. Existing projects and downloaded artifacts are never swept or deleted.

The change must pass the full Python coverage floor, frontend check/build,
accessibility and a browser rehearsal before merge. Use normal required review;
do not bypass branch protection. After merge, verify the deployed build before
claiming hosted readiness. Also rehearse one physical TERN session in VS Code;
automated web tests do not verify that editor launch on the presentation machine.

## Independent verification, 5 October

### Combined Claude + merged-main delivery

The original working folder was preserved in a private local checkpoint before
integration. The combined copy was independently exercised on port 8014 with a
separate SQLite database; no existing participant projects were deleted.

- Python: **918 passed**, **84.16%** total coverage, metrics **98.92%**;
  Ruff and six-package consistency passed.
- Extension: **227 passed**, typecheck/lint/format passed, both dependency audits
  reported zero vulnerabilities. VSIX packaging passed (52 files); the scripted
  classifier harness ran and explicitly reports its known failure cases, not
  real-world accuracy.
- Platform: all semantic/UI checks, lint, typecheck, contrast and production
  build passed; landing and unknown-route accessibility smoke passed.
- Browser: final **60 cases** (five tabs × six widths × two themes), no Axe
  violations or document overflow. Setup/approval/enrollment, evidence import,
  source inspection, stale compile, Plan loading/assignment, replay, outage/retry,
  keyboard/dialog/wheel scroll and all four download actions passed.
- Additional human-workflow rehearsal: invalid counts never create links;
  copy denial remains visible with manually selectable connection strings;
  link dialogs fit 320–1440px; all tabs fit at 200% text; coarse-pointer buttons
  have 44px targets; reading older chat stays in place when a reply completes;
  Stop restores text immediately without resending; retry reuses its request id.
- End-to-end smoke: 126 scoped synthetic rows, ingest idempotency, sequence-gap
  detection, joined CSV keys, all ten analysis recipes, report/notebook/dictionary.
- Strict documentation build passed. Docker daemon was unavailable locally;
  the Docker image build passed in PR CI. The configured Ministral route returned
  usable structured replies for all three bounded synthetic briefs, without a
  429; this is compatibility evidence, not a model-quality benchmark.
  A physical VS Code session and hosted deployment are **not certified** by these
  tests. No claim of exhaustive testing of every possible state or measured
  100/100 researcher usability is made.

Run the extra regression against an isolated database:

```bash
REHEARSAL_ISOLATED=1 REHEARSAL_URL=http://127.0.0.1:8014 npm --prefix platform run rehearse:human-workflows
```

Integration retains Claude's disconnect/upload handling, validation harness,
compiler-default warnings, revisions, readable capture labels, project palette,
name limits and keyboard helpers, alongside merged evidence, replay, exports,
study folders and the persistent collapsed draft rail. Contradictory route-removal
assertions were corrected: Setup still calls quick-protocol, and the public
schema/artifact/corpus APIs remain supported. Hosted unknown-study checks use
hosted identity semantics; sensor integrity flags retain the existing nonblocking
collection contract.

The following records describe the earlier merged-main verification, not a second
independent review of the combined delivery:

- Full workspace: 841 Python tests passed, 83.28% coverage; metrics retained
  its stricter floor at 98.92%. Ruff and the six-package consistency check passed.
- Extension: typecheck, lint, format and all 205 tests passed. Platform lint,
  typecheck, semantic verifiers, token contrast checks and production build passed.
  Both npm dependency audits reported no vulnerabilities. Strict docs build passed.
- Browser: all five study tabs checked at 320, 390, 768, 1024, 1440 and 2048px
  in light and dark themes, with reduced motion enabled: 60 cases, zero Axe
  violations or document overflow. Tab-owned scroll containers were exercised.
- Separate workflow rehearsals cover empty/manual setup, unapplied preview,
  approval, assignments, evidence import/source inspection, keyboard decisions,
  privacy, enrollment, deterministic replay and explicit outage/retry paths.
  All four Share exports produced actual nonempty downloads.
- Integrated smoke: simulation, synthetic/live separation, ingest idempotency,
  sequence gaps, joined CSV keys, ten analysis recipes, report and notebook passed.

Verified defects fixed: disappearing collapsed draft rail; expanded desktop
preference hiding mobile review; inconsistent chat/composer widths; stale Plan
loading/assignment state; approval offered during an unfinished compile; 320px
project-switcher overflow; skipped Evidence heading levels. Delayed compilation
now has a regression test: Apply remains disabled until the current draft arrives.
The labelled draft rail is available from 768px, including smaller desktop
windows; its expanded state is checked separately at that breakpoint.
An independent read-only reviewer approved the focused sidebar and timing fixes.

These are software checks, not a human usability score or a claim that every
possible interaction was tested. Hosted sign-in, the deployed release, physical
VS Code pairing/capture, all external providers and a consented human pilot still
need their own verification. The test smoke study is retained only in the isolated
synthetic database; existing user projects and tickets were not deleted.
