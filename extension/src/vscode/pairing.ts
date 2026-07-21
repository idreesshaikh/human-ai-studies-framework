import * as vscode from 'vscode';
import { decodeConnectionString } from '../core/connectionString';
import {
  CaptureConfig,
  overlayFlags,
  shouldApplyCaptureConfig,
} from '../core/captureConfig';
import { preflightSummary } from '../core/preflight';
import { ConsentGate } from '../core/consentGate';

const SECRET_CRED = 'tern.sessionCredential';
const STATE_SERVER = 'tern.serverUrl';
const STATE_VERSION = 'tern.captureConfigVersion';

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

/** Identity/transport keys resolved from the redeem, NOT from the protocol —
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
 * IDE has never paired. Read-only — does not touch the network. */
export async function getStoredCredential(
  context: vscode.ExtensionContext,
): Promise<string | undefined> {
  return context.secrets.get(SECRET_CRED);
}

/** Re-pull the study's capture config at a session boundary and apply it if
 * the version changed AND no session is active (wall #6 — see
 * `shouldApplyCaptureConfig`). `sessionActive` is the caller's own liveness
 * flag (e.g. `Boolean(study)`); the only real call site passes `false`
 * because it runs before the clock arms, but the guard fails closed even if
 * a future call site got that wrong. No-op when unpaired. Returns the
 * credential to use for the session's HttpSink, or undefined when unpaired. */
export async function refreshConfigAtSessionStart(
  context: vscode.ExtensionContext,
  sessionActive: boolean,
): Promise<string | undefined> {
  const cred = await context.secrets.get(SECRET_CRED);
  const server = context.workspaceState.get<string>(STATE_SERVER);
  const studyId = vscode.workspace
    .getConfiguration('tern')
    .get<string>('studyId');
  if (!cred || !server || !studyId) return cred ?? undefined;
  try {
    const res = await fetch(`${server}/studies/${studyId}/capture-config`, {
      headers: { authorization: `Bearer ${cred}` },
    });
    if (res.ok) {
      const cfg = (await res.json()) as CaptureConfig;
      const applied = context.workspaceState.get<string>(STATE_VERSION);
      if (
        shouldApplyCaptureConfig(
          sessionActive,
          applied,
          cfg.captureConfigVersion,
        )
      ) {
        await applyConfig(cfg);
        await context.workspaceState.update(
          STATE_VERSION,
          cfg.captureConfigVersion,
        );
      }
    }
  } catch {
    // Never block a session on a config refresh — last-applied config stands.
  }
  return cred;
}

/** Redeem a connection string, gate on consent, persist identity + the
 * credential, apply the initial capture config, and show the pre-flight
 * summary. Shared by the `connectToStudy` command and the `vscode://…/pair`
 * URI handler — one redeem path, no second mechanism. */
export async function pairFromConnectionString(
  context: vscode.ExtensionContext,
  raw: string,
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

  // Consent gate — show the statement + policy, require explicit acceptance.
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
  await context.workspaceState.update(STATE_SERVER, conn.serverUrl);
  await context.workspaceState.update(
    STATE_VERSION,
    result.captureConfig.captureConfigVersion,
  );
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
    'condition',
    result.condition,
    vscode.ConfigurationTarget.Workspace,
  );
  await conf.update(
    'output.httpEndpoint',
    result.ingestEndpoint,
    vscode.ConfigurationTarget.Workspace,
  );
  await applyConfig(result.captureConfig);

  // Pre-flight summary (before any session starts).
  const items = preflightSummary(overlayFlags(result.captureConfig));
  const on =
    items
      .filter((i) => i.on)
      .map((i) => i.label)
      .join(', ') || 'nothing';
  void vscode.window.showInformationMessage(
    `Connected as ${result.participantId} (${result.condition}). This study will capture: ${on}. Run “TERN: Start session” when you're ready.`,
  );
}

export function registerPairing(
  context: vscode.ExtensionContext,
): vscode.Disposable {
  return vscode.commands.registerCommand('tern.connectToStudy', async () => {
    const raw = await vscode.window.showInputBox({
      title: 'Connect to study',
      prompt: 'Paste the connection string your researcher gave you',
      ignoreFocusOut: true,
    });
    if (!raw) return;
    await pairFromConnectionString(context, raw);
  });
}
