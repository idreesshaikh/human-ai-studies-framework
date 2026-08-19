## What this changes

<!-- One paragraph. The why belongs here; the what is visible in the diff. -->

## Why now

<!--
What does this unblock, and for whom? A change on the design → setup path
should say which hop it improves; a change off that path should say why it
earns its keep. Pure refactors and docs fixes can write "no behaviour change".
-->

## Gates

<!-- Tick what you ran. CI runs all of these; running them locally first is faster. -->

- [ ] `uv run pytest`: all Python tests pass
- [ ] `uv run ruff check .`: clean
- [ ] `npm run check` in `platform/` (if the frontend changed)
- [ ] `npm run check` in `extension/` (if the extension changed)
- [ ] Coverage did not drop: the workspace floor is 79%

## Invariants

<!--
These are the rules that keep the science sound. Confirm the ones your change
touches, and delete the rest.
-->

- [ ] **Join keys**: every new data row carries `participantId`, `condition`,
      `taskId`, `sessionId`, a timestamp, and a schema version
- [ ] **Schema versioning**: any change to event shape or meaning bumps
      `SCHEMA_VERSION` / `protocolVersion`, and consumers branch on the version
      rather than guessing
- [ ] **Never interrupt the participant**: new sensors, sinks, and hooks are
      fire-and-forget; failures are swallowed, counted, and reported once
- [ ] **Privacy by construction**: no raw code content, keystrokes, or
      clipboard text; aggregates, shapes, and salted hashes only
- [ ] **Assistant sees aggregates only**: enforced server-side, not in a
      prompt
- [ ] **Cite only what was retrieved**: a move may cite a paper only if this
      turn's retrieval returned it; anything else is dropped, never rendered
- [ ] **Deterministic compile**: the same accepted moves against the same base
      produce a byte-identical protocol, with no model in the loop
- [ ] **Honest statistics**: exact tests, effect sizes, per-cell n; never a
      bare p-value
- [ ] **No participant data in git**: nothing under `.study-data/`,
      `results/`, or `*.sqlite3` is staged
- [ ] **Glossary terms**: `participant` not user, `condition` not group,
      `recipe` not script (in identifiers and schema fields too)

## New dependencies

<!--
Any new library, tool, or service: say what it replaces, why building it here
would be worse, and how the platform behaves when it is unavailable. Every
external service degrades gracefully; a new one must too. Write "none" if
there are none.
-->

## Trackers

- [ ] `platform/docs/agent-annotations.md` updated, if a `data-agent` name
      was added, renamed, or removed (the lint gate enforces this)
- [ ] `extension/CHANGELOG.md` updated under `## [Unreleased]`, if the
      extension changed

---

<!--
Authorship: your commits stay yours. By opening this PR you agree to license
your contribution under the repository's MIT licence.
-->
