/* Theme control. The app always starts in light; dark is an explicit choice
 * the researcher makes with the toggle, and it persists. There is no
 * OS-"system" auto-dark — a first load (and any load before a choice) is
 * light, every time, on every machine. A pre-paint inline script in
 * index.html applies the stored choice before first paint so there's no
 * flash. */
export type Theme = "light" | "dark";

const KEY = "platform-theme";

export function getTheme(): Theme {
  return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
}

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(KEY, theme);
}

/** Toggle light ↔ dark. */
export function nextTheme(t: Theme): Theme {
  return t === "light" ? "dark" : "light";
}
