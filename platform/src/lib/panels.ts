import { useSyncExternalStore } from "react";

/* Which panels the researcher has folded away, remembered per device.
 *
 * A per-device ergonomic, not an identity preference: how much chrome you
 * want around the work depends on the screen you are sitting at, so this
 * follows the machine rather than the account. The navigation fold is global,
 * while the protocol draft fold belongs to a study. A new study therefore
 * opens its draft for orientation, and a return to that study remembers the
 * last choice made there.
 */

export type PanelId = "nav" | "draft";
export type RailId = "papers" | "draft";

const KEY = "phoenix.panels";
const listeners = new Set<() => void>();

function railKey(studyId: string): string {
  return `phoenix.study.${studyId}.rail`;
}

export function readRail(studyId: string, fallback: RailId = "draft"): RailId {
  try {
    const value = localStorage.getItem(railKey(studyId));
    return value === "papers" || value === "draft" ? value : fallback;
  } catch {
    return fallback;
  }
}

export function writeRail(studyId: string, rail: RailId): void {
  try {
    localStorage.setItem(railKey(studyId), rail);
  } catch {
    /* Storage denied: the rail still works for this mount. */
  }
}

/** Cached so `getSnapshot` returns a stable primitive for each panel; the
 * external store still updates every mounted conversation when another
 * control changes the preference. */
const cache: Record<string, boolean> = {};

function read(): Record<PanelId, boolean> {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return { nav: parsed.nav === true, draft: false };
  } catch {
    // Storage denied: the panels still fold, they just forget across reloads.
    return { nav: false, draft: false };
  }
}

cache.nav = read().nav;

function storageKey(id: PanelId, studyId?: string): string {
  return id === "draft" && studyId
    ? `phoenix.study.${studyId}.draft-folded`
    : KEY;
}

function readValue(id: PanelId, studyId?: string): boolean {
  const key = storageKey(id, studyId);
  if (key in cache) return cache[key];
  if (key === KEY) return cache.nav;
  try {
    cache[key] = localStorage.getItem(key) === "1";
  } catch {
    cache[key] = false;
  }
  return cache[key];
}

export function isCollapsed(id: PanelId, studyId?: string): boolean {
  return readValue(id, studyId);
}

export function getPanels(): Record<PanelId, boolean> {
  return { nav: readValue("nav"), draft: false };
}

export function togglePanel(id: PanelId, studyId?: string): void {
  const key = storageKey(id, studyId);
  const next = !readValue(id, studyId);
  cache[key] = next;
  try {
    if (key === KEY) {
      localStorage.setItem(KEY, JSON.stringify({ nav: next }));
    } else {
      localStorage.setItem(key, next ? "1" : "0");
    }
  } catch {
    /* see read() */
  }
  listeners.forEach((fn) => fn());
}

export function subscribePanels(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** The collapsed state of one panel, live. */
export function usePanel(id: PanelId, studyId?: string): boolean {
  return useSyncExternalStore(
    subscribePanels,
    () => readValue(id, studyId),
    () => false,
  );
}
