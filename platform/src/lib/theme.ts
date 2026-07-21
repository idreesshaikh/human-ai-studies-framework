/* Theme control. Light is the default for a first-time visitor; the toggle
 * stamps data-theme on <html> to override it (light/dark/system), and the
 * choice persists. "system" remains a selectable option (follows the OS
 * setting) — it just isn't what a brand-new visitor sees before choosing. */
export type Theme = "light" | "dark" | "system";

const KEY = "platform-theme";

export function getTheme(): Theme {
  return (localStorage.getItem(KEY) as Theme | null) ?? "light";
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
    localStorage.removeItem(KEY);
  } else {
    root.setAttribute("data-theme", theme);
    localStorage.setItem(KEY, theme);
  }
}

/** Cycle system → light → dark → system. */
export function nextTheme(t: Theme): Theme {
  return t === "system" ? "light" : t === "light" ? "dark" : "system";
}
