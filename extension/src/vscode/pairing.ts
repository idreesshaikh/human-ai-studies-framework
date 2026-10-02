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

export const STATE_LEGS = 'tern.legs';

export const STATE_PENDING = 'tern.pendingConfigVersion';

export const STATE_BLOCK = 'tern.sessionBlock';

export const STATE_MANIFEST = 'tern.sessionManifest';

export interface PairedIdentity {
  studyId: string;
  participantId: string;
  condition: string;
  ingestEndpoint: string;
}

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

const IDENTITY_KEYS = new Set([
  'participantId',
  'condition',
  'output.httpEndpoint',
]);

async function applyConfig(cfg: CaptureConfig): Promise<void> {
  const flags = overlayFlags(cfg);
  const conf = vscode.workspace.getConfiguration('tern');
  for (const [key, value] of Object.entries(flags)) {
    if (IDENTITY_KEYS.has(key)) continue;
    await conf.update(key, value, vscode.ConfigurationTarget.Workspace);
  }
}

export async function getStoredCredential(
  context: vscode.ExtensionContext,
): Promise<string | undefined> {
  return context.secrets.get(SECRET_CRED);
}

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
    const url = new URL(`${server}/studies/${studyId}/capture-config`);
    if (sessionId) url.searchParams.set('sessionId', sessionId);
    const res = await fetch(url, {
      headers: { authorization: `Bearer ${cred}` },
    });
    if (res.ok) {
      const cfg = (await res.json()) as CaptureConfig;

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

  const gate = new ConsentGate(result.consentStatement, result.contentPolicy);
  const choice = await vscode.window.showInformationMessage(
    result.consentStatement,
    { modal: true },
    'I consent',
  );
  if (choice !== 'I consent') return;
  gate.acknowledge();

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

  const initialBlock = readBlock(result.captureConfig);
  if (initialBlock) await openAssignedWorkspace(initialBlock);
  else {
    await refreshConfigAtSessionStart(context, false);
    const refreshedBlock = pairingState<SessionBlock>(context, STATE_BLOCK);
    if (refreshedBlock) await openAssignedWorkspace(refreshedBlock);
  }
  onPaired?.();

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

  await conf.update('condition', undefined, target);
  if (identity.ingestEndpoint) {
    await conf.update('output.httpEndpoint', identity.ingestEndpoint, target);
  }
}

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

    onPaired?.();
  });
}
