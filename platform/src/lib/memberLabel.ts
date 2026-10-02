import type { Member } from "./api.ts";

export function memberLabel(
  m: Member,
  viewer?: { id: string; label: string } | null,
): string {
  if (viewer && m.identitySub === viewer.id) return viewer.label;
  return `Member ${m.identitySub.slice(-6)}`;
}
