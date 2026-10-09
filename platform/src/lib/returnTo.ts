/* Keep the sign-in return path in the URL so it survives an authentication reload. */

const DEFAULT_NEXT = "/home";

/** Longer than any route this app has; a cap keeps a hostile link from
 * stuffing the address bar. */
const MAX_NEXT = 512;

/* Allow same-origin app paths only; reject protocol-relative and backslash redirects. */
export function safeNext(raw: string | null | undefined): string {
  if (!raw) return DEFAULT_NEXT;
  if (raw.length > MAX_NEXT) return DEFAULT_NEXT;
  if (!raw.startsWith("/")) return DEFAULT_NEXT;
  if (raw.startsWith("//") || raw.startsWith("/\\")) return DEFAULT_NEXT;
  return raw;
}

/* Carry the current route through sign-in, excluding /signin to avoid a redirect loop. */
export function signInHref(from: string): string {
  const next = safeNext(from);
  if (next === DEFAULT_NEXT || next.startsWith("/signin")) return "/signin";
  return `/signin?next=${encodeURIComponent(next)}`;
}
