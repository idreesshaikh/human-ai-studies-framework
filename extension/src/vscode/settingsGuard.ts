import * as vscode from 'vscode';
import { LockedConfig } from '../core/lockedConfig';
import { detectDrift, detectDriftAgainst } from '../core/settingsDrift';

/**
 * Makes a settings override visible (issue #38).
 *
 * The lock already makes participant edits harmless  -  capture stopped reading
 * settings at the session boundary. What a researcher still needs is the fact
 * that an edit was attempted, so it lands in the study's own event stream
 * beside every other measurement rather than in a log nobody exports.
 *
 * The payload carries the setting key and its before/after values only: these
 * are protocol-domain scalars, never source, conversation, or clipboard text
 * (FR-ETH-2).
 */

export const OVERRIDE_EVENT = 'settings_override_attempt';

export interface SettingsGuardDeps {
  /** The frozen config in force, or undefined when no paired session runs. */
  lock: () => LockedConfig | undefined;
  /**
   * What the settings-backed identity keys should be, from the pairing redeem,
   * or undefined when unpaired. `condition` is deliberately excluded by the
   * caller: it is never written into settings at all, so comparing it would
   * report drift forever  -  and writing it back would expose the arm the
   * participant is blind to.
   */
  identity?: () => Record<string, unknown> | undefined;
  /** Restores the redeem-issued identity values after an edit. */
  reassertIdentity?: () => Promise<void>;
  record: (type: string, payload: Record<string, unknown>) => void;
  /** Lets a surface (the sidebar) show that an override was seen. */
  onDrift?: () => void;
}

export function registerSettingsGuard(
  deps: SettingsGuardDeps,
): vscode.Disposable {
  // Set while the write-back below runs, so the change events it raises are
  // not themselves recorded as participant edits. After the write-back the
  // stored values match the lock again, so any event that still slips past
  // this flag simply finds no drift.
  let reasserting = false;

  return vscode.workspace.onDidChangeConfiguration(async (event) => {
    if (reasserting || !event.affectsConfiguration('tern')) return;
    const lock = deps.lock();
    if (!lock?.locked) return;

    const conf = vscode.workspace.getConfiguration('tern');
    const current: Record<string, unknown> = {};
    for (const key of lock.keys()) {
      const value = conf.get(key);
      if (value !== undefined) current[key] = value;
    }

    // Identity is checked separately because the lock holds no entry for it.
    const expectedIdentity = deps.identity?.();
    const identityCurrent: Record<string, unknown> = {};
    if (expectedIdentity) {
      for (const key of Object.keys(expectedIdentity)) {
        identityCurrent[key] = conf.get(key);
      }
    }
    const identityDrift = expectedIdentity
      ? detectDriftAgainst(expectedIdentity, identityCurrent)
      : [];

    const lockDrift = detectDrift(lock, current);
    const drifted = [...lockDrift, ...identityDrift];
    if (drifted.length === 0) return;

    for (const report of drifted) {
      deps.record(OVERRIDE_EVENT, {
        key: report.key,
        lockedValue: report.lockedValue ?? null,
        attemptedValue: report.attemptedValue ?? null,
      });
    }
    deps.onDrift?.();

    // Put the locked values back so the Settings screen stops showing an edit
    // that has no effect. Cosmetic only: capture never read them anyway.
    reasserting = true;
    try {
      for (const report of lockDrift) {
        await conf.update(
          report.key,
          report.lockedValue,
          vscode.ConfigurationTarget.Workspace,
        );
      }
      // Identity goes back through the one function that already knows how to
      // restore it, rather than a second, divergent account of the same rule.
      if (identityDrift.length > 0) await deps.reassertIdentity?.();
    } catch {
      // A failed write-back leaves the screen misleading but the data correct,
      // which is the right way round to fail.
    } finally {
      reasserting = false;
    }
  });
}
