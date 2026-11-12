import { test } from 'node:test';
import assert from 'node:assert/strict';
import { shouldRetryFatiguePrompt } from '../src/core/fatiguePrompt';

test('a scheduled fatigue probe retries after pause cancels its prompt', () => {
  assert.equal(
    shouldRetryFatiguePrompt(
      { value: null, skipped: true, cancelled: true },
      { paused: true, statusMenuInterrupted: false, ending: false },
    ),
    true,
  );
});

test('status-menu QuickPick collision retries even when hide looks like a skip', () => {
  assert.equal(
    shouldRetryFatiguePrompt(
      { value: null, skipped: true, cancelled: false },
      { paused: false, statusMenuInterrupted: true, ending: false },
    ),
    true,
  );
});

test('an explicit Esc remains a participant skip', () => {
  assert.equal(
    shouldRetryFatiguePrompt(
      { value: null, skipped: true, cancelled: false },
      { paused: false, statusMenuInterrupted: false, ending: false },
    ),
    false,
  );
});

test('session end does not retry a dismissed fatigue prompt', () => {
  assert.equal(
    shouldRetryFatiguePrompt(
      { value: null, skipped: true, cancelled: true },
      { paused: false, statusMenuInterrupted: true, ending: true },
    ),
    false,
  );
});
