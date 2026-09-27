import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detectDrift, detectDriftAgainst } from '../src/core/settingsDrift';
import { LockedConfig } from '../src/core/lockedConfig';

// Local stub, so these cases test the comparison and not the builder.
function stubLock(
  locked: boolean,
  values: Record<string, unknown>,
): LockedConfig {
  return {
    locked,
    get<T>(key: string, fallback: T): T {
      return Object.hasOwn(values, key) ? (values[key] as T) : fallback;
    },
    has(key: string): boolean {
      return Object.hasOwn(values, key);
    },
    lockedValue(key: string): unknown {
      return values[key];
    },
    keys(): string[] {
      return Object.keys(values);
    },
  };
}

const LOCK = stubLock(true, {
  'behavior.captureClipboard': true,
  'stuck.enabled': true,
  'stuck.languages': ['python'],
  participantId: 'P01',
  'comprehensionProbe.probeTypes': ['recall', 'transfer'],
});

test('a changed boolean is reported with both values populated', () => {
  const drift = detectDrift(LOCK, {
    'behavior.captureClipboard': false,
  });
  assert.equal(drift.length, 1);
  assert.equal(drift[0].key, 'behavior.captureClipboard');
  assert.equal(drift[0].lockedValue, true);
  assert.equal(drift[0].attemptedValue, false);
});

test('an unchanged value is not reported', () => {
  const drift = detectDrift(LOCK, {
    'behavior.captureClipboard': true,
  });
  assert.deepEqual(drift, []);
});

test('a changed array is reported', () => {
  const drift = detectDrift(LOCK, {
    'stuck.languages': ['python', 'javascript'],
  });
  assert.equal(drift.length, 1);
  assert.equal(drift[0].key, 'stuck.languages');
  assert.deepEqual(drift[0].lockedValue, ['python']);
  assert.deepEqual(drift[0].attemptedValue, ['python', 'javascript']);
});

test('an identical array with the same contents is not reported', () => {
  const drift = detectDrift(LOCK, {
    'stuck.languages': ['python'],
  });
  assert.deepEqual(drift, []);
});

test('a key present in current but not in the lock is ignored', () => {
  const drift = detectDrift(LOCK, {
    'unknown.setting': 'whatever',
  });
  assert.deepEqual(drift, []);
});

test('a fully unlocked config returns no drift even when values differ', () => {
  const unlocked = stubLock(false, {
    'behavior.captureClipboard': true,
  });
  const drift = detectDrift(unlocked, {
    'behavior.captureClipboard': false,
  });
  assert.deepEqual(drift, []);
});

test('multiple drifted keys come back sorted by key', () => {
  const drift = detectDrift(LOCK, {
    'stuck.enabled': false,
    'behavior.captureClipboard': false,
    participantId: 'P02',
  });
  assert.deepEqual(
    drift.map((d) => d.key),
    ['behavior.captureClipboard', 'participantId', 'stuck.enabled'],
  );
});

test('a changed number and a changed string are each reported', () => {
  const numericLock = stubLock(true, {
    'stuck.thresholdSeconds': 60,
    participantId: 'P01',
  });
  const drift = detectDrift(numericLock, {
    'stuck.thresholdSeconds': 90,
    participantId: 'P02',
  });
  assert.equal(drift.length, 2);
  assert.deepEqual(
    drift.map((d) => d.key),
    ['participantId', 'stuck.thresholdSeconds'],
  );
  const numeric = drift.find((d) => d.key === 'stuck.thresholdSeconds');
  assert.equal(numeric?.lockedValue, 60);
  assert.equal(numeric?.attemptedValue, 90);
  const str = drift.find((d) => d.key === 'participantId');
  assert.equal(str?.lockedValue, 'P01');
  assert.equal(str?.attemptedValue, 'P02');
});

// detectDriftAgainst: identity and transport are authoritative but absent from
// the lock, so they are compared against the values the redeem issued.

test('detectDriftAgainst reports an edited identity key', () => {
  const drift = detectDriftAgainst(
    { participantId: 'P01', studyId: 'study-a' },
    { participantId: 'P99', studyId: 'study-a' },
  );
  assert.deepEqual(drift, [
    { key: 'participantId', lockedValue: 'P01', attemptedValue: 'P99' },
  ]);
});

test('detectDriftAgainst reports a redirected ingest endpoint', () => {
  const drift = detectDriftAgainst(
    { 'output.httpEndpoint': 'https://study.example/ingest/events' },
    { 'output.httpEndpoint': 'http://127.0.0.1:1/ingest/events' },
  );
  assert.equal(drift.length, 1);
  assert.equal(drift[0].key, 'output.httpEndpoint');
});

test('detectDriftAgainst ignores a key the caller did not declare', () => {
  // `condition` is never written into settings, so the caller leaves it out;
  // it must not be reported just because settings hold the schema default.
  const drift = detectDriftAgainst(
    { participantId: 'P01' },
    { participantId: 'P01', condition: 'unspecified' },
  );
  assert.deepEqual(drift, []);
});

test('detectDriftAgainst returns nothing when everything matches', () => {
  assert.deepEqual(
    detectDriftAgainst({ studyId: 's1' }, { studyId: 's1' }),
    [],
  );
});

test('detectDrift still delegates to the same comparison', () => {
  const lock = stubLock(true, { 'stuck.enabled': true });
  assert.deepEqual(detectDrift(lock, { 'stuck.enabled': false }), [
    { key: 'stuck.enabled', lockedValue: true, attemptedValue: false },
  ]);
});
