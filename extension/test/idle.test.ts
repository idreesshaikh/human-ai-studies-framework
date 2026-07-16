import { test, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import {
  ActivityState,
  DEFAULT_IDLE_CONFIG,
  IdleDetector,
} from '../src/core/idle';
import { CLOCK_BASE, advanceTo } from './helpers';

function detector(windowMs = DEFAULT_IDLE_CONFIG.windowMs): {
  d: IdleDetector;
  transitions: ActivityState[];
} {
  const transitions: ActivityState[] = [];
  const d = new IdleDetector({ ...DEFAULT_IDLE_CONFIG, windowMs }, (state) =>
    transitions.push(state),
  );
  return { d, transitions };
}

afterEach(() => mock.timers.reset());

test('emits nothing while the participant stays active', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, transitions } = detector(120_000);
  d.start();

  for (let i = 0; i < 10; i++) {
    advanceTo(Date.now() + 60_000);
    d.activity(Date.now());
  }

  assert.deepEqual(transitions, [], 'transitions only - no periodic spam');
  d.dispose();
});

test('emits one idle transition after the rolling window elapses', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, transitions } = detector(120_000);
  d.start();
  d.activity(Date.now());

  advanceTo(Date.now() + 180_000); // 3 min of silence

  assert.deepEqual(transitions, ['idle'], 'exactly one idle row for the gap');
  d.dispose();
});

test('activity after idling emits the matching active transition', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, transitions } = detector(120_000);
  d.start();
  d.activity(Date.now());

  advanceTo(Date.now() + 180_000);
  d.activity(Date.now());

  assert.deepEqual(transitions, ['idle', 'active'], 'one transition pair');
  d.dispose();
});

test('window size is injectable', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, transitions } = detector(30_000);
  d.start();
  d.activity(Date.now());

  advanceTo(Date.now() + 45_000);

  assert.deepEqual(transitions, ['idle']);
  d.dispose();
});

test('stop() freezes the state machine (session pause)', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { d, transitions } = detector(120_000);
  d.start();
  d.activity(Date.now());
  d.stop();

  advanceTo(Date.now() + 300_000);

  assert.deepEqual(transitions, [], 'no idle transition while stopped');
  d.dispose();
});
