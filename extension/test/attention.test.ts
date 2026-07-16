import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  AttentionTracker,
  AttentionConfig,
  AttentionEvent,
  DEFAULT_ATTENTION_CONFIG,
} from '../src/core/attention';

function tracker(over: Partial<AttentionConfig> = {}): {
  t: AttentionTracker;
  events: AttentionEvent[];
} {
  const events: AttentionEvent[] = [];
  const t = new AttentionTracker(
    { ...DEFAULT_ATTENTION_CONFIG, ...over },
    (e) => events.push(e),
  );
  return { t, events };
}

test('caret dwell accrues time and emits on moving out of the band', () => {
  const { t, events } = tracker();
  t.look('cursor', 'a.py', 40, 1_000);
  t.look('cursor', 'a.py', 50, 6_000); // beyond radius 3 => new region
  assert.equal(events.length, 1);
  assert.equal(events[0].file, 'a.py');
  assert.equal(events[0].focusMs, 5_000);
  assert.equal(events[0].cursorMs, 5_000);
  assert.equal(events[0].hoverMs, 0);
  assert.equal(events[0].mode, 'reading');
  assert.equal(events[0].exitReason, 'moved-away');
  assert.equal(events[0].startLine, 37);
  assert.equal(events[0].endLine, 43);
});

test('movement within the radius band stays the same region', () => {
  const { t, events } = tracker();
  t.look('cursor', 'a.py', 40, 1_000);
  t.look('cursor', 'a.py', 42, 3_000); // within +/- 3
  t.look('cursor', 'a.py', 41, 5_000); // still within
  t.flush(6_000);
  assert.equal(events.length, 1);
  assert.equal(events[0].focusMs, 5_000);
  assert.equal(events[0].exitReason, 'session-end');
});

test('a file switch closes the region with exitReason=file-switch', () => {
  const { t, events } = tracker();
  t.look('cursor', 'a.py', 10, 1_000);
  t.look('cursor', 'b.py', 10, 4_000);
  assert.equal(events.length, 1);
  assert.equal(events[0].file, 'a.py');
  assert.equal(events[0].focusMs, 3_000);
  assert.equal(events[0].exitReason, 'file-switch');
});

test('idle / blur pauses the clock so away-time is not counted', () => {
  const { t, events } = tracker();
  t.look('cursor', 'a.py', 10, 1_000);
  t.setPresent(false, 3_000); // banks 2 000 ms, then pauses
  t.setPresent(true, 10_000); // 7 s away, not counted
  t.look('cursor', 'a.py', 20, 12_000); // +2 000 ms after resume
  assert.equal(events.length, 1);
  assert.equal(events[0].focusMs, 4_000);
});

test('mouse hover accrues reading time with no caret movement', () => {
  const { t, events } = tracker();
  t.look('hover', 'a.py', 10, 1_000);
  t.flush(4_000);
  assert.equal(events.length, 1);
  assert.equal(events[0].hoverMs, 3_000);
  assert.equal(events[0].cursorMs, 0);
  assert.equal(events[0].mode, 'reading');
});

test('an edit in the region marks mode=editing', () => {
  const { t, events } = tracker();
  t.look('cursor', 'a.py', 10, 1_000);
  t.edit('a.py', 10, 2_000);
  t.flush(5_000);
  assert.equal(events.length, 1);
  assert.equal(events[0].edited, true);
  assert.equal(events[0].mode, 'editing');
});

test('caret + hover on the same region classifies as mixed', () => {
  const { t, events } = tracker();
  t.look('cursor', 'a.py', 10, 1_000);
  t.look('hover', 'a.py', 11, 3_000); // same band: bank 2 000 to cursor, switch
  t.flush(5_000); // bank 2 000 to hover
  assert.equal(events.length, 1);
  assert.equal(events[0].cursorMs, 2_000);
  assert.equal(events[0].hoverMs, 2_000);
  assert.equal(events[0].mode, 'mixed');
});

test('pass-through glances below minDwell are dropped', () => {
  const { t, events } = tracker();
  t.look('cursor', 'a.py', 10, 1_000);
  t.look('cursor', 'a.py', 20, 1_500); // 500 ms < 1 500 ms floor
  assert.equal(events.length, 0);
});

test('setPresent with no open region is a no-op (never throws)', () => {
  const { t, events } = tracker();
  assert.doesNotThrow(() => {
    t.setPresent(false, 1_000);
    t.setPresent(true, 2_000);
    t.flush(3_000);
  });
  assert.equal(events.length, 0);
});

test('sanitizes a negative region radius to 0 (each line its own region)', () => {
  const { t, events } = tracker({ regionRadiusLines: -5 });
  t.look('cursor', 'a.py', 10, 1_000);
  t.look('cursor', 'a.py', 11, 3_000); // one line away => new region at radius 0
  assert.equal(events.length, 1);
  assert.equal(events[0].startLine, 10);
  assert.equal(events[0].endLine, 10);
  assert.equal(events[0].focusMs, 2_000);
});

test('sanitizes a NaN minDwell to 0 (no glance is dropped)', () => {
  const { t, events } = tracker({ minDwellMs: NaN });
  t.look('cursor', 'a.py', 10, 1_000);
  t.flush(1_100);
  assert.equal(events.length, 1);
  assert.equal(events[0].focusMs, 100);
});

test('flush carries a distinct session-pause exit reason', () => {
  const { t, events } = tracker();
  t.look('cursor', 'a.py', 10, 1_000);
  t.flush(4_000, 'session-pause');
  assert.equal(events.length, 1);
  assert.equal(events[0].exitReason, 'session-pause');
});
