import { test, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import {
  BurstAggregator,
  BurstConfig,
  ChangeSignal,
  DEFAULT_BURST_CONFIG,
  EditBurst,
} from '../src/core/behavior';
import { CLOCK_BASE, advanceTo } from './helpers';

function aggregator(over: Partial<BurstConfig> = {}): {
  a: BurstAggregator;
  bursts: EditBurst[];
} {
  const bursts: EditBurst[] = [];
  const a = new BurstAggregator({ ...DEFAULT_BURST_CONFIG, ...over }, (b) =>
    bursts.push(b),
  );
  return { a, bursts };
}

function typing(over: Partial<ChangeSignal> = {}): ChangeSignal {
  return {
    fileKey: 'src/task.py',
    charsAdded: 1,
    charsDeleted: 0,
    lines: 1,
    tsMono: Date.now(),
    ...over,
  };
}

afterEach(() => mock.timers.reset());

test('aggregates rapid changes into one burst and closes after the 2 s gap', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  for (let i = 0; i < 10; i++) {
    a.change(typing());
    advanceTo(Date.now() + 300);
  }
  assert.equal(bursts.length, 0, 'burst still open while typing continues');

  advanceTo(Date.now() + 2_500);
  assert.equal(bursts.length, 1);
  assert.equal(bursts[0].charsAdded, 10);
  assert.equal(bursts[0].origin, 'human');
  assert.ok(bursts[0].durationMs >= 2_400, 'spans the typing period');
  a.dispose();
});

test('a file switch closes the open burst immediately', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.change(typing({ fileKey: 'src/a.py', charsAdded: 3 }));
  advanceTo(Date.now() + 100);
  a.change(typing({ fileKey: 'src/b.py', charsAdded: 5 }));

  assert.equal(bursts.length, 1, 'switching files closed the first burst');
  assert.equal(bursts[0].file, 'src/a.py');
  assert.equal(bursts[0].charsAdded, 3);
  a.dispose();
});

test('flush closes the open burst (session end / pause)', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();
  a.change(typing({ charsAdded: 7 }));
  a.flush();
  assert.equal(bursts.length, 1);
  assert.equal(bursts[0].charsAdded, 7);
  a.dispose();
});

test('undo-redo flag wins over every other origin signal', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.noteAiAccept(Date.now());
  a.notePaste(Date.now());
  a.change(typing({ charsAdded: 500, undoRedo: true }));
  a.flush();

  assert.equal(bursts[0].origin, 'undo-redo');
  a.dispose();
});

test('classifies ai when an accepted suggestion correlates within 500 ms', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.noteAiAccept(Date.now());
  advanceTo(Date.now() + 200);
  a.change(typing({ charsAdded: 40 })); // below the block threshold
  advanceTo(Date.now() + 2_500);

  assert.equal(bursts.length, 1);
  assert.equal(bursts[0].origin, 'ai');
  a.dispose();
});

test('an accepted suggestion outside the window does not mark later typing', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.noteAiAccept(Date.now());
  advanceTo(Date.now() + 5_000);
  a.change(typing());
  a.flush();

  assert.equal(bursts[0].origin, 'human');
  a.dispose();
});

test('classifies paste on clipboard correlation within 100 ms', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.notePaste(Date.now());
  advanceTo(Date.now() + 50);
  a.change(typing({ charsAdded: 30 }));
  a.flush();

  assert.equal(bursts[0].origin, 'paste');
  a.dispose();
});

test('a LARGE paste stays paste - direct evidence beats the block heuristic', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.notePaste(Date.now());
  a.change(typing({ charsAdded: 400 })); // also trips the >= 80-char rule
  a.flush();

  assert.equal(bursts[0].origin, 'paste');
  a.dispose();
});

test('ai-accept correlation outranks a simultaneous paste signal', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.notePaste(Date.now());
  a.noteAiAccept(Date.now());
  a.change(typing({ charsAdded: 120 }));
  a.flush();

  assert.equal(bursts[0].origin, 'ai');
  a.dispose();
});

test('classifies ai on a massive uncorrelated block (>= 80 chars in <= 50 ms)', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.change(typing({ charsAdded: 200, lines: 8 }));
  a.flush();

  assert.equal(bursts[0].origin, 'ai');
  a.dispose();
});

test('80 chars of ordinary typing spread over seconds stays human', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator({ gapMs: 2_000 });
  a.start();

  for (let i = 0; i < 100; i++) {
    a.change(typing());
    advanceTo(Date.now() + 100); // 10 chars/s - fast but human
  }
  advanceTo(Date.now() + 2_500);

  assert.equal(bursts.length, 1);
  assert.equal(bursts[0].charsAdded, 100);
  assert.equal(bursts[0].origin, 'human');
  a.dispose();
});

test('threshold chars arriving as several events inside 50 ms still count as ai', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.change(typing({ charsAdded: 45 }));
  advanceTo(Date.now() + 10);
  a.change(typing({ charsAdded: 45 }));
  a.flush();

  assert.equal(bursts[0].origin, 'ai');
  a.dispose();
});

test('thresholds are injectable (protocol-derived config, FR-PROT-4)', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator({ aiBlockCharThreshold: 500 });
  a.start();

  a.change(typing({ charsAdded: 200 }));
  a.flush();

  assert.equal(bursts[0].origin, 'human', 'below the raised threshold');
  a.dispose();
});

test('deletions and lines accumulate across the burst', () => {
  mock.timers.enable({ apis: ['Date', 'setInterval'], now: CLOCK_BASE });
  const { a, bursts } = aggregator();
  a.start();

  a.change(typing({ charsAdded: 5, charsDeleted: 2, lines: 1 }));
  advanceTo(Date.now() + 500);
  a.change(typing({ charsAdded: 0, charsDeleted: 10, lines: 2 }));
  a.flush();

  assert.equal(bursts[0].charsAdded, 5);
  assert.equal(bursts[0].charsDeleted, 12);
  assert.equal(bursts[0].linesTouched, 3);
  a.dispose();
});
