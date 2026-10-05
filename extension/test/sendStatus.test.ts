import { test } from 'node:test';
import assert from 'node:assert/strict';
import { describeSend } from '../src/core/sendStatus';

const now = 1_000_000;

test('says nothing is confirmed when no send has succeeded', () => {
  const r = describeSend({ lastSuccessAt: undefined, pending: 0 }, now);
  assert.equal(r.detail, 'No send yet');
});

test('reports last successful send age', () => {
  const r = describeSend({ lastSuccessAt: now - 30_000, pending: 0 }, now);
  assert.equal(r.detail, 'Last sent 30s ago');
  assert.equal(r.warn, false);
});

test('reports minutes for older sends', () => {
  const r = describeSend({ lastSuccessAt: now - 5 * 60_000, pending: 0 }, now);
  assert.equal(r.detail, 'Last sent 5m ago');
});

test('pending events are shown and flagged', () => {
  const r = describeSend({ lastSuccessAt: now - 1000, pending: 4 }, now);
  assert.equal(r.detail, 'Last sent 1s ago, 4 not yet sent');
  assert.equal(r.warn, true);
});
