import { test, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import {
  SessionConfig,
  SessionHooks,
  StudySession,
  newSessionId,
} from '../src/core/session';
import { CLOCK_BASE, advanceTo } from './helpers';

function baseConfig(over: Partial<SessionConfig> = {}): SessionConfig {
  return {
    participantId: 'P01',
    condition: 'unspecified',
    durationMs: 100_000,
    fatigueIntervalMs: 60_000,
    fatigueJitterRatio: 0, // deterministic schedule for tests
    fatigueQuietTailMs: 0,
    ...over,
  };
}

interface Spy extends SessionHooks {
  ended: Array<'elapsed' | 'manual'>;
  fatigueDue: number;
  ticks: number;
}

function spyHooks(): Spy {
  const spy: Spy = {
    ended: [],
    fatigueDue: 0,
    ticks: 0,
    onEnded: (reason) => {
      spy.ended.push(reason);
    },
    onFatigueDue: () => {
      spy.fatigueDue++;
    },
    onTick: () => {
      spy.ticks++;
    },
  };
  return spy;
}

function startMockedSession(
  cfg: SessionConfig,
  hooks: SessionHooks,
): StudySession {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  return new StudySession(cfg, hooks);
}

afterEach(() => mock.timers.reset());

test('remaining time counts down and the session ends when the timer elapses', () => {
  const hooks = spyHooks();
  const s = startMockedSession(baseConfig({ durationMs: 10_000 }), hooks);
  assert.equal(s.remainingMs, 10_000);

  advanceTo(CLOCK_BASE + 10_000);
  assert.deepEqual(hooks.ended, ['elapsed']);
  assert.equal(s.remainingMs, 0);
  assert.ok(hooks.ticks > 0, 'onTick fired each second');
});

test('fatigue probes fire on the scheduled interval', () => {
  const hooks = spyHooks();
  startMockedSession(
    baseConfig({ durationMs: 300_000, fatigueIntervalMs: 60_000 }),
    hooks,
  );
  advanceTo(CLOCK_BASE + 300_000);
  // Probes at 60/120/180/240 s; the 300 s probe is pre-empted by session end.
  assert.equal(hooks.fatigueDue, 4);
});

test('the quiet tail suppresses probes near the end of the session', () => {
  const hooks = spyHooks();
  startMockedSession(
    baseConfig({
      durationMs: 120_000,
      fatigueIntervalMs: 30_000,
      fatigueQuietTailMs: 30_000,
    }),
    hooks,
  );
  advanceTo(CLOCK_BASE + 120_000);
  // Probes at 30/60 s; the 90 s probe lands inside the quiet tail and is dropped.
  assert.equal(hooks.fatigueDue, 2);
});

test('pausing freezes the study clock; resume returns the pause duration', () => {
  const hooks = spyHooks();
  const s = startMockedSession(baseConfig({ durationMs: 100_000 }), hooks);

  advanceTo(CLOCK_BASE + 10_000);
  assert.equal(s.elapsedMs, 10_000);

  s.pause();
  assert.ok(s.paused);
  advanceTo(CLOCK_BASE + 40_000); // 30 s of break
  assert.equal(s.elapsedMs, 10_000, 'clock frozen while paused');
  assert.equal(s.remainingMs, 90_000);

  const pauseMs = s.resume();
  assert.equal(pauseMs, 30_000, 'resume reports the just-ended pause');
  assert.equal(s.pausedMsAccumulated, 30_000);
  assert.ok(!s.paused);

  advanceTo(CLOCK_BASE + 50_000); // 10 s more active work
  assert.equal(
    s.elapsedMs,
    20_000,
    'break time is excluded from the study clock',
  );
});

test('a paused session does not fire fatigue probes', () => {
  const hooks = spyHooks();
  const s = startMockedSession(
    baseConfig({ durationMs: 300_000, fatigueIntervalMs: 30_000 }),
    hooks,
  );
  advanceTo(CLOCK_BASE + 10_000);
  s.pause();
  advanceTo(CLOCK_BASE + 300_000); // long break spanning several would-be probes
  assert.equal(hooks.fatigueDue, 0);
});

test('resume returns 0 when the session was not paused', () => {
  const hooks = spyHooks();
  const s = startMockedSession(baseConfig(), hooks);
  assert.equal(s.resume(), 0);
});

test('manual end fires once and is idempotent', () => {
  const hooks = spyHooks();
  const s = startMockedSession(baseConfig(), hooks);
  s.end('manual');
  s.end('manual');
  advanceTo(CLOCK_BASE + 200_000);
  assert.deepEqual(hooks.ended, ['manual']);
});

test('newSessionId produces unique, well-formed ids', () => {
  const id = newSessionId();
  assert.match(id, /^s-[a-z0-9]+-[a-z0-9]{1,6}$/);
  assert.notEqual(newSessionId(), newSessionId());
});
