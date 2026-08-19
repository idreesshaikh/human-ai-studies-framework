import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  overlayFlags,
  configChanged,
  readBlock,
  shouldApplyCaptureConfig,
  CaptureConfig,
} from '../src/core/captureConfig';

const CFG: CaptureConfig = {
  captureConfigVersion: 'abc123',
  producer: 'overlay',
  settings: {
    'tern.participantId': 'P01',
    'tern.stuck.enabled': true,
    'tern.behavior.captureClipboard': false,
  },
};

test('overlayFlags strips the tern prefix', () => {
  const f = overlayFlags(CFG);
  assert.equal(f['participantId'], 'P01');
  assert.equal(f['stuck.enabled'], true);
  assert.equal(f['behavior.captureClipboard'], false);
  assert.equal(Object.hasOwn(f, 'tern.participantId'), false);
});

test('configChanged is true only when the version differs', () => {
  assert.equal(configChanged(undefined, 'abc123'), true);
  assert.equal(configChanged('abc123', 'abc123'), false);
  assert.equal(configChanged('old', 'abc123'), true);
});

test('wall #6: shouldApplyCaptureConfig refuses a version change while a session is active', () => {
  // A researcher flips a toggle mid-session — the version changed, but the
  // running session must not be reconfigured.
  assert.equal(shouldApplyCaptureConfig(true, 'v1', 'v2'), false);
});

test('wall #6: shouldApplyCaptureConfig applies a version change only at a boundary', () => {
  assert.equal(shouldApplyCaptureConfig(false, 'v1', 'v2'), true);
});

test('wall #6: an unchanged version is never re-applied, active or not', () => {
  assert.equal(shouldApplyCaptureConfig(false, 'v1', 'v1'), false);
  assert.equal(shouldApplyCaptureConfig(true, 'v1', 'v1'), false);
});

test('wall #6: full lifecycle — a mid-session amendment lands only at the next session start', () => {
  // Session 1 starts at a clean boundary: v1 is new, applies.
  let applied: string | undefined;
  const boundary = (sessionActive: boolean, incoming: string) => {
    if (shouldApplyCaptureConfig(sessionActive, applied, incoming)) {
      applied = incoming;
    }
  };

  boundary(false, 'v1');
  assert.equal(applied, 'v1');

  // Session 1 is now running. The researcher amends the protocol — the
  // server would now serve v2 — but nothing re-checks mid-session (the
  // adapter's only call site is pre-arm), and even a defensive check would
  // refuse because sessionActive is true.
  boundary(true, 'v2');
  assert.equal(applied, 'v1', 'a running session keeps its applied config');

  // Session 1 ends. Session 2's boundary re-pulls and finds v2 — applies now.
  boundary(false, 'v2');
  assert.equal(applied, 'v2', 'the amendment lands at the next session start');
});

// ------------------------------------------------------ the assigned block

const BLOCK = {
  index: 1,
  of: 2,
  taskId: 'fix-the-failing-test',
  condition: 'unassisted',
  title: 'Fix the failing test',
  description: 'The suite is red on main.',
  materials: 'https://example.invalid/repo',
};

test('readBlock returns the assigned task', () => {
  const b = readBlock({ ...CFG, block: BLOCK });
  assert.equal(b?.taskId, 'fix-the-failing-test');
  assert.equal(b?.condition, 'unassisted');
  assert.equal(b?.index, 1);
  assert.equal(b?.of, 2);
});

test('readBlock is undefined when the server sent none', () => {
  assert.equal(readBlock(CFG), undefined);
});

test('a block missing its task or condition is refused, not half-read', () => {
  // Rendering "task 2 of 2" with no task is worse than rendering nothing:
  // the participant is told they have an assignment and not what it is.
  assert.equal(
    readBlock({ ...CFG, block: { ...BLOCK, taskId: '' } }),
    undefined,
  );
  assert.equal(
    readBlock({ ...CFG, block: { ...BLOCK, condition: '' } }),
    undefined,
  );
});

test('a malformed block never throws at session start', () => {
  // The block is display state. A study must not fail to start because a
  // field the editor only shows came back the wrong shape.
  for (const bad of [null, 'a string', 42, [], { taskId: 7 }]) {
    assert.equal(readBlock({ ...CFG, block: bad }), undefined);
  }
});

test('a block falls back to its task id when it carries no title', () => {
  const b = readBlock({ ...CFG, block: { ...BLOCK, title: '' } });
  assert.equal(b?.title, 'fix-the-failing-test');
});
