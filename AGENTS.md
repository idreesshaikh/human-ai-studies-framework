# Agent guide

Read this before changing anything. It applies to every coding agent working in
this repository (Codex, Claude Code and others); `CLAUDE.md` points here.

## What is here

StudyLoop configures, runs and inspects human–AI developer studies.

| Path | What it is | Checks |
|---|---|---|
| `protocol/` | study protocol schema and deterministic derivations | `uv run --no-sync pytest -q protocol` |
| `middleware/` | API, storage, model provider orchestration | `uv run --no-sync pytest -q middleware` |
| `analysis/` | audits, planner, simulations; never reads middleware storage | `uv run --no-sync pytest -q analysis` |
| `platform/` | PHOENIX, the researcher web app (React, Vite) | `npm --prefix platform run check` |
| `extension/` | TERN, the VS Code capture extension | `npm --prefix extension run check` |
| `agent-capture/` | Claude Code hooks and transcript importer | `uv run --no-sync pytest -q agent-capture` |
| `scripts/` | tooling, including the AI-use calibration kit | `uv run --no-sync pytest -q analysis/tests/test_calibration_scripts.py` |

The full gate is `uv run --no-sync python scripts/check_demo.py`. Python lint:
`uv run --no-sync ruff check <paths>` and `uv run --no-sync ruff format <paths>`
(line length 88). Setup is in `CONTRIBUTING.md`.

## Rules

- **Git.** Do not commit, push, tag, stash, rebase or rewrite history unless the
  maintainer asks in the current conversation. Leave changes unstaged and report
  what changed and what you ran.
- **Private material.** `docs/experiments/`, `docs/private/`, `reports/`,
  `research_notes/`, `artifacts/` and `.research-artifacts/` are ignored on
  purpose. Never force-add them, quote them in public files, or make tests depend
  on them; tests use synthetic fixtures (`tmp_path`).
- **Frozen instrument.** The AI-use calibration runs on a fixed TERN build. Do not
  change `extension/`, `agent-capture/` or
  `analysis/src/analysis/recipes/control_arm_audit.py` without being asked;
  `scripts/freeze_calibration.py check` fails when they or the calibration
  scripts differ from the frozen versions.
- **Claims.** Never describe a TERN signal as detecting or verifying AI use
  without its measured error rates beside it, and never claim that non-use in a
  control arm is verified.
- **Synthetic data** stays out of findings and exports, as the code already
  enforces.
- **References.** Every citation must be one you have opened; venues desk-reject
  fabricated references.

## Non-interactive tools for agents

Every command below runs without prompts, exits non-zero with a one-line reason
on refusal, and never needs a GUI unless stated.

| Task | Command |
|---|---|
| Session order | `uv run --no-sync python scripts/calibration_order.py` |
| Instrument version | `uv run --no-sync python scripts/instrument_version.py` |
| Freeze check | `uv run --no-sync python scripts/freeze_calibration.py check` |
| Prepare / finish a session | `uv run --no-sync python scripts/calibration_session.py prepare N` / `finish N --ai-used … --exposed … --assisted … --note …` |
| Blinded post-session check (optional model review) | `uv run --no-sync python scripts/calibration_session.py verify N --reviewer none\|codex\|claude`; never reports signals |
| Rehearse in real VS Code (GUI, macOS) | `node scripts/calibration_drive.cjs STEPS.json --out ACTIONS.jsonl` after `prepare dry SCENARIO --no-open`; step files in `scripts/rehearsals/` |
| Compare a rehearsal with TERN's rows | `uv run --no-sync python scripts/rehearsals/compare.py LOG_DIR` |
| Calibration matrix | `uv run --no-sync python scripts/run_calibration.py --rows … --labels … --out …` |

`calibration_drive.cjs` drives an isolated VS Code (its own user data and
extensions under `~/ai-use-calibration/dry/`) through scripted steps and logs
each action with timestamps. Agent-driven sessions are rehearsals and regression
checks of the instrument. They are never calibration data, which must come from
a person taking each route.

When running `codex exec` from another agent, close stdin (`< /dev/null`);
otherwise it waits for piped input.
