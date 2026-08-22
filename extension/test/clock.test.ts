import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatRemaining, remainingSeconds } from '../src/core/clock';

test('countdown does not show a second early', () => {
  assert.equal(remainingSeconds(1_200), 2);
  assert.equal(remainingSeconds(1), 1);
  assert.equal(remainingSeconds(0), 0);
});

test('negative remaining time clamps to zero', () => {
  assert.equal(remainingSeconds(-500), 0);
  assert.equal(formatRemaining(-500), '0:00');
});

test('formats minutes and seconds for the status surface', () => {
  assert.equal(formatRemaining(60_000), '1:00');
  assert.equal(formatRemaining(61_200), '1:02');
  assert.equal(formatRemaining(3_661_000), '61:01');
});
