# Draft templates (not in the active registry)

These templates encode real study designs but reference recipes or
instruments the platform does not yet run, so they would fail the
registry's F2.3 validation ("a template cannot promise an analysis the
platform can't run"). They are kept here as design drafts until their
dependencies exist:

- **cursor-mining-v1**: the *recipe ids* it names (`task-outcome-by-condition`,
  `code-quality-by-condition`, `meyer-fragmentation`) now exist in the
  analysis catalogue, but at the wrong measurement unit: those recipes read
  live-session events (`task_outcome`, `editor_focus`) or per-participant
  workspace-snapshot metrics, none of which a curated GitHub mining run
  produces. `validate_registry()`'s recipe-existence check would pass on a
  name match alone; promoting on that basis would be F2.3 in letter only,
  not in spirit. Needs real **repository-trend recipes** (velocity-trend,
  complexity-trend, or PR-size/review) built in `analysis/`, scoped to
  `unit: repository`. The protocol-schema side is solved (see
  `protocol/examples/cursor-mining-2026.yaml`'s nominal-`tern` +
  `planned: 1` + `durationMinutes: 1` convention, now mirrored in this
  draft's `protocolSkeleton`); only the recipes are the remaining gap.

`hai-eval-synergy-v1` (formerly listed here) has been promoted to
`templates/registry/`: its recipes (`task-outcome-by-condition`,
`code-quality-by-condition`, `agent-interaction-dynamics`) are live-session
recipes, matching this template's live, within-subjects lab-experiment
design.

A template enters `templates/registry/` only once `validate_registry()`
passes for it (schema, mandatory citations, every recipe exists, and every
skeleton placeholder is a declared parameter, so it instantiates into a
valid protocol with zero hand edits) **and** the recipes it names are
actually scoped to fit the design's measurement unit and data path;
`validate_registry()` checks the name exists, not that it fits; that
second check is a human judgment call each promotion must still make.
