import { useSyncExternalStore } from "react";

/* Which panels the researcher has folded away, remembered per device.
 *
 * A per-device ergonomic, not an identity preference: how much chrome you
 * want around the work depends on the screen you are sitting at, so this
 * follows the machine rather than the account. Same external-store shape as
 * `theme.ts`, and for the same reason — the value can change from more than
 * one place, so React has to subscribe to it rather than copy it at mount.
 */

export type PanelId = "nav" | "draft";

const KEY = "phoenix.panels";
const listeners = new Set<() => void>();

/** Cached so `getSnapshot` returns a stable reference; `useSyncExternalStore`
 * re-renders forever if it hands back a fresh object each call. */
let cache: Record<PanelId, boolean> = read();

function read(): Record<PanelId, boolean> {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return { nav: parsed.nav === true, draft: parsed.draft === true };
  } catch {
    // Storage denied: the panels still fold, they just forget across reloads.
    return { nav: false, draft: false };
  }
}

export function isCollapsed(id: PanelId): boolean {
  return cache[id];
}

export function getPanels(): Record<PanelId, boolean> {
  return cache;
}

export function togglePanel(id: PanelId): void {
  cache = { ...cache, [id]: !cache[id] };
  try {
    localStorage.setItem(KEY, JSON.stringify(cache));
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
export function usePanel(id: PanelId): boolean {
  const panels = useSyncExternalStore(subscribePanels, getPanels, getPanels);
  return panels[id];
}
