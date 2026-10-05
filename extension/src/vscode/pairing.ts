import * as vscode from 'vscode';
import * as fs from 'fs';
import * as os from 'os';
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
import {
  PAIRED_SETTING_KEYS,
  PAIRING_STATE_KEYS,
  disconnectBlockedReason,
} from '../core/studyLink';
import { setActiveLock } from './configLock';
import { openStudyFolder } from '../core/workspaceOpen';
import { fetchAndUnpack } from '../core/workspaceArchive';

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
/** The `tern.`-stripped settings from the capture config last actually applied.
 *  A session's locked config is built from these, so what governs capture is
 *  the researcher's protocol rather than whatever the settings file says once
 *  the participant has been at it (issue #38). */
export const STATE_LOCKED_SETTINGS = 'tern.lockedSettings';

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

/** Workspace-scoped settings can only be written once a folder or workspace is
 *  open; with none, VS Code throws "no workspace is opened". A participant
 *  pairing from an empty window is the normal case (the study folder opens
 *  right after), so pairing skips these writes and `reapplyPairedSettings`
 *  makes them once the folder is open. */
export function hasWorkspace(): boolean {
  return (
    (vscode.workspace.workspaceFolders?.length ?? 0) > 0 ||
    vscode.workspace.workspaceFile !== undefined
  );
}

/** Run a workspace-settings write without letting it abort pairing. A folder
 *  that cannot take a `.vscode/settings.json` (read-only, owned by another
 *  user) must not stop the participant joining or the study folder opening:
 *  identity and locked settings live in extension state, not in that file. */
async function bestEffort(write: () => Promise<void>): Promise<void> {
  try {
    await write();
  } catch (e) {
    console.warn('TERN: could not write workspace settings:', e);
  }
}

/** Write a flat `tern.*` map into workspace settings, skipping values already
 *  in place so an activation does not rewrite settings.json every time. */
async function writeWorkspaceFlags(
  flags: Record<string, unknown>,
): Promise<void> {
  if (!hasWorkspace()) return;
  const conf = vscode.workspace.getConfiguration('tern');
  for (const [key, value] of Object.entries(flags)) {
    if (IDENTITY_KEYS.has(key)) continue; // identity/endpoint come from the redeem
    if (
      JSON.stringify(conf.inspect(key)?.workspaceValue) ===
      JSON.stringify(value)
    ) {
      continue;
    }
    await bestEffort(() =>
      Promise.resolve(
        conf.update(key, value, vscode.ConfigurationTarget.Workspace),
      ),
    );
  }
}

/** Apply a capture config's overlay flags into `tern.*` settings
 * (workspace scope). Called only at a session boundary (wall #6). The flags are
 * always remembered, so a pairing from an empty window still locks them. */
async function applyConfig(
  context: vscode.ExtensionContext,
  cfg: CaptureConfig,
): Promise<void> {
  const flags = overlayFlags(cfg);
  await writeWorkspaceFlags(flags);
  await persistPairingState(context, STATE_LOCKED_SETTINGS, flags);
}

/** On activation in a window that now has a folder (typically right after the
 *  study folder opened): write the settings pairing could not write earlier. */
