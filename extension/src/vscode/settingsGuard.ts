import * as vscode from 'vscode';
import { LockedConfig } from '../core/lockedConfig';
import { detectDrift } from '../core/settingsDrift';

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

    const drifted = detectDrift(lock, current);
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
      for (const report of drifted) {
        await conf.update(
          report.key,
          report.lockedValue,
          vscode.ConfigurationTarget.Workspace,
        );
      }
    } catch {
      // A failed write-back leaves the screen misleading but the data correct,
      // which is the right way round to fail.
    } finally {
      reasserting = false;
    }
  });
}
