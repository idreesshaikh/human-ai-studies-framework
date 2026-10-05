import { humanSlug } from "./slug.ts";
import { clampName } from "./uiText.ts";

/* A study row stores only its slug, so the name a researcher typed would be
 * lost and the heading rebuilt from the slug ("Zz audit temp" for
 * "ZZ Audit Temp"). The name is remembered on this device as entered, and the
 * slug-as-words is the fallback everywhere else. */
interface NameStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const key = (id: string) => `phoenix.studyName.${id}`;

export function rememberStudyName(store: NameStore, id: string, name: string): void {
  const clean = clampName(name.trim());
  if (!clean) return;
  try {
    store.setItem(key(id), clean);
  } catch {
    /* storage can be unavailable; the slug fallback still reads fine */
  }
}

export function studyDisplayName(store: NameStore, id: string): string {
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
