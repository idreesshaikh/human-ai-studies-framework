import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  disconnectBlockedReason,
  PAIRING_STATE_KEYS,
  PAIRED_SETTING_KEYS,
} from '../src/core/studyLink';

test('disconnect is blocked while a session is active', () => {
  assert.match(disconnectBlockedReason(true) ?? '', /end the session/i);
});

test('disconnect is allowed with no session', () => {
  assert.equal(disconnectBlockedReason(false), undefined);
});

test('disconnect clears every pairing state key, including the locked overlay', () => {
  for (const k of [
    'tern.paired',
    'tern.pairedStudyId',
    'tern.pairedParticipantId',
    'tern.pairedCondition',
    'tern.pairedIngestEndpoint',
    'tern.serverUrl',
    'tern.captureConfigVersion',
    'tern.legs',
    'tern.pendingConfigVersion',
    'tern.sessionBlock',
    'tern.sessionManifest',
    'tern.lockedSettings',
  ]) {
    assert.ok(PAIRING_STATE_KEYS.includes(k), k);
  }
});

test('disconnect resets the identity settings pairing wrote', () => {
  for (const k of ['studyId', 'participantId', 'output.httpEndpoint']) {
    assert.ok(PAIRED_SETTING_KEYS.includes(k), k);
  }
});
