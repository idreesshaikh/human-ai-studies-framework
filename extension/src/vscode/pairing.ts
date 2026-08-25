import * as vscode from 'vscode';
import * as path from 'path';
import { decodeConnectionString } from '../core/connectionString';
import {
  CaptureConfig,
  SessionBlock,
  overlayFlags,
  readBlock,
  shouldApplyCaptureConfig,
} from '../core/captureConfig';
import { preflightSummary } from '../core/preflight';
import { ConsentGate } from '../core/consentGate';

const SECRET_CRED = 'tern.sessionCredential';
const STATE_SERVER = 'tern.serverUrl';
export const STATE_STUDY_ID = 'tern.pairedStudyId';
export const STATE_PARTICIPANT_ID = 'tern.pairedParticipantId';
export const STATE_CONDITION = 'tern.pairedCondition';
export const STATE_INGEST_ENDPOINT = 'tern.pairedIngestEndpoint';
export const STATE_PAIRED = 'tern.paired';
const STATE_VERSION = 'tern.captureConfigVersion';
/** The leg summary from the config currently *in force*  -  what the sidebar
 *  (FR-INST-22) renders. Written only where the config is actually applied,
 *  so the surface can never claim a leg is running before it is. */
export const STATE_LEGS = 'tern.legs';
/** Set when the server has a newer config than the one in force  -  i.e. a
 *  researcher amended the study mid-session. Wall #6 says it lands at the
 *  next session start, so the sidebar shows it as pending rather than
 *  silently implying the change already took effect. */
export const STATE_PENDING = 'tern.pendingConfigVersion';
/** The task block this session was assigned  -  what the sidebar shows the
 *  participant so they know what they have been asked to do. */
export const STATE_BLOCK = 'tern.sessionBlock';
/** The full manifest for facilitator-visible producer state and external runners. */
export const STATE_MANIFEST = 'tern.sessionManifest';

export interface PairedIdentity {
  studyId: string;
  participantId: string;
  condition: string;
  ingestEndpoint: string;
}

/** Pairing survives the deliberate workspace switch to the assigned task.
 * Workspace state is retained as a local mirror for older sessions, while
 * global state carries the link across `vscode.openFolder`. */
export function pairingState<T>(
  context: vscode.ExtensionContext,
  key: string,
): T | undefined {
  return context.globalState.get<T>(key) ?? context.workspaceState.get<T>(key);
}

async function persistPairingState(
  context: vscode.ExtensionContext,
  key: string,
  value: unknown,
): Promise<void> {
  await Promise.all([
    context.globalState.update(key, value),
    context.workspaceState.update(key, value),
  ]);
}

interface RedeemResult {
  studyId: string;
  participantId: string;
  condition: string;
  sessionCredential: string;
  ingestEndpoint: string;
  captureConfig: CaptureConfig;
  consentStatement: string;
  contentPolicy: string;
}

/** Identity/transport keys resolved from the redeem, NOT from the protocol  -
 * applyConfig must never clobber them (else a session-start refresh would
 * reset the paired endpoint to the protocol's example value). */
const IDENTITY_KEYS = new Set([
  'participantId',
  'condition',
  'output.httpEndpoint',
]);

/** Apply a capture config's overlay flags into `tern.*` settings
 * (workspace scope). Called only at a session boundary (wall #6). */
async function applyConfig(cfg: CaptureConfig): Promise<void> {
  const flags = overlayFlags(cfg);
  const conf = vscode.workspace.getConfiguration('tern');
  for (const [key, value] of Object.entries(flags)) {
    if (IDENTITY_KEYS.has(key)) continue; // identity/endpoint come from the redeem
    await conf.update(key, value, vscode.ConfigurationTarget.Workspace);
  }
}

/** The credential last stored by a successful pairing, or undefined if this
 * IDE has never paired. Read-only  -  does not touch the network. */
export async function getStoredCredential(
  context: vscode.ExtensionContext,
): Promise<string | undefined> {
  return context.secrets.get(SECRET_CRED);
}

/** The server-issued identity for a paired participant. Never read these
 * values back from editable VS Code settings. */
export function getPairedIdentity(
  context: vscode.ExtensionContext,
): PairedIdentity | undefined {
  if (!pairingState<boolean>(context, STATE_PAIRED)) return undefined;
  const studyId = pairingState<string>(context, STATE_STUDY_ID) ?? '';
  const participantId =
    pairingState<string>(context, STATE_PARTICIPANT_ID) ?? '';
  const condition = pairingState<string>(context, STATE_CONDITION) ?? '';
  const ingestEndpoint =
    pairingState<string>(context, STATE_INGEST_ENDPOINT) ?? '';
  if (!studyId || !participantId || !condition) return undefined;
  return { studyId, participantId, condition, ingestEndpoint };
}

