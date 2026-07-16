import { test, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_STUCK_CONFIG,
  StuckDetector,
  StuckDetectorConfig,
} from '../src/core/stuckDetector';
import { EditorSignal, StuckRegion } from '../src/core/types';
import { CLOCK_BASE, advanceTo } from './helpers';

function detector(over: Partial<StuckDetectorConfig> = {}): {
  d: StuckDetector;
  fired: StuckRegion[];
} {
  const fired: StuckRegion[] = [];
  const d = new StuckDetector({ ...DEFAULT_STUCK_CONFIG, ...over }, (region) =>
    fired.push(region),
  );
  return { d, fired };
}

function selection(line: number, file = 'a.ts'): EditorSignal {
  return { kind: 'selection', file, line, at: Date.now() };
}
function scroll(line: number, file = 'a.ts'): EditorSignal {
  return { kind: 'scroll', file, line, at: Date.now() };
}

afterEach(() => mock.timers.reset());

test('fires a dwell region after prolonged non-editing focus on one spot', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, fired } = detector({ stuckAfterMs: 90_000 });
  d.start();
  d.signal(selection(100));

  // Keep faint activity alive (within the idle window) but never edit.
  advanceTo(CLOCK_BASE + 40_000);
  d.signal(selection(102));
  advanceTo(CLOCK_BASE + 80_000);
  d.signal(selection(101));
  advanceTo(CLOCK_BASE + 92_000);

  assert.equal(fired.length, 1);
  assert.equal(fired[0].reason, 'dwell');
  assert.equal(fired[0].file, 'a.ts');
  assert.ok(fired[0].startLine <= 100 && fired[0].endLine >= 100);
  d.dispose();
});

test('does not fire dwell once the participant goes idle (away from keyboard)', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, fired } = detector({ stuckAfterMs: 90_000, idleAfterMs: 45_000 });
  d.start();
  d.signal(selection(100));
  // No further signals: after idleAfterMs the participant counts as away.
  advanceTo(CLOCK_BASE + 120_000);
  assert.equal(fired.length, 0);
  d.dispose();
});

test('editing resets the dwell clock (edits are progress)', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, fired } = detector({ stuckAfterMs: 90_000 });
  d.start();
  d.signal(selection(100));

  advanceTo(CLOCK_BASE + 60_000);
  d.signal({ kind: 'edit', file: 'a.ts', at: Date.now() }); // progress
  advanceTo(CLOCK_BASE + 120_000);
  d.signal(selection(101)); // keep non-idle
  advanceTo(CLOCK_BASE + 140_000);

  // 80 s since the edit - below the 90 s dwell threshold, so no prompt yet.
  assert.equal(fired.length, 0);
  d.dispose();
});

test('does not fire while the window is blurred', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, fired } = detector({ stuckAfterMs: 90_000 });
  d.start();
  d.signal(selection(100));
  d.signal({ kind: 'blur', at: Date.now() });
  advanceTo(CLOCK_BASE + 60_000);
  d.signal(selection(101));
  advanceTo(CLOCK_BASE + 120_000);
  assert.equal(fired.length, 0, 'blurred window is never flagged as stuck');
  d.dispose();
});

test('fires a scroll-thrash region on repeated re-reading oscillation', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, fired } = detector({
    stuckAfterMs: 90_000,
    scrollWindowMs: 60_000,
    scrollDirectionFlips: 4,
  });
  d.start();

  // Wait past the edit-recency gate (stuckAfterMs / 2), then oscillate.
  advanceTo(CLOCK_BASE + 50_000);
  for (let i = 0; i < 7; i++) {
    d.signal(scroll(i % 2 === 0 ? 100 : 110));
    advanceTo(Date.now() + 1_000);
  }
  advanceTo(CLOCK_BASE + 60_000);

  const thrash = fired.find((f) => f.reason === 'scroll-thrash');
  assert.ok(thrash, 'scroll-thrash detected');
  assert.equal(thrash!.file, 'a.ts');
  d.dispose();
});

test('respects the cooldown between two prompts', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, fired } = detector({ stuckAfterMs: 30_000, cooldownMs: 300_000 });
  d.start();
  d.signal(selection(100));

  // First dwell prompt around 30 s.
  advanceTo(CLOCK_BASE + 20_000);
  d.signal(selection(100));
  advanceTo(CLOCK_BASE + 40_000);
  assert.equal(fired.length, 1);

  // Keep dwelling; a second prompt must wait out the 5 min cooldown.
  for (let t = 50_000; t <= 200_000; t += 20_000) {
    d.signal(selection(100));
    advanceTo(CLOCK_BASE + t);
  }
  assert.equal(fired.length, 1, 'no second prompt inside the cooldown window');
  d.dispose();
});

test('notePromptShown starts the cooldown so external prompts are respected', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, fired } = detector({ stuckAfterMs: 30_000, cooldownMs: 300_000 });
  d.start();
  d.signal(selection(100));
  d.notePromptShown(); // e.g. a fatigue prompt just appeared

  for (let t = 20_000; t <= 120_000; t += 20_000) {
    d.signal(selection(100));
    advanceTo(CLOCK_BASE + t);
  }
  assert.equal(
    fired.length,
    0,
    'cooldown from an external prompt suppresses dwell',
  );
  d.dispose();
});

test('lastEditTime tracks the most recent edit signal', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d } = detector();
  d.start();
  advanceTo(CLOCK_BASE + 5_000);
  const editAt = Date.now();
  d.signal({ kind: 'edit', file: 'a.ts', at: editAt });
  assert.equal(d.lastEditTime, editAt);
  d.dispose();
});
