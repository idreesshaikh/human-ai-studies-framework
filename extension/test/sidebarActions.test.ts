import { test } from 'node:test';
import assert from 'node:assert/strict';
import { sessionActions } from '../src/core/sidebarActions';

test('a recording session offers Pause and End', () => {
  assert.deepEqual(
    sessionActions({ paused: false }).map((a) => a.command),
    ['tern.pauseSession', 'tern.endSession'],
  );
});

test('a paused session offers Resume and End', () => {
  assert.deepEqual(
    sessionActions({ paused: true }).map((a) => a.command),
    ['tern.resumeSession', 'tern.endSession'],
  );
});