/** Re-pull the study's capture config at a session boundary and apply it if
 * the version changed AND no session is active (wall #6  -  see
 * `shouldApplyCaptureConfig`). `sessionActive` is the caller's own liveness
 * flag (e.g. `Boolean(study)`); the only real call site passes `false`
 * because it runs before the clock arms, but the guard fails closed even if
 * a future call site got that wrong. No-op when unpaired. Returns the
 * credential to use for the session's HttpSink, or undefined when unpaired. */
export async function refreshConfigAtSessionStart(
  context: vscode.ExtensionContext,
  sessionActive: boolean,
  sessionId?: string,
): Promise<string | undefined> {
  const cred = await context.secrets.get(SECRET_CRED);
  const server = pairingState<string>(context, STATE_SERVER);
  const paired = getPairedIdentity(context);
  const studyId =
    paired?.studyId ??
    vscode.workspace.getConfiguration('tern').get<string>('studyId');
  if (!cred || !server || !studyId) return cred ?? undefined;
  try {
    // The session id lets the server assign (and remember) this session's
    // task block. Sending it is what makes the assignment idempotent: a
    // re-pull for a session already under way returns the same block rather
    // than advancing the participant to the next one.
    const url = new URL(`${server}/studies/${studyId}/capture-config`);
    if (sessionId) url.searchParams.set('sessionId', sessionId);
    const res = await fetch(url, {
      headers: { authorization: `Bearer ${cred}` },
    });
    if (res.ok) {
      const cfg = (await res.json()) as CaptureConfig;
      // The assigned block is display state, not capture config: it is
      // stored whatever wall #6 decides about the settings, because what the
      // participant is asked to do this session is true either way.
      await persistPairingState(context, STATE_BLOCK, readBlock(cfg));
      await persistPairingState(context, STATE_MANIFEST, cfg.sessionManifest);
      const applied = pairingState<string>(context, STATE_VERSION);
      if (
        !sessionActive &&
        (Boolean(paired) ||
          shouldApplyCaptureConfig(
            sessionActive,
            applied,
            cfg.captureConfigVersion,
          ))
      ) {
        await applyConfig(cfg);
        if (paired) {
          await enforcePairedSettings(paired);
        }
        await persistPairingState(
          context,
          STATE_VERSION,
          cfg.captureConfigVersion,
        );
        await persistPairingState(context, STATE_LEGS, cfg.legs);
        await persistPairingState(context, STATE_PENDING, undefined);
      } else {
        // Not applied. Either nothing changed, or a change arrived mid-session
        // and wall #6 holds it until the next start  -  record which, so the
        // sidebar can say so instead of showing stale state as current.
        await persistPairingState(
          context,
          STATE_PENDING,
          cfg.captureConfigVersion === applied
            ? undefined
            : cfg.captureConfigVersion,
        );
      }
    }
  } catch {
    // Never block a session on a config refresh  -  last-applied config stands.
  }
  return cred;
}

/** Redeem a connection string, gate on consent, persist identity + the
 * credential, apply the initial capture config, and show the pre-flight
 * summary. Shared by the `connectToStudy` command and the `vscode://…/pair`
 * URI handler  -  one redeem path, no second mechanism. */
