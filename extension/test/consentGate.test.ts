import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ConsentGate, ConsentNotGivenError } from '../src/core/consentGate';

test('blocks until acknowledged, then allows', () => {
  const g = new ConsentGate('You are joining...', 'metadata-only');
  assert.equal(g.accepted, false);
  assert.throws(() => g.assertAccepted(), ConsentNotGivenError);
  g.acknowledge();
  assert.equal(g.accepted, true);
  assert.doesNotThrow(() => g.assertAccepted());
});

test('carries the statement and policy verbatim', () => {
  const g = new ConsentGate('Statement text', 'redacted');
  assert.equal(g.statement, 'Statement text');
  assert.equal(g.policy, 'redacted');
});
