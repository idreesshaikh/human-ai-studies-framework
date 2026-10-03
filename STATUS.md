# Status

We are applying for **Artifacts Available** and **Artifacts Evaluated —
Reusable**.

We are **not** applying for *Results Reproduced*. The reason is stated plainly
below, because a reviewer will work it out in five minutes and we would rather
say it first.

## Artifacts Available

The artifact is public under the [MIT License](LICENSE), archived with a DOI,
and needs no credentials, institutional access, or proprietary data to obtain
or run.

## Artifacts Evaluated — Functional

- **Documented.** [INSTALL.md](INSTALL.md) gives two install routes and a
  five-step smoke test, each command verified against this revision.
  [REQUIREMENTS.md](REQUIREMENTS.md) states what is needed and what is not.
  [docs/architecture.md](docs/architecture.md) maps the code paths.
- **Consistent.** The artifact is the system the paper describes: a versioned
  protocol drives capture configuration and the analysis plan from one source.
- **Complete.** Every component in the paper ships here — protocol schema and
  validator, researcher workspace, VS Code extension, middleware, analysis
  recipes, notebook and replication-kit export.
- **Exercisable.** The test suite runs offline with no credentials. CI additionally
  enforces a workspace-consistency check, a repository size budget, a ratcheted
  82% coverage floor, and a stricter 95% floor on the static-metrics package.

## Artifacts Evaluated — Reusable

- Installs from a committed `uv.lock` and `package-lock.json`, so the
  dependency graph is exact rather than approximate.
- Structured as a documented workspace of packages with stated
  responsibilities, not a single script.
- The analysis catalogue is extensible: a recipe declares the research
  questions it answers and the event types it requires, and the planner refuses
  a plan whose data the protocol never captures.
- Exports a replication kit so a third party can re-run an analysis from the
  protocol and dataset alone.
- MIT licensed, with contribution and security policies.

## Why not Results Reproduced

**This artifact has not been run with human participants.** No study has been
conducted with it. It therefore makes no empirical claim about how developers
work with AI, and there is no such result for a reviewer to reproduce.

What can be reproduced is the artifact's own behaviour: the test suite, the
validation decisions, and the full capture-to-report path exercised with
labelled synthetic data.

We have made it structurally difficult to mistake the second thing for the
first. Synthetic rows are labelled at ingest; any report or figure computed
from them is banner-stamped **SYNTHETIC DATA — not a research finding**;
figures are watermarked; and `analysis run` exits non-zero on a dataset mixing
synthetic and participant rows unless overridden deliberately. A reviewer who
runs the pipeline will see a complete report that says, on its own face, that
it is not evidence about developers.

## Scope

The evaluated artifact is the live study path: protocol, workspace, extension,
middleware, and analysis. External-archive mining was explored during
development and removed before release rather than shipped half-finished; see
[docs/scope.md](docs/scope.md).