export async function pairFromConnectionString(
  context: vscode.ExtensionContext,
  raw: string,
  onPaired?: () => void,
): Promise<void> {
  let conn;
  try {
    conn = decodeConnectionString(raw);
  } catch (e) {
    void vscode.window.showErrorMessage((e as Error).message);
    return;
  }
  let result: RedeemResult;
  try {
    const res = await fetch(`${conn.serverUrl}/pair/redeem`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ token: conn.token }),
    });
    if (!res.ok) {
      void vscode.window.showErrorMessage(
        `Could not connect: ${res.status === 410 ? 'this link is invalid, used, or expired.' : `server said ${res.status}.`}`,
      );
      return;
    }
    result = (await res.json()) as RedeemResult;
  } catch {
    void vscode.window.showErrorMessage(
      'Could not reach the study server. Check your connection.',
    );
    return;
  }

  // Consent gate  -  show the statement + policy, require explicit acceptance.
  const gate = new ConsentGate(result.consentStatement, result.contentPolicy);
  const choice = await vscode.window.showInformationMessage(
    result.consentStatement,
    { modal: true },
    'I consent',
  );
  if (choice !== 'I consent') return;
  gate.acknowledge();

  // Persist identity + credential (SecretStorage for the secret) and apply config.
  await context.secrets.store(SECRET_CRED, result.sessionCredential);
  await persistPairingState(context, STATE_SERVER, conn.serverUrl);
  await persistPairingState(context, STATE_STUDY_ID, result.studyId);
  await persistPairingState(
    context,
    STATE_PARTICIPANT_ID,
    result.participantId,
  );
  await persistPairingState(context, STATE_CONDITION, result.condition);
  await persistPairingState(
    context,
    STATE_INGEST_ENDPOINT,
    result.ingestEndpoint,
  );
  await persistPairingState(context, STATE_PAIRED, true);
  await persistPairingState(
    context,
    STATE_VERSION,
    result.captureConfig.captureConfigVersion,
  );
  await persistPairingState(context, STATE_LEGS, result.captureConfig.legs);
  await persistPairingState(
    context,
    STATE_MANIFEST,
    result.captureConfig.sessionManifest,
  );
  await persistPairingState(
    context,
    STATE_BLOCK,
    readBlock(result.captureConfig),
  );
  await persistPairingState(context, STATE_PENDING, undefined);
  const conf = vscode.workspace.getConfiguration('tern');
  await conf.update(
    'studyId',
    result.studyId,
    vscode.ConfigurationTarget.Workspace,
  );
  await conf.update(
    'participantId',
    result.participantId,
    vscode.ConfigurationTarget.Workspace,
  );
  await conf.update(
    'output.httpEndpoint',
    result.ingestEndpoint,
    vscode.ConfigurationTarget.Workspace,
  );
  await applyConfig(result.captureConfig);
  await enforcePairedSettings({
    studyId: result.studyId,
    participantId: result.participantId,
    condition: result.condition,
    ingestEndpoint: result.ingestEndpoint,
  });

  // The redeem payload includes the first assigned task when the protocol
  // declares one. Open a local task workspace before the participant starts;
  // repository URLs remain informational and are never executed or cloned.
  const initialBlock = readBlock(result.captureConfig);
  if (initialBlock) await openAssignedWorkspace(initialBlock);
  else {
    await refreshConfigAtSessionStart(context, false);
    const refreshedBlock = pairingState<SessionBlock>(context, STATE_BLOCK);
    if (refreshedBlock) await openAssignedWorkspace(refreshedBlock);
  }
  onPaired?.();

  // Pre-flight summary (before any session starts).
  const items = preflightSummary(overlayFlags(result.captureConfig));
  const on =
    items
      .filter((i) => i.on)
      .map((i) => i.label)
      .join(', ') || 'nothing';
  void vscode.window.showInformationMessage(
    `Study connected for ${result.participantId}. This study will capture: ${on}. Run “TERN: Start session” when you're ready.`,
  );
}

export async function enforcePairedSettings(
  identity: PairedIdentity,
): Promise<void> {
  const conf = vscode.workspace.getConfiguration('tern');
  const target = vscode.ConfigurationTarget.Workspace;
  await conf.update('studyId', identity.studyId, target);
  await conf.update('participantId', identity.participantId, target);
  // Do not write the assigned arm into editable workspace settings. The
  // recorder receives it from the pairing lock, while leaving it here would
  // let participants discover the blind through Settings or settings.json.
  await conf.update('condition', undefined, target);
  if (identity.ingestEndpoint) {
    await conf.update('output.httpEndpoint', identity.ingestEndpoint, target);
  }
}

/** Open only an explicit local folder supplied as task materials. */
async function openAssignedWorkspace(block: SessionBlock): Promise<void> {
  const raw = block.materials.trim();
  if (!raw) return;
  let folder: vscode.Uri | undefined;
  if (raw.startsWith('file://')) {
    try {
      folder = vscode.Uri.parse(raw);
    } catch {
      return;
    }
  } else if (path.isAbsolute(raw)) {
    folder = vscode.Uri.file(raw);
  }
  if (!folder) return;
  const current = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
  if (current && path.resolve(current) === path.resolve(folder.fsPath)) return;
  try {
    await vscode.commands.executeCommand('vscode.openFolder', folder, false);
  } catch {
    void vscode.window.showWarningMessage(
      'Study connected, but the assigned workspace could not be opened automatically.',
    );
  }
}

export function registerPairing(
  context: vscode.ExtensionContext,
  onPaired?: () => void,
): vscode.Disposable {
  return vscode.commands.registerCommand('tern.connectToStudy', async () => {
    if (getPairedIdentity(context)) {
      void vscode.window.showInformationMessage(
        'This editor is already connected to a study. Ask the researcher before changing study access.',
      );
      return;
    }
    const raw = await vscode.window.showInputBox({
      title: 'Connect to study',
      prompt: 'Paste the connection string your researcher gave you',
      ignoreFocusOut: true,
    });
    if (!raw) return;
    await pairFromConnectionString(context, raw, onPaired);
    // Keep the command boundary explicit as well as the shared redeem path:
    // TreeViews can be mounted after the async consent flow returns, so a
    // refresh at the command boundary guarantees the participant sees the
    // newly applied capture scope immediately.
    onPaired?.();
  });
}
