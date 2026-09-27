/**
 * Tampering-visible, not tampering-preventable: `lockedConfig.ts` already
 * makes an edited `tern.*` setting harmless to capture. This module answers
 * the separate research question of whether a participant tried  -  a
 * content-free integrity signal the coordinator records into the same event
 * stream as every other measurement. Portable core: pure comparison, no
 * event recording, no session or VS Code awareness.
 */

import { LockedConfig } from './lockedConfig';

export interface DriftReport {
  /** The `tern.`-stripped setting key. */
  key: string;
  lockedValue: unknown;
  attemptedValue: unknown;
}

/** True when two config values differ. A locked value may be a protocol
 *  array (`stuck.languages`, `behavior.languages`,
 *  `comprehensionProbe.probeTypes`), so `===` is not enough; JSON.stringify
 *  is sufficient here because these values are protocol-domain scalars and
 *  flat arrays, never cyclic or class instances. A value that cannot be
 *  stringified (e.g. a value containing a circular reference) is treated as
 *  changed rather than thrown on. */
function differs(locked: unknown, attempted: unknown): boolean {
  if (locked === attempted) return false;
  try {
    return JSON.stringify(locked) !== JSON.stringify(attempted);
  } catch {
    return true;
  }
}

/** What a participant changed, if anything, relative to the lock. Returns
 *  `[]` when nothing is locked  -  no lock, no drift to detect  -  and
 *  ignores any key in `current` the lock never saw, since an unlocked key
 *  can't have been tampered with. Sorted by key for deterministic event
 *  order. */
export function detectDrift(
  lock: LockedConfig,
  current: Record<string, unknown>,
): DriftReport[] {
  if (!lock.locked) return [];
  const expected: Record<string, unknown> = {};
  for (const key of lock.keys()) expected[key] = lock.lockedValue(key);
  return detectDriftAgainst(expected, current);
}

/**
 * The same comparison against an explicit expected map.
 *
 * Identity and transport are authoritative but deliberately absent from the
 * lock  -  they come from the pairing redeem, because the protocol carries only
 * example values for them  -  so `detectDrift` alone can never notice them being
 * edited. The caller supplies what those keys should be.
 */
export function detectDriftAgainst(
  expected: Record<string, unknown>,
  current: Record<string, unknown>,
): DriftReport[] {
  const out: DriftReport[] = [];
  for (const [key, attemptedValue] of Object.entries(current)) {
    if (!Object.hasOwn(expected, key)) continue;
    const lockedValue = expected[key];
    if (differs(lockedValue, attemptedValue)) {
      out.push({ key, lockedValue, attemptedValue });
    }
  }
  out.sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
  return out;
}
