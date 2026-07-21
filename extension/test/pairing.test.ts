import * as assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  createPairingMachine,
  transition,
  isPaired,
  type PairingMachine,
} from '../src/core/pairing';

describe('pairing state machine', () => {
  it('starts in idle state', () => {
    const m = createPairingMachine();
    assert.equal(m.state, 'idle');
    assert.equal(isPaired(m.state), false);
  });

  it('idle → redeeming on REDEEM', () => {
    const m = transition(createPairingMachine(), { type: 'REDEEM' });
    assert.equal(m.state, 'redeeming');
    assert.equal(isPaired(m.state), false);
  });

  it('idle ignores CONSENT_ACCEPT', () => {
    const m = transition(createPairingMachine(), { type: 'CONSENT_ACCEPT' });
    assert.equal(m.state, 'idle');
  });

  it('redeeming → consent-pending on REDEEM_OK', () => {
    let m = transition(createPairingMachine(), { type: 'REDEEM' });
    m = transition(m, {
      type: 'REDEEM_OK',
      consentStatement: 'You consent',
      contentPolicy: 'metadata-only',
    });
    assert.equal(m.state, 'consent-pending');
    assert.equal(m.consentStatement, 'You consent');
    assert.equal(m.contentPolicy, 'metadata-only');
  });

  it('redeeming → idle on REDEEM_FAIL', () => {
    let m = transition(createPairingMachine(), { type: 'REDEEM' });
    m = transition(m, { type: 'REDEEM_FAIL', error: 'network error' });
    assert.equal(m.state, 'idle');
    assert.equal(m.error, 'network error');
  });

  it('consent-pending → paired on CONSENT_ACCEPT', () => {
    let m = transition(createPairingMachine(), { type: 'REDEEM' });
    m = transition(m, {
      type: 'REDEEM_OK',
      consentStatement: '',
      contentPolicy: '',
    });
    m = transition(m, { type: 'CONSENT_ACCEPT' });
    assert.equal(m.state, 'paired');
    assert.equal(isPaired(m.state), true);
  });

  it('consent-pending → idle on CONSENT_DECLINE', () => {
    let m = transition(createPairingMachine(), { type: 'REDEEM' });
    m = transition(m, {
      type: 'REDEEM_OK',
      consentStatement: '',
      contentPolicy: '',
    });
    m = transition(m, { type: 'CONSENT_DECLINE' });
    assert.equal(m.state, 'idle');
  });

  it('consent-pending → idle on DISCONNECT', () => {
    let m = transition(createPairingMachine(), { type: 'REDEEM' });
    m = transition(m, {
      type: 'REDEEM_OK',
      consentStatement: '',
      contentPolicy: '',
    });
    m = transition(m, { type: 'DISCONNECT' });
    assert.equal(m.state, 'idle');
  });

  it('paired → capturing on SESSION_START', () => {
    let m = transition(createPairingMachine(), { type: 'REDEEM' });
    m = transition(m, {
      type: 'REDEEM_OK',
      consentStatement: '',
      contentPolicy: '',
    });
    m = transition(m, { type: 'CONSENT_ACCEPT' });
    m = transition(m, { type: 'SESSION_START' });
    assert.equal(m.state, 'capturing');
    assert.equal(isPaired(m.state), true);
  });

  it('paired → idle on DISCONNECT', () => {
    let m = transition(createPairingMachine(), { type: 'REDEEM' });
    m = transition(m, {
      type: 'REDEEM_OK',
      consentStatement: '',
      contentPolicy: '',
    });
    m = transition(m, { type: 'CONSENT_ACCEPT' });
    m = transition(m, { type: 'DISCONNECT' });
    assert.equal(m.state, 'idle');
  });

  it('capturing → paired on SESSION_END', () => {
    let m = _pairedAndCapturing();
    m = transition(m, { type: 'SESSION_END' });
    assert.equal(m.state, 'paired');
  });

  it('capturing → idle on DISCONNECT', () => {
    let m = _pairedAndCapturing();
    m = transition(m, { type: 'DISCONNECT' });
    assert.equal(m.state, 'idle');
  });

  it('unknown events in a state are ignored', () => {
    let m = _pairedAndCapturing();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    m = transition(m, { type: 'REDEEM' } as any);
    assert.equal(m.state, 'capturing');
  });
});

function _pairedAndCapturing(): PairingMachine {
  let m = transition(createPairingMachine(), { type: 'REDEEM' });
  m = transition(m, {
    type: 'REDEEM_OK',
    consentStatement: '',
    contentPolicy: '',
  });
  m = transition(m, { type: 'CONSENT_ACCEPT' });
  m = transition(m, { type: 'SESSION_START' });
  return m;
}
