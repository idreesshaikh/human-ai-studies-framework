import { test } from 'node:test';
import assert from 'node:assert/strict';
import { preflightSummary } from '../src/core/preflight';

test('summarizes the known capture toggles as on/off', () => {
  const items = preflightSummary({
    'stuck.enabled': true,
    'behavior.captureClipboard': false,
    'behavior.captureEditBursts': true,
  });
  const byKey = Object.fromEntries(items.map((i) => [i.key, i]));
  assert.equal(byKey['stuck.enabled'].on, true);
  assert.equal(byKey['stuck.enabled'].label, 'Stuck detection');
  assert.equal(byKey['behavior.captureClipboard'].on, false);
});

test('a toggle absent from the config is reported off', () => {
  const items = preflightSummary({});
  assert.ok(items.every((i) => i.on === false));
  assert.ok(items.length > 0);
});
