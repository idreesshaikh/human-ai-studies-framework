import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  IDENTITY_KEYS,
  extensionDefaults,
  buildLockedConfig,
} from '../src/core/lockedConfig';

test('overlay beats extension default', () => {
  const cfg = buildLockedConfig({
    defaults: { 'stuck.enabled': false },
    overlay: { 'stuck.enabled': true },
    paired: true,
  });
  assert.equal(cfg.get('stuck.enabled', false), true);
});

test('issue #38 regression: an undeclared overlay key falls back to the extension default, not to any participant-supplied value', () => {
  // The pilot study protocol declares no `behavior` block at all, so the
  // overlay carries no `behavior.*` key  -  this is exactly the gap that let
  // a participant's own settings leak through before the lock existed.
  const cfg = buildLockedConfig({
    defaults: { 'behavior.captureClipboard': true },
    overlay: { participantId: 'P01', 'stuck.enabled': true },
    paired: true,
  });
  assert.equal(cfg.get('behavior.captureClipboard', false), true);
});

test('unpaired: locked is false and get returns the caller fallback', () => {
  const cfg = buildLockedConfig({
    defaults: { 'stuck.enabled': true },
    overlay: { 'stuck.enabled': false },
    paired: false,
  });
  assert.equal(cfg.locked, false);
  assert.equal(cfg.get('stuck.enabled', 'fallback'), 'fallback');
  assert.equal(cfg.has('stuck.enabled'), false);
  assert.deepEqual(cfg.keys(), []);
});

test('an IDENTITY_KEYS member present in the overlay is excluded from the lock', () => {
  const cfg = buildLockedConfig({
    defaults: {},
    overlay: { 'output.httpEndpoint': 'http://participant-supplied/ingest' },
    paired: true,
  });
  assert.equal(cfg.has('output.httpEndpoint'), false);
  assert.equal(
    cfg.get('output.httpEndpoint', 'server-issued'),
    'server-issued',
  );
});

test('get returns the call-site fallback for a key in neither defaults nor overlay', () => {
  const cfg = buildLockedConfig({
    defaults: { 'stuck.enabled': true },
    overlay: {},
    paired: true,
  });
  assert.equal(cfg.get('fatigue.intervalMinutes', 15), 15);
});

test('a locked value of false or 0 is returned as-is, not swallowed as missing', () => {
  const cfg = buildLockedConfig({
    defaults: {},
    overlay: {
      'behavior.captureClipboard': false,
      'fatigue.jitterPercent': 0,
    },
    paired: true,
  });
  assert.equal(cfg.get('behavior.captureClipboard', true), false);
  assert.equal(cfg.get('fatigue.jitterPercent', 20), 0);
  assert.equal(cfg.lockedValue('behavior.captureClipboard'), false);
  assert.equal(cfg.lockedValue('fatigue.jitterPercent'), 0);
});

// ------------------------------------------------------ extensionDefaults

test('extensionDefaults parses a realistic package.json shape', () => {
  const packageJSON = {
    contributes: {
      configuration: {
        title: 'TERN',
        properties: {
          'tern.participantId': { type: 'string', default: '' },
          'tern.stuck.enabled': { type: 'boolean', default: true },
          'tern.behavior.captureClipboard': {
            type: 'boolean',
            default: true,
          },
          'tern.session.durationMinutes': { type: 'number', default: 60 },
          'not.tern.something': { type: 'string', default: 'ignored' },
          'tern.noDefault.here': { type: 'string' },
        },
      },
    },
  };
  const defaults = extensionDefaults(packageJSON);
  assert.deepEqual(defaults, {
    participantId: '',
    'stuck.enabled': true,
    'behavior.captureClipboard': true,
    'session.durationMinutes': 60,
  });
  assert.equal(Object.hasOwn(defaults, 'noDefault.here'), false);
});

test('extensionDefaults never throws and returns {} for malformed input', () => {
  for (const bad of [
    undefined,
    null,
    'a string',
    {},
    { contributes: { configuration: null } },
  ]) {
    assert.deepEqual(extensionDefaults(bad), {});
  }
});

// ------------------------------------------------------ immutability

test('the result is immutable: mutating what keys() returns does not affect the lock', () => {
  const cfg = buildLockedConfig({
    defaults: { 'stuck.enabled': true },
    overlay: {},
    paired: true,
  });
  const k = cfg.keys();
  k.push('injected');
  assert.deepEqual(cfg.keys(), ['stuck.enabled']);
  assert.equal(cfg.has('injected'), false);
});

test('IDENTITY_KEYS contains exactly the six protocol-excluded keys', () => {
  assert.deepEqual(
    [...IDENTITY_KEYS].sort(),
    [
      'condition',
      'output.directory',
      'output.httpEndpoint',
      'participantId',
      'session.id',
      'studyId',
    ].sort(),
  );
});

test('hazard: an identity key resolves to the caller fallback, never to a value', () => {
  // Why this matters, and it cost a regression once: reading an identity key
  // through the lock does not return the protocol value and does not return the
  // participant's value  -  it returns whatever fallback the call site passed.
  // For the ingest endpoint that fallback is '', and an empty endpoint means
  // bootSession builds no HttpSink at all, so a paired session would record
  // locally and silently send nothing. Callers must take these from the pairing
  // redeem (getPairedIdentity), not from cfg()/captureSetting().
  const cfg = buildLockedConfig({
    defaults: { 'output.httpEndpoint': 'http://from-extension-default' },
    overlay: { 'output.httpEndpoint': 'http://from-protocol-example' },
    paired: true,
  });
  assert.equal(cfg.has('output.httpEndpoint'), false);
  assert.equal(cfg.get('output.httpEndpoint', ''), '');
  assert.equal(cfg.get('output.httpEndpoint', 'FALLBACK'), 'FALLBACK');
  for (const key of IDENTITY_KEYS) {
    assert.equal(cfg.get(key, 'FALLBACK'), 'FALLBACK', key);
  }
});
