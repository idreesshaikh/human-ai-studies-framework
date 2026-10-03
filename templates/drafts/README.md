# Draft templates

These designs are kept as research notes, not as supported templates. They
refer to instruments or analysis units that the live workflow does not
provide, so the platform does not show them in the registry.

## `cursor-mining-v1`

This draft describes repository-level trends around coding-agent adoption. Its
recipes need repository observations (velocity, pull-request size, review
activity, and code trends), while the current analysis catalogue consumes live
session events or per-session snapshots. Nothing in the repository mines those
observations: the experimental adapter that once explored it was removed, so
this draft has no data path at all.

`protocol/examples/cursor-mining-2026.yaml` is the corresponding protocol
shape. It validates as a schema example, but it is not a runnable study.

## Promotion rule

A draft can move into `templates/registry/` only when its schema, citations,
placeholders, instruments, data path, and analysis recipes form one complete
tested vertical slice. A name match in the recipe registry is not enough.
Until then, keep the draft isolated and do not describe it as supported
functionality.