export async function reapplyPairedSettings(
  context: vscode.ExtensionContext,
): Promise<void> {
  const paired = getPairedIdentity(context);
  if (!paired || !hasWorkspace()) return;
  await enforcePairedSettings(paired);
  const locked = pairingState<Record<string, unknown>>(
    context,
    STATE_LOCKED_SETTINGS,
  );
  if (locked) await writeWorkspaceFlags(locked);
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
        await applyConfig(context, cfg);
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
  await bestEffort(async () => {
    if (!hasWorkspace()) return;
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
  });
  await applyConfig(context, result.captureConfig);
  await enforcePairedSettings({
    studyId: result.studyId,
    participantId: result.participantId,
    condition: result.condition,
    ingestEndpoint: result.ingestEndpoint,
  });

  // The redeem payload includes the first assigned task when the protocol
  // declares one. Open the assigned study folder before the participant starts;
  // repository URLs remain informational and are never executed or cloned.
  const initialBlock = readBlock(result.captureConfig);
  if (initialBlock) await openAssignedWorkspace(context, initialBlock);
  else {
    await refreshConfigAtSessionStart(context, false);
    const refreshedBlock = pairingState<SessionBlock>(context, STATE_BLOCK);
    if (refreshedBlock) await openAssignedWorkspace(context, refreshedBlock);
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
  if (!hasWorkspace()) return; // written on activation once a folder is open
  await bestEffort(async () => {
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
  });
}

/** Open the study folder the researcher assigned: a local path, or an uploaded
 *  zip unpacked under the extension's own storage. Never clones a repository.
 *  Pairing has already succeeded, so every problem ends in a clear message with
 *  a way forward rather than a silent no-op. */
async function openAssignedWorkspace(
  context: vscode.ExtensionContext,
  block: SessionBlock,
): Promise<void> {
  await openStudyFolder(block, {
    env: {
      web: vscode.env.uiKind === vscode.UIKind.Web,
      homeDir: os.homedir(),
      currentFolder: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
    },
    isDirectory,
    download: async (target) => {
      const serverUrl = pairingState<string>(context, STATE_SERVER);
      const credential = await context.secrets.get(SECRET_CRED);
      if (!serverUrl || !credential) {
        throw new Error('this computer is not paired with the study server');
      }
      return fetchAndUnpack({
        serverUrl,
        url: target.url,
        credential,
        sha256: target.sha256,
        size: target.size,
        destRoot: path.join(
          context.globalStorageUri.fsPath,
          'study-workspaces',
          pairingState<string>(context, STATE_STUDY_ID) ?? 'study',
        ),
      });
    },
    openFolder: async (folder) => {
      await vscode.commands.executeCommand(
        'vscode.openFolder',
        vscode.Uri.file(folder),
        false,
      );
    },
    offerFallback: (reason, shown) =>
      offerFolderFallback(context, block, reason, shown),
  });
}

function isDirectory(p: string): boolean {
  try {
    return fs.statSync(p).isDirectory();
  } catch {
    return false;
  }
}

/** Tell the participant what happened and let them recover themselves. */
async function offerFolderFallback(
  context: vscode.ExtensionContext,
  block: SessionBlock,
  reason: string,
  shown: string,
): Promise<void> {
  const task = block.title ? ` for “${block.title}”` : '';
  const choice = await vscode.window.showWarningMessage(
    `Study connected, but its folder${task} was not opened. ${reason} Folder: ${shown}`,
    'Open Folder…',
    'Try again',
  );
  if (choice === 'Open Folder…') {
    await vscode.commands.executeCommand('workbench.action.files.openFolder');
  } else if (choice === 'Try again') {
    await openAssignedWorkspace(context, block);
  }
}

/** Forget the study link: credential, paired identity, locked overlay and the
 *  settings pairing wrote. Nothing locked survives, so standalone use is
 *  governed by local settings again. */
async function clearPairing(context: vscode.ExtensionContext): Promise<void> {
  const overlay = pairingState<Record<string, unknown>>(
    context,
    STATE_LOCKED_SETTINGS,
  );
  setActiveLock(undefined);
  await context.secrets.delete(SECRET_CRED);
  for (const key of PAIRING_STATE_KEYS) {
    await persistPairingState(context, key, undefined);
  }
  const conf = vscode.workspace.getConfiguration('tern');
  const target = vscode.ConfigurationTarget.Workspace;
  const keys = new Set([...PAIRED_SETTING_KEYS, ...Object.keys(overlay ?? {})]);
  for (const key of keys) {
    await conf.update(key, undefined, target);
  }
}

export function registerPairing(
  context: vscode.ExtensionContext,
  onChanged?: () => void,
  sessionActive: () => boolean = () => false,
): vscode.Disposable {
  const onPaired = onChanged;
  const connect = vscode.commands.registerCommand(
    'tern.connectToStudy',
    async () => {
      if (getPairedIdentity(context)) {
        void vscode.window.showInformationMessage(
          'This editor is already connected to a study. Use “TERN: Disconnect from Study” first if you need to switch.',
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
    },
  );
  const disconnect = vscode.commands.registerCommand(
    'tern.disconnectStudy',
    async () => {
      const blocked = disconnectBlockedReason(sessionActive());
      if (blocked) {
        void vscode.window.showWarningMessage(blocked);
        return;
      }
      if (!getPairedIdentity(context)) {
        void vscode.window.showInformationMessage(
          'This editor is not connected to a study.',
        );
        return;
      }
      const choice = await vscode.window.showWarningMessage(
        'Disconnect from this study? Capture settings from the study will be removed and you will need a new connection string to rejoin.',
        { modal: true },
        'Disconnect',
      );
      if (choice !== 'Disconnect') return;
      await clearPairing(context);
      onChanged?.();
      void vscode.window.showInformationMessage('Disconnected from the study.');
    },
  );
  return vscode.Disposable.from(connect, disconnect);
}
