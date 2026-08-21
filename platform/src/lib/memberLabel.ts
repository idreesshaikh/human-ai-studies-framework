import type { Member } from "./api.ts";

/* A raw identity_sub (a Clerk user id, e.g. "user_3GdJzJX...") is never a
 * name anyone recognizes — resolve the best available label instead:
 * the signed-in viewer's own real Clerk profile name, falling back to a
 * short, de-fanged id rather than the full raw string. */
export function memberLabel(
  m: Member,
  viewer?: { id: string; label: string } | null,
): string {
  if (viewer && m.identitySub === viewer.id) return viewer.label;
  return `Member ${m.identitySub.slice(-6)}`;
}
