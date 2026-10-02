

export type Theme = "light" | "dark";

const KEY = "platform-theme";

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

export function nextTheme(t: Theme): Theme {
  return t === "light" ? "dark" : "light";
}
