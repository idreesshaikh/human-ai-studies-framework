

const DEFAULT_NEXT = "/home";

const MAX_NEXT = 512;

export function safeNext(raw: string | null | undefined): string {
  if (!raw) return DEFAULT_NEXT;
  if (raw.length > MAX_NEXT) return DEFAULT_NEXT;
  if (!raw.startsWith("/")) return DEFAULT_NEXT;
  if (raw.startsWith("//") || raw.startsWith("/\\")) return DEFAULT_NEXT;
  return raw;
}

export function signInHref(from: string): string {
  const next = safeNext(from);
  if (next === DEFAULT_NEXT || next.startsWith("/signin")) return "/signin";
  return `/signin?next=${encodeURIComponent(next)}`;
}
