# Draft templates (not in the active registry)

These templates encode real study designs but reference recipes or
instruments the platform does not yet run, so they would fail the
registry's F2.3 validation ("a template cannot promise an analysis the
platform can't run"). They are kept here as design drafts until their
dependencies exist:

- **cursor-mining-v1** — needs curated-mining instruments wired as a
  template instrument block and repository-trend recipes
  (velocity/complexity trend analysis) built in `analysis/`.
- **hai-eval-synergy-v1** — needs 3-way comparison + human-AI synergy
  recipes built in `analysis/`.

A template enters `templates/registry/` only once `validate_registry()`
passes for it (schema, mandatory citations, every recipe exists, and every
skeleton placeholder is a declared parameter — so it instantiates into a
valid protocol with zero hand edits).
