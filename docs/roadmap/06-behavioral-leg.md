# Phase 06 — Behavioral telemetry leg

> Read first: `extension/docs/developer_behavior_capture.md`,
> `extension/docs/adaptation-notes.md`.
> **Satisfies:** FR-INST-5/8/9/10/11/12. **Status:** ✅ built.

## The idea

What a developer *does* — captured content-free, on the same timeline as the
felt and static-code legs. Focus switches, aggregated edit bursts, paste events
(sizes and timings, never content), file saves, the AI-completion lifecycle,
visible-range tracking for scroll coverage, and — the differentiator — an
**origin classification** on every edit burst (human / ai / paste / undo-redo).

## What it builds

Extends the TERN extension (`src/core`, IDE-agnostic):
- `behavior.ts`, `recorder.ts`, `debounce.ts` — edit-burst aggregation.
- AI-completion lifecycle events: suggestion shown → accepted/rejected/dismissed
  with **review latency** and accepted size (FR-INST-8).
- `attention.ts` visible-range tracking → scroll coverage (FR-INST-9).
- origin classifier: `ai` when completion-correlated or a large fast block;
  thresholds protocol-configurable, heuristic documented (FR-INST-10).
- `idle.ts` — WakaTime-style heartbeats for active-vs-idle denominators
  (FR-INST-11); `captureFilter.ts` scopes capture to declared languages/paths
  (FR-INST-12).

## Acceptance

- Every edit burst carries an origin; paste-then-edit latency, focus switches,
  and the human/AI/paste mix are recoverable (RQ-P3/P4).
- No raw code, keystrokes, or clipboard text ever leave the instrument
  (FR-ETH-2) — sizes, shapes, timings, salted hashes only.

## Verification

- `cd extension && npm run check` green; grep-the-output confirms no content in
  emitted events.
