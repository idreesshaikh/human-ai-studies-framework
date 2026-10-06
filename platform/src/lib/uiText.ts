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
  { value: "participant", label: "Per participant" },
  { value: "session", label: "Per session" },
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
  "workspace-snapshot": "Workspace snapshots",
  "participant-git": "Git history",
  "task-harness": "Task outcomes",
  "agent-derived": "Derived AI measures",
};

const STATE_LABELS: Record<string, string> = {
  enabled: "Configured",
  disabled: "Off",
  "external-required": "Separate runner needed",
  unsupported: "Not supported",
  unavailable: "Not configured",
};

/** A producer's configuration state as words. */
export function producerStateLabel(state: string): string {
  return STATE_LABELS[state] ?? captureTokenLabel(state);
}

/** A raw event type (agent.prompt_sent) as words. */
export function eventTypeLabel(type: string): string {
  return captureTokenLabel(type.replace(/\./g, " "));
}

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

/** First letter upper-cased; the rest untouched. */
export function sentenceCase(text: string): string {
  const t = text.trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : "";
}

/** A server message made fit to print: capitalised and ended with a full stop
 * (the API's `detail` strings are often lowercase fragments). */
export function displayServerMessage(text: string): string {
  const t = sentenceCase(text);
  if (!t) return "";
  return /[.!?…]$/.test(t) ? t : `${t}.`;
}

/** An invitation that is gone (404) or expired/revoked (410) will not work on a
 * second try, so the page stops offering to accept it. */
export function isFatalInviteError(e: unknown): boolean {
  const status = (e as { status?: unknown } | null | undefined)?.status;
  return status === 404 || status === 410;
}

/** The registry's generated match reason, in plain words. */
export function plainMatchReason(text: string): string {
  return text.replace(/^Describes itself with:/, "Matches:");
}

/** After a researcher decides a card, should the assistant be asked for its
 * next turn? Only when nothing else in that reply is still waiting on them;
 * deciding one of several pending cards just records the decision. `cards` is
 * the latest assistant turn's moves as they were BEFORE this decision. */
export function shouldFollowUpAfterDecision(
  cards: { moveId: string; status: string }[],
  decidedId: string,
  status: string = "accepted",
): boolean {
  if (status === "proposed") return false;
  if (!cards.some((c) => c.moveId === decidedId)) return false;
  return !cards.some((c) => c.moveId !== decidedId && c.status === "proposed");
}

/** The word a decided card wears: it matches the button that decided it. */
export function moveStateLabel(status: string, kind: string): string {
  if (status === "rejected") return "Rejected";
  if (status !== "accepted") return "";
  if (kind === "merge-templates") return "Merged";
  return kind === "caution" ? "Noted" : "Accepted";
}

const MOVE_NOUN: Record<string, string> = {
  "add-rq": "research question",
  "choose-template": "design",
  "set-parameter": "setting",
  "set-field": "setting",
  "declare-task": "task",
  "add-instrument": "instrument",
  "reconfigure-instrument": "instrument setting",
  "add-measure": "measure",
  "merge-templates": "design",
  "prescribe-statistics": "analysis plan",
};

/** The researcher's own turn when they reject a card. It names the kind of
 * card, never its text, so it cannot be read back as a new study idea. */
export function rejectedMoveText(kind: string): string {
  return `I rejected the proposed ${MOVE_NOUN[kind] ?? "choice"}.`;
}

/** A proposal as the review prints it: no "Declare the task:" template prefix
 * and no doubled full stop. */
export function cleanProposalText(text: string): string {
  const t = text
    .replace(/^\s*declare the task\s*:\s*/i, "")
    .replace(/(?<!\.)\.\.(?!\.)/g, ".")
    .trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/** Which of the dialog's outcome options the researcher already accepted as
 * measure cards in chat (by the patch value, else the proposal text). */
export function measureOptionsFromMoves(
  moves: {
    status: string;
    kind: string;
    proposal: string;
    patch?: unknown;
  }[],
  options: string[],
): string[] {
  const texts = moves
    .filter((m) => m.status === "accepted" && m.kind === "add-measure")
    .map((m) => {
      const patch = m.patch as { section?: string; value?: unknown } | undefined;
      const value = patch?.section === "measures" && typeof patch.value === "string" ? patch.value : "";
      return `${value} ${m.proposal}`.toLowerCase();
    });
  return options.filter((o) => texts.some((t) => t.includes(o.toLowerCase())));
}

const EYEBROW_BY_SECTION: Record<string, string> = {
  researchQuestions: "Research question",
  design: "Design",
  participants: "Participants",
  conditions: "Conditions",
  measures: "Measure",
  instruments: "Instrument",
  statisticalPlan: "Analysis",
  ethics: "Setting",
};

const EYEBROW_BY_KIND: Record<string, string> = {
  "add-rq": "Research question",
  "choose-template": "Design",
  "merge-templates": "Design",
  "set-parameter": "Setting",
  "set-field": "Setting",
  "declare-task": "Task",
  "add-instrument": "Instrument",
  "reconfigure-instrument": "Instrument",
  "add-measure": "Measure",
  "prescribe-statistics": "Analysis",
  caution: "Caution",
};

/** The card's eyebrow: a human noun matching the draft rail's sections. A
 *  patch that names its section wins over the move kind. */
export function moveEyebrow(kind: string, patch?: unknown): string {
  const section = (patch as { section?: unknown } | undefined)?.section;
  if (kind !== "caution" && typeof section === "string" && EYEBROW_BY_SECTION[section]) {
    return EYEBROW_BY_SECTION[section];
  }
  return EYEBROW_BY_KIND[kind] ?? "Setting";
}

/** Composer prefill for the rail's "Next" button. Drafted for the researcher
 *  to edit; never sent. */
export function nextStepPrompt(sectionLabel: string): string {
  return `Propose the ${sectionLabel.toLowerCase()} for this study.`;
}
