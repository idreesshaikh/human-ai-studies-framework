import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  readLegs,
  activeLegCount,
  capturesContent,
  LEG_IDS,
  CaptureConfigLike,
} from '../src/core/legs';

/** A capture config as the middleware's `leg_summary` serves it. */
const CFG: CaptureConfigLike = {
  legs: [
    {
      leg: 'metrics',
      label: 'Static metrics',
      description: 'Measures the shape of the code you produce.',
      state: 'enabled',
      toggles: [
        {
          label: 'Workspace snapshots',
          description: 'Stores your code, governed by the study consent.',
          path: ['snapshot', 'enabled'],
          currentValue: true,
        },
        {
          label: 'Snapshot interval',
          description: 'Minutes between snapshots.',
          path: ['snapshot', 'intervalMinutes'],
          currentValue: 10,
        },
      ],
    },
    {
      leg: 'behavioral',
      label: 'Behavioral',
      description: 'Records what you did.',
      state: 'enabled',
      toggles: [],
    },
    {
      leg: 'cognitive',
      label: 'Cognitive',
      description: 'Asks how you are finding the work.',
      state: 'disabled',
      toggles: [],
    },
    {
      leg: 'agent',
      label: 'Agent interaction',
      description: 'Records agent turns.',
      state: 'unavailable',
      toggles: [],
    },
  ],
};

test('all four legs always come back, in a stable order', () => {
  assert.deepEqual(
    readLegs(CFG).map((l) => l.id),
    [...LEG_IDS],
  );
});

test('leg state is read from the middleware summary, not re-derived', () => {
  const byId = new Map(readLegs(CFG).map((l) => [l.id, l]));
  assert.equal(byId.get('metrics')?.state, 'enabled');
  assert.equal(byId.get('cognitive')?.state, 'disabled');
  assert.equal(byId.get('agent')?.state, 'unavailable');
});

test('with no capture config, every leg is unavailable — never a silent off', () => {
  const legs = readLegs(undefined);
  assert.equal(legs.length, 4);
  assert.ok(legs.every((l) => l.state === 'unavailable'));
  // The distinction that matters: we must not tell a participant a leg is
  // switched off when we simply have not asked the middleware yet.
  assert.ok(legs.every((l) => l.state !== 'disabled'));
});

test('a leg missing from the summary is unavailable, and still listed', () => {
  const partial: CaptureConfigLike = {
    legs: [
      { leg: 'behavioral', label: 'B', description: 'd', state: 'enabled' },
    ],
  };
  const byId = new Map(readLegs(partial).map((l) => [l.id, l]));
  assert.equal(byId.get('behavioral')?.state, 'enabled');
  assert.equal(byId.get('metrics')?.state, 'unavailable');
  assert.equal(byId.size, 4);
});

test('an older middleware sending no legs block degrades, it does not throw', () => {
  const legs = readLegs({});
  assert.equal(legs.length, 4);
  assert.ok(legs.every((l) => l.state === 'unavailable'));
  // Fallback copy still names each leg, so the surface is never blank.
  assert.ok(legs.every((l) => l.label.length > 0 && l.description.length > 0));
});

test('a malformed legs payload is ignored rather than trusted', () => {
  for (const junk of [
    { legs: 'nope' },
    { legs: [1, 2, 3] },
    { legs: [null] },
  ]) {
    const legs = readLegs(junk as CaptureConfigLike);
    assert.equal(legs.length, 4);
    assert.ok(legs.every((l) => l.state === 'unavailable'));
  }
});

test('an unrecognised state reads unavailable, not enabled', () => {
  const weird: CaptureConfigLike = {
    legs: [{ leg: 'metrics', label: 'M', description: 'd', state: 'on' }],
  };
  assert.equal(readLegs(weird)[0].state, 'unavailable');
});

test('content-touching toggles are flagged; ordinary ones are not', () => {
  const metrics = readLegs(CFG)[0];
  const snapshot = metrics.toggles.find(
    (t) => t.label === 'Workspace snapshots',
  );
  const interval = metrics.toggles.find((t) => t.label === 'Snapshot interval');
  assert.equal(snapshot?.consentRelevant, true);
  assert.equal(interval?.consentRelevant, false);
});

test('a toggle without a label or description is dropped, not half-rendered', () => {
  const broken: CaptureConfigLike = {
    legs: [
      {
        leg: 'metrics',
        label: 'M',
        description: 'd',
        state: 'enabled',
        toggles: [{ path: ['x'], currentValue: true }, null],
      },
    ],
  };
  assert.deepEqual(readLegs(broken)[0].toggles, []);
});

test('activeLegCount counts only enabled legs', () => {
  assert.equal(activeLegCount(readLegs(CFG)), 2);
  assert.equal(activeLegCount(readLegs(undefined)), 0);
});

test('capturesContent is true when an enabled leg has a content toggle on', () => {
  assert.equal(capturesContent(readLegs(CFG)), true);
});

test('capturesContent is false when the content toggle is off', () => {
  const off = JSON.parse(JSON.stringify(CFG)) as CaptureConfigLike;
  (
    off.legs as { toggles: { currentValue: unknown }[] }[]
  )[0].toggles[0].currentValue = false;
  assert.equal(capturesContent(readLegs(off)), false);
});

test('capturesContent ignores a content toggle on a leg that is not running', () => {
  // The toggle says "snapshots on", but the leg itself is disabled — claiming
  // content capture here would frighten a participant about nothing.
  const off = JSON.parse(JSON.stringify(CFG)) as CaptureConfigLike;
  (off.legs as { state: string }[])[0].state = 'disabled';
  assert.equal(capturesContent(readLegs(off)), false);
});
