import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  IdeHealthCollector,
  type IdeHealthConfig,
  type IdeHealthEvent,
} from '../src/core/ideHealth';

const FAST_DEBOUNCE: IdeHealthConfig = { debounceMs: 20 };

test('records and flushes error counts', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordDiagnostics(3, 5);
  c.flush();
  assert.equal(events.length, 1);
  assert.equal(events[0].errorCount, 3);
  assert.equal(events[0].warningCount, 5);
  assert.equal(events[0].buildInvocations, 0);
  assert.equal(events[0].testInvocations, 0);
  assert.equal(events[0].type, 'ide_health');
  assert.ok(events[0].seq > 0);
});

test('records and flushes build invocations', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordInvocation('build');
  c.recordInvocation('build');
  c.flush();
  assert.equal(events.length, 1);
  assert.equal(events[0].buildInvocations, 2);
});

test('records and flushes test invocations', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordInvocation('test');
  c.flush();
  assert.equal(events[0].testInvocations, 1);
});

test('flush after zero counts emits nothing', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.flush();
  assert.equal(events.length, 0);
});

test('flush resets counters to zero', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordDiagnostics(2, 3);
  c.flush();
  c.flush();
  assert.equal(events.length, 1);
});

test('multiple flushes produce multiple events with incrementing seq', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordDiagnostics(1, 0);
  c.flush();
  c.recordDiagnostics(0, 2);
  c.flush();
  assert.equal(events.length, 2);
  assert.equal(events[0].seq, 1);
  assert.equal(events[1].seq, 2);
});

test('snapshot returns current counts without flushing', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordDiagnostics(4, 6);
  const s = c.snapshot();
  assert.equal(s.errorCount, 4);
  assert.equal(s.warningCount, 6);
  assert.equal(events.length, 0, 'snapshot must not emit');
});

test('reset clears all state including sequence', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordDiagnostics(1, 0);
  c.flush();
  c.reset();
  c.recordDiagnostics(2, 0);
  c.flush();
  assert.equal(events.length, 2);
  assert.equal(
    events[1].seq,
    1,
    'seq resets to 0, first post-reset flush is seq 1',
  );
});

test('debounce fires after configured window', async () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordDiagnostics(1, 0);
  assert.equal(events.length, 0, 'not emitted before debounce window');
  await new Promise((r) => setTimeout(r, FAST_DEBOUNCE.debounceMs + 10));
  assert.equal(events.length, 1, 'emitted after debounce window');
  assert.equal(events[0].errorCount, 1);
});

test('debounce resets on new record within window', async () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordDiagnostics(1, 0);
  // Record again half-way through the debounce window  -  the timer resets.
  await new Promise((r) => setTimeout(r, FAST_DEBOUNCE.debounceMs / 2));
  c.recordDiagnostics(0, 2);
  await new Promise((r) => setTimeout(r, FAST_DEBOUNCE.debounceMs * 0.8));
  // The first timer (20ms) would have fired ~10ms ago, but the second
  // record at ~10ms reset it, so the real quiet window is ~20ms from the
  // second record = ~30ms total. At 16ms after the second record we should
  // still see nothing.
  assert.equal(events.length, 0, 'debounce timer was reset by second record');
  // Wait for the second timer to fire.
  await new Promise((r) => setTimeout(r, FAST_DEBOUNCE.debounceMs + 10));
  assert.equal(events.length, 1);
  // The event should carry the accumulated counts from both records.
  assert.equal(events[0].errorCount, 1);
  assert.equal(events[0].warningCount, 2);
});

test('collector can be disposed without error', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordDiagnostics(1, 0);
  c.dispose();
  // dispose flushes then silences further events.
  assert.equal(events.length, 1);
  c.recordDiagnostics(2, 0);
  c.flush();
  assert.equal(events.length, 1, 'no more events after dispose');
});

test('content-free: emitted event carries no diagnostic message, file path, or code content  -  FR-ETH-2', () => {
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e));
  c.recordDiagnostics(5, 3);
  c.flush();
  const json = JSON.stringify(events[0]);
  // The event must never carry diagnostic messages or file paths.
  assert.ok(!json.includes('"message"'), 'no message field');
  assert.ok(!json.includes('.ts'), 'no .ts file path');
  assert.ok(!json.includes('.py'), 'no .py file path');
  assert.ok(!json.includes('/src/'), 'no source path');
  assert.ok(!json.includes('file://'), 'no URI scheme');
  assert.ok(!json.includes('stack'), 'no stack trace');
  // Only the allowed numeric fields + metadata.
  const allowed = [
    'type',
    'ts',
    'mono',
    'seq',
    'errorCount',
    'warningCount',
    'buildInvocations',
    'testInvocations',
  ];
  for (const key of Object.keys(events[0])) {
    assert.ok(
      allowed.includes(key),
      `unexpected key "${key}" in ideHealth event`,
    );
  }
});

test('injected clock is used for event timestamps', () => {
  const time = 1_000_000;
  const clock = () => time;
  const events: IdeHealthEvent[] = [];
  const c = new IdeHealthCollector(FAST_DEBOUNCE, (e) => events.push(e), clock);
  c.recordDiagnostics(1, 0);
  c.flush();
  assert.equal(events[0].ts, 1000);
});
