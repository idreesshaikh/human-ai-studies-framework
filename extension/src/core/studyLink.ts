/**
 * What it takes to leave a study. Kept free of `vscode` so the rules are
 * testable: disconnecting is refused mid-session, and must clear everything
 * pairing stored so no stale locked configuration outlives the link.
 */

/** Extension-state keys (global + workspace) written by pairing. */
export const PAIRING_STATE_KEYS: readonly string[] = [
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
];

/** Workspace `tern.*` settings that pairing writes besides the protocol overlay. */
export const PAIRED_SETTING_KEYS: readonly string[] = [
  'studyId',
  'participantId',
  'condition',
  'output.httpEndpoint',
];

/** Why disconnecting is not allowed right now, or undefined if it is. */
export function disconnectBlockedReason(
  sessionActive: boolean,
): string | undefined {
  return sessionActive
    ? 'A study session is running. End the session before disconnecting from the study.'
    : undefined;
}
