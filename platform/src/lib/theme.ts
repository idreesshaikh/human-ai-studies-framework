/* Theme control. The default follows the OS setting; the toggle stamps
 * data-theme on <html> to override it, and the choice persists. */
export type Theme = "light" | "dark" | "system";

const KEY = "platform-theme";

export function getTheme(): Theme {
  return (localStorage.getItem(KEY) as Theme | null) ?? "system";
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
