# Phase 05: Cognitive leg (fatigue, stuck, session)

> Read first: `requirements/srs.md` §FR-INST, `extension/PROJECT_GUIDE.md`.
> **Satisfies:** FR-INST-1/2/3/13/14. **Status:** ✅ built.

## The idea

The in-IDE study companion for how a developer *feels* while working, sampled
without ever interrupting them (NFR-1). Fatigue micro-probes timed into typing
pauses, stuck-episode detection that prompts inline without stealing focus, and
a pausable, crash-recoverable session clock ending in a TLX-style debrief.
Prompts render as translucent in-editor surfaces layered over the code; the
participant's eyes stay on their work.

## What it builds

`extension/` (VS Code extension "TERN", TypeScript), respecting
the core/adapter split (NFR-3: `src/core` never imports `vscode`):
- `src/core/`: `surveys.ts`, `stuckDetector.ts`, `session.ts`, `idle.ts`,
  `attention.ts` (IDE-agnostic logic, mocked-timer tested).
- `src/vscode/`: `fatiguePrompt.ts`, `stuckPrompt.ts`, `endSurvey.ts`,
  `statusBar.ts` (the adapter surfaces).
- Session start records an environment snapshot (VS Code + extension versions,
  OS, agent tool + model, task ID) for replication provenance (FR-INST-14).

## Acceptance

- Fatigue probes fire in typing pauses with jitter and a quiet tail (FR-INST-1);
  stuck episodes prompt inline without stealing focus (FR-INST-2).
- The session clock is pausable and crash-recoverable, ending in the debrief
  (FR-INST-3).
- Prompts are in-editor surfaces, never separate windows (FR-INST-13).

## Verification

- `cd extension && npm run check` (typecheck + lint + format + mocked-timer
  tests) is green; time-dependent logic uses an injected clock.
