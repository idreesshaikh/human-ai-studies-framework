/* Small pure helpers for wording and behaviour that several screens share.
 * Kept free of React so scripts/verify-ui-fixes.mjs can exercise them. */
import type { ProjectSummary } from "./api.ts";

/** Longest project or study name a researcher can enter. */
export const NAME_MAX_LENGTH = 80;

export function clampName(name: string): string {
  return name.slice(0, NAME_MAX_LENGTH);
}

/** What an error should say to a person. A server sentence is kept; a
 * transport string (`GET https://… HTTP 404`) or a bare `Error:` prefix is
 * never shown. */
export function plainErrorMessage(e: unknown, fallback: string): string {
  const message = (e as { message?: unknown } | null | undefined)?.message;
  const text =
    typeof message === "string" ? message : typeof e === "string" ? e : "";
  const clean = text.replace(/^\s*(?:[A-Za-z]*Error):\s*/, "").trim();
  if (!clean) return fallback;
  if (/\bhttps?:\/\//i.test(clean) || /\bHTTP \d{3}\b/.test(clean)) return fallback;
  return clean;
}

/** A study with no applied protocol answers its protocol-dependent reads with
 * a 404 or a "no protocol" sentence. */
export function isMissingProtocolError(e: unknown): boolean {
  if (e && typeof e === "object") {
    const { status, message } = e as { status?: unknown; message?: unknown };
    if (status === 404) return true;
    if (typeof message === "string" && /no protocol/i.test(message)) return true;
  }
  return false;
}

export const APPLY_PROTOCOL_FIRST = "Apply the protocol first, in Setup.";

export function describeMintError(e: unknown): string {
  if (isMissingProtocolError(e)) return APPLY_PROTOCOL_FIRST;
  return plainErrorMessage(e, "Could not create links. Check your connection and try again.");
}

export const MINT_COUNT_HINT = "Enter a whole number from 1 to 100.";

/** null when the text is a valid link count, otherwise the hint to show. */
export function mintCountProblem(text: string): string | null {
  const t = text.trim();
  if (!/^\d+$/.test(t)) return MINT_COUNT_HINT;
  const n = Number(t);
  return n >= 1 && n <= 100 ? null : MINT_COUNT_HINT;
}

export const GRAIN_OPTIONS = [
  { value: "participant", label: "One link per participant, reusable" },
  { value: "session", label: "One link per session, single use" },
] as const;

const TOKEN_LABELS: Record<string, string> = {
  stuck: "Stuck prompts",
  fatigue: "Fatigue probes",
  ideHealth: "IDE health",
  session: "Session",
  output: "Output",
  metrics: "Code metrics",
  tern: "TERN",
  "agent-capture": "Agent capture",
};

/** A capture instrument or producer id as words. */
export function captureTokenLabel(token: string): string {
  const known = TOKEN_LABELS[token];
  if (known) return known;
  const words = token
    .replace(/[-_]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim()
    .toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** The roster heading counts links, not people: a link nobody has opened is
 * not an enrolment. */
export function enrollmentHeading(
  created: number,
  redeemed: number,
): { title: string; detail: string } {
  if (created === 0) return { title: "No links yet", detail: "" };
  return {
    title: `${created} ${created === 1 ? "link" : "links"} created`,
    detail: `${redeemed} redeemed`,
  };
}

export function isMacPlatform(nav: { platform?: string } | undefined): boolean {
  return /mac|iphone|ipad|ipod/i.test(nav?.platform ?? "");
}

export function shortcutLabel(mac: boolean): string {
  return mac ? "⌘K" : "Ctrl K";
}

/** Where the palette's "New project" row goes: the list, composer open. */
export const NEW_PROJECT_PATH = "/home?new=1";

/** Every project the viewer can open, in the order /home lists them. */
export function paletteProjects(list: ProjectSummary[]): ProjectSummary[] {
  const seen = new Set<string>();
  return list.filter((p) => !seen.has(p.slug) && !!seen.add(p.slug));
}

/** After deciding a move by keyboard, where focus should go: the next card
 * still waiting on a decision (later ones first, then earlier), otherwise the
 * decided card's own Undo. */
export function nextFocusAfterDecision(
  moves: { moveId: string; status: string }[],
  decidedId: string,
):
  | { kind: "move"; moveId: string }
  | { kind: "undo"; moveId: string } {
  const at = moves.findIndex((m) => m.moveId === decidedId);
  const order = [...moves.slice(at + 1), ...moves.slice(0, Math.max(at, 0))];
  const next = order.find(
    (m) => m.moveId !== decidedId && m.status === "proposed",
  );
  return next
    ? { kind: "move", moveId: next.moveId }
    : { kind: "undo", moveId: decidedId };
}
