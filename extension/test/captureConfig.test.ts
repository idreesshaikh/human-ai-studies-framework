import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  overlayFlags,
  configChanged,
  CaptureConfig,
} from '../src/core/captureConfig';

const CFG: CaptureConfig = {
  captureConfigVersion: 'abc123',
  producer: 'overlay',
  settings: {
    'cognitiveOverlay.participantId': 'P01',
    'cognitiveOverlay.stuck.enabled': true,
    'cognitiveOverlay.behavior.captureClipboard': false,
  },
};

test('overlayFlags strips the cognitiveOverlay prefix', () => {
  const f = overlayFlags(CFG);
  assert.equal(f['participantId'], 'P01');
  assert.equal(f['stuck.enabled'], true);
  assert.equal(f['behavior.captureClipboard'], false);
  assert.equal(Object.hasOwn(f, 'cognitiveOverlay.participantId'), false);
});

test('configChanged is true only when the version differs', () => {
  assert.equal(configChanged(undefined, 'abc123'), true);
  assert.equal(configChanged('abc123', 'abc123'), false);
  assert.equal(configChanged('old', 'abc123'), true);
});
