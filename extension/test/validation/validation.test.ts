import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  classStats,
  confusionMatrix,
  misclassified,
  summariseStuck,
} from './metrics';
import { replayEditScenario, replayStuckScenario } from './replay';
import {
  EDIT_SCENARIOS,
  EditScenario,
  STUCK_SCENARIOS,
  StuckScenario,
} from './scenarios';
import { DISCLAIMER, renderReport } from './report';
import { parseRecording } from './recording';

const LABELS = ['human', 'ai', 'paste', 'undo-redo'];

test('confusionMatrix counts [expected][actual]', () => {
  const m = confusionMatrix(
    [
      { id: 'a', index: 0, expected: 'human', actual: 'human' },
      { id: 'b', index: 0, expected: 'paste', actual: 'ai' },
      { id: 'c', index: 0, expected: 'paste', actual: 'ai' },
    ],
    LABELS,
  );
  assert.equal(m[0][0], 1);
  assert.equal(m[2][1], 2);
  assert.equal(m[1][1], 0);
});

test('classStats gives precision/recall, null when undefined', () => {
  const pairs = [
    { id: 'a', index: 0, expected: 'human', actual: 'human' },
    { id: 'b', index: 0, expected: 'paste', actual: 'ai' },
    { id: 'c', index: 0, expected: 'ai', actual: 'ai' },
  ];
  const s = classStats(confusionMatrix(pairs, LABELS), LABELS);
  const ai = s.find((x) => x.label === 'ai')!;
  assert.equal(ai.precision, 0.5);
  assert.equal(ai.recall, 1);
  const paste = s.find((x) => x.label === 'paste')!;
  assert.equal(paste.precision, null, 'never predicted');
  assert.equal(paste.recall, 0);
  const undo = s.find((x) => x.label === 'undo-redo')!;
  assert.equal(undo.recall, null, 'no support');
});

test('misclassified lists only disagreements', () => {
  const out = misclassified([
    { id: 'a', index: 0, expected: 'human', actual: 'human' },
    { id: 'b', index: 2, expected: 'paste', actual: 'ai' },
  ]);
  assert.deepEqual(out, [
    { id: 'b', index: 2, expected: 'paste', actual: 'ai' },
  ]);
});

test('replayEditScenario classifies a scripted burst and is repeatable', () => {
  const s: EditScenario = {
    id: 'unit-typing',
    description: 'x',
    expected: ['human', 'paste'],
    events: [
      { t: 0, kind: 'change', charsAdded: 1 },
      { t: 300, kind: 'change', charsAdded: 1 },
      { t: 5_000, kind: 'paste' },
      { t: 5_000, kind: 'change', charsAdded: 10 },
    ],
  };
  for (let i = 0; i < 2; i++) {
    const out = replayEditScenario(s);
    assert.deepEqual(
      out.map((o) => o.actual),
      ['human', 'paste'],
    );
    assert.equal(out[0].charsAdded, 2);
  }
});

test('replayEditScenario throws when burst count disagrees with labels', () => {
  const s: EditScenario = {
    id: 'bad',
    description: 'x',
    expected: ['human', 'human'],
    events: [{ t: 0, kind: 'change', charsAdded: 1 }],
  };
  assert.throws(() => replayEditScenario(s), /bad.*1 burst/);
});

test('replayStuckScenario reports fire times relative to scenario start', () => {
  const s: StuckScenario = {
    id: 'unit-dwell',
    description: 'x',
    stuck: true,
    stuckFromMs: 0,
    durationMs: 120_000,
    expectedFires: 1,
    events: [
      { t: 0, kind: 'selection', line: 100 },
      { t: 40_000, kind: 'selection', line: 102 },
      { t: 80_000, kind: 'selection', line: 98 },
    ],
  };
  const r = replayStuckScenario(s);
  assert.equal(r.fires.length, 1);
  assert.equal(r.fires[0].atMs, 90_000);
  assert.equal(r.fires[0].reason, 'dwell');
});

test('summariseStuck computes time-to-detect and false alarms per hour', () => {
  const sum = summariseStuck([
    {
      id: 'a',
      stuck: true,
      stuckFromMs: 10_000,
      durationMs: 100_000,
      fires: [{ atMs: 50_000, reason: 'dwell' }],
    },
    {
      id: 'b',
      stuck: true,
      stuckFromMs: 0,
      durationMs: 100_000,
      fires: [],
    },
    {
      id: 'c',
      stuck: false,
      stuckFromMs: 0,
      durationMs: 1_800_000,
      fires: [{ atMs: 1, reason: 'dwell' }],
    },
  ]);
  assert.equal(sum.stuckScenarios, 2);
  assert.equal(sum.detected, 1);
  assert.deepEqual(sum.timeToDetectMs, [40_000]);
  assert.equal(sum.falseAlarms, 1);
  assert.equal(sum.nonStuckHours, 0.5);
  assert.equal(sum.falseAlarmsPerHour, 2);
});

test('parseRecording validates the labelled-recording shape', () => {
  const good = JSON.stringify({
    version: 1,
    source: 'vscode+copilot',
    events: [{ t: 0, kind: 'change', charsAdded: 3 }],
    labels: ['human'],
  });
  const s = parseRecording(good);
  assert.deepEqual(s.expected, ['human']);
  assert.throws(() => parseRecording('{"version":2}'), /version/);
  assert.throws(
    () =>
      parseRecording(
        JSON.stringify({ version: 1, events: [], labels: ['robot'] }),
      ),
    /label/,
  );
});

// ---- Regression gate on the scripted scenarios ----

test('gate: edit-origin results match the documented expectations exactly', () => {
  const ids = new Set<string>();
  const wrong = new Set<string>();
  for (const s of EDIT_SCENARIOS) {
    assert.ok(!ids.has(s.id), `duplicate scenario id ${s.id}`);
    ids.add(s.id);
    const out = replayEditScenario(s);
    const bad = out.filter((o) => o.actual !== o.expected);
    if (bad.length) wrong.add(s.id);
    if (s.knownFailure) {
      assert.ok(
        bad.length > 0,
        `${s.id} is flagged knownFailure but now classifies correctly; remove the flag`,
      );
    }
  }
  const documented = new Set(
    EDIT_SCENARIOS.filter((s) => s.knownFailure).map((s) => s.id),
  );
  assert.deepEqual([...wrong].sort(), [...documented].sort());
});

test('gate: stuck detector fires exactly as documented', () => {
  for (const s of STUCK_SCENARIOS) {
    const r = replayStuckScenario(s);
    assert.equal(r.fires.length, s.expectedFires, `${s.id} fire count`);
    if (!s.stuck && s.expectedFires > 0) {
      assert.ok(s.knownFalseAlarm, `${s.id} false alarm must be documented`);
    }
  }
});

test('report opens with the disclaimer and lists known failures', () => {
  const text = renderReport();
  assert.ok(text.startsWith(DISCLAIMER));
  assert.match(DISCLAIMER, /NOT an accuracy estimate/);
  assert.match(text, /Known failure/i);
  assert.match(text, /false alarms per simulated hour/i);
});
