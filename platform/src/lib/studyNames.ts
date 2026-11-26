import { humanSlug } from "./slug.ts";
import { clampName } from "./uiText.ts";

/* The server stores the name a researcher typed; older studies have none, so
 * the name remembered on this device as entered comes next, and the
 * slug-as-words ("Zz audit temp" for "ZZ Audit Temp") is the last resort. */
interface NameStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const key = (id: string) => `phoenix.studyName.${id}`;

/* Names arrive after the page first renders (with the study summary), so
 * whatever shows a name can subscribe and re-read it. */
const listeners = new Set<() => void>();
let version = 0;

export function subscribeStudyNames(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const studyNamesVersion = (): number => version;

export function rememberStudyName(store: NameStore, id: string, name: string): void {
  const clean = clampName(name.trim());
  if (!clean) return;
  try {
    if (store.getItem(key(id)) === clean) return;
    store.setItem(key(id), clean);
  } catch {
    /* storage can be unavailable; the slug fallback still reads fine */
    return;
  }
  version += 1;
  for (const listener of listeners) listener();
}

export function studyDisplayName(store: NameStore, id: string, serverName?: string): string {
  if (serverName?.trim()) return serverName.trim();
  try {
    const saved = store.getItem(key(id));
    if (saved) return saved;
  } catch {
    /* fall through */
  }
  return humanSlug(id);
}

export function browserNameStore(): NameStore {
  try {
    return window.localStorage;
  } catch {
    return { getItem: () => null, setItem: () => undefined };
  }
}
