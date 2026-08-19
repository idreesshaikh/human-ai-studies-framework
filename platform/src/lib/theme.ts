/* Theme control. The app always starts in light; dark is an explicit choice
 * the researcher makes with the toggle, and it persists. There is no
 * OS-"system" auto-dark — a first load (and any load before a choice) is
 * light, every time, on every machine. A pre-paint inline script in
 * index.html applies the stored choice before first paint so there's no
 * flash. */
export type Theme = "light" | "dark";

const KEY = "platform-theme";

/* Applying a theme is not always the toggle's doing: the signed-in profile
 * carries a saved theme (FR-OPS-7) that lands one round-trip after the shell
 * has already mounted. A toggle holding its own mount-time copy of the theme
 * would then be a step behind the page and spend its first click re-applying
 * what is already on screen — a dead click. So the applied theme is the one
 * store, and every control reads it live. */
const listeners = new Set<() => void>();

export function getTheme(): Theme {
  return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
}

export function subscribeTheme(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => {
    listeners.delete(onChange);
  };
}

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(KEY, theme);
  for (const notify of listeners) notify();
}

/** Toggle light ↔ dark. */
export function nextTheme(t: Theme): Theme {
  return t === "light" ? "dark" : "light";
}
