import * as vscode from 'vscode';
import { LockedConfig } from '../core/lockedConfig';

/**
 * Where capture reads its `tern.*` configuration from.
 *
 * A paired session resolves its configuration once, at the session boundary,
 * and freezes it (see `buildLockedConfig`). From then on the participant's own
 * VS Code settings are not consulted: they can still be edited  -  VS Code has
 * no read-only setting  -  but editing them no longer changes what is captured
 * (issue #38). Unpaired, nothing is locked and live settings still win, so
 * standalone testing behaves as it always has.
 */

let current: LockedConfig | undefined;

export function setActiveLock(lock: LockedConfig | undefined): void {
  current = lock;
}

export function activeLock(): LockedConfig | undefined {
  return current;
}

/** Read one `tern.`-stripped capture setting under the lock when there is one. */
export function captureSetting<T>(key: string, fallback: T): T {
  if (current?.locked) return current.get(key, fallback);
  return vscode.workspace.getConfiguration('tern').get<T>(key, fallback);
}
