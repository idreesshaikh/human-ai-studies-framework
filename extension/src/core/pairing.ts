/**
 * vscode-free pairing state machine (FR-INST-20, NFR-3).
 *
 * States:
 *   idle               -  never paired, no pairing attempt in progress
 *   redeeming          -  /pair/redeem fetch in flight
 *   consent-pending    -  server responded; waiting for participant to accept
 *                       the consent statement (FR-AGENT-5)
 *   paired             -  pairing complete; identity + config applied,
 *                       awaiting session start
 *   capturing          -  a session is actively running under the paired config
 *
 * The ``unpaired-fallback`` is not a machine state but an outcome:
 * when the machine stays ``idle`` the adapter reads any legacy hand-typed
 * settings  -  the pre-pairing path continues working (wall #9).
 */

export type PairingState =
  'idle' | 'redeeming' | 'consent-pending' | 'paired' | 'capturing';

export type PairingEvent =
  | { type: 'REDEEM' }
  | { type: 'REDEEM_FAIL'; error: string }
  | { type: 'REDEEM_OK'; consentStatement: string; contentPolicy: string }
  | { type: 'CONSENT_ACCEPT' }
  | { type: 'CONSENT_DECLINE' }
  | { type: 'SESSION_START' }
  | { type: 'SESSION_END' }
  | { type: 'DISCONNECT' };

export interface PairingMachine {
  readonly state: PairingState;
  /** The consent statement shown at the consent-pending gate. */
  readonly consentStatement: string;
  /** The content policy active for this pairing. */
  readonly contentPolicy: string;
  /** Non-null only after a successful redeem. */
  readonly error: string | null;
}

export function createPairingMachine(): PairingMachine {
  return {
    state: 'idle',
    consentStatement: '',
    contentPolicy: '',
    error: null,
  };
}

export function transition(
  machine: PairingMachine,
  event: PairingEvent,
): PairingMachine {
  switch (machine.state) {
    case 'idle':
      if (event.type === 'REDEEM') {
        return { ...machine, state: 'redeeming', error: null };
      }
      return machine;

    case 'redeeming':
      if (event.type === 'REDEEM_FAIL') {
        return { ...machine, state: 'idle', error: event.error };
      }
      if (event.type === 'REDEEM_OK') {
        return {
          ...machine,
          state: 'consent-pending',
          consentStatement: event.consentStatement,
          contentPolicy: event.contentPolicy,
        };
      }
      return machine;

    case 'consent-pending':
      if (event.type === 'CONSENT_ACCEPT') {
        return {
          ...machine,
          state: 'paired',
          consentStatement: '',
          contentPolicy: '',
        };
      }
      if (event.type === 'CONSENT_DECLINE' || event.type === 'DISCONNECT') {
        return { ...machine, state: 'idle', error: null };
      }
      return machine;

    case 'paired':
      if (event.type === 'SESSION_START') {
        return { ...machine, state: 'capturing' };
      }
      if (event.type === 'DISCONNECT') {
        return { ...machine, state: 'idle' };
      }
      return machine;

    case 'capturing':
      if (event.type === 'SESSION_END') {
        return { ...machine, state: 'paired' };
      }
      if (event.type === 'DISCONNECT') {
        // Disconnect stops the session too.
        return { ...machine, state: 'idle' };
      }
      return machine;

    default:
      return machine;
  }
}

export function isPaired(state: PairingState): boolean {
  return state === 'paired' || state === 'capturing';
}
