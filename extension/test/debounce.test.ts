import { test, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import { FirstLastDebouncer, TrailingDebouncer } from '../src/core/debounce';
import { CLOCK_BASE, advanceTo } from './helpers';

afterEach(() => mock.timers.reset());

test('first-last: rapid tab-cycling emits first and last only', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const emitted: string[] = [];
  const d = new FirstLastDebouncer<string>(250, (v) => emitted.push(v));

  d.push('a.py');
  d.push('b.py');
  d.push('c.py');
  d.push('d.py');
  assert.deepEqual(emitted, ['a.py'], 'first emits immediately');

  advanceTo(Date.now() + 300);
  assert.deepEqual(emitted, ['a.py', 'd.py'], 'last emits after the window');
  d.dispose();
});

test('first-last: slow switching emits every value', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const emitted: string[] = [];
  const d = new FirstLastDebouncer<string>(250, (v) => emitted.push(v));

  d.push('a.py');
  advanceTo(Date.now() + 400);
  d.push('b.py');
  advanceTo(Date.now() + 400);

  assert.deepEqual(emitted, ['a.py', 'b.py']);
  d.dispose();
});

test('first-last: dispose drops the pending trailing value', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const emitted: string[] = [];
  const d = new FirstLastDebouncer<string>(250, (v) => emitted.push(v));

  d.push('a.py');
  d.push('b.py');
  d.dispose();
  advanceTo(Date.now() + 500);

  assert.deepEqual(emitted, ['a.py']);
});

test('trailing: only the resting scroll position emits', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const emitted: number[] = [];
  const d = new TrailingDebouncer<number>(500, (v) => emitted.push(v));

  for (let line = 0; line <= 100; line += 10) {
    d.push(line);
    advanceTo(Date.now() + 50);
  }
  assert.deepEqual(emitted, [], 'nothing emits mid-scroll');

  advanceTo(Date.now() + 600);
  assert.deepEqual(emitted, [100], 'the resting range emits once');
  d.dispose();
});
