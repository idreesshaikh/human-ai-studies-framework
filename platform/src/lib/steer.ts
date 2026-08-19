/* Steer — how much the design assistant drives the conversation.
 *
 * One control, two real levers, both of which already exist in the
 * middleware and neither of which is cosmetic:
 *
 *   REGISTER   which researcher profile the assistant speaks to
 *              (elicitation.PROFILES): how much is explained, which
 *              trade-offs are worth surfacing, whether a term gets defined.
 *   INITIATIVE how much it proposes unprompted (design_assistant's stance):
 *              a turn that leads with the next move, versus one that answers
 *              what was asked and flags only what is methodologically wrong.
 *
 * The METHOD never changes with this control. The same designs, the same
 * statistics, the same honesty about what is grounded and what is not — a
 * researcher who turns steer down gets a quieter colleague, never a less
 * rigorous one, and one who turns it up is not given easier science. That
 * invariant is the reason this is a comfort setting and not a quality
 * setting, and it is enforced on the server: the stance machinery filters
 * what may be proposed, so a model that ignores the instruction still cannot
 * flood a low-steer conversation with proposals.
 *
 * The profile in Settings (FR-OPS-7) is the account-wide default this starts
 * from; this dial is the per-study override, because how much help you want
 * is a property of the study you are in the middle of, not of who you are. */

export type SteerLevel = 0 | 1 | 2 | 3;

export interface SteerStop {
  level: SteerLevel;
  /** Sent to the middleware; joins `profile` on the turn payload. */
  id: "checks" | "assists" | "guides" | "leads";
  label: string;
  /** The live readout under the dial: what changes about the next turn. */
  summary: string;
  /** The register this stop speaks in (elicitation.PROFILES key). */
  profile: "student" | "new-researcher" | "experienced";
}

/** Low to high, so the array index IS the level and the slider's own
 * left-to-right order is the order of increasing help. */
export const STEER_STOPS: readonly SteerStop[] = [
  {
    level: 0,
    id: "checks",
    label: "Checks",
    summary: "Answers what you ask. Flags only risks and unsourced claims.",
    profile: "experienced",
  },
  {
    level: 1,
    id: "assists",
    label: "Assists",
    summary: "Proposes where the protocol is structurally missing something.",
    profile: "experienced",
  },
  {
    level: 2,
    id: "guides",
    label: "Guides",
    summary: "Proposes freely and explains why, following your order.",
    profile: "new-researcher",
  },
  {
    level: 3,
    id: "leads",
    label: "Leads",
    summary: "Asks one question at a time and names the next move itself.",
    profile: "student",
  },
] as const;

/** Where a researcher who has never touched the dial starts: proposing and
 * explaining, but not steering. The same default the middleware applies when
 * no profile is declared. */
export const DEFAULT_STEER: SteerLevel = 2;

export function steerStop(level: SteerLevel): SteerStop {
  return STEER_STOPS[level] ?? STEER_STOPS[DEFAULT_STEER];
}

/** Per-study, because the amount of help you want belongs to the study you
 * are in the middle of. */
function key(studyId: string): string {
  return `phoenix.steer.${studyId}`;
}

export function readSteer(studyId: string): SteerLevel {
  try {
    /* Read the string first and test it for absence explicitly. `Number(null)`
     * is 0, and 0 is a valid level — so coercing first silently turned "this
     * researcher has never touched the dial" into "this researcher asked for
     * the quietest setting", which is the one stop that stops proposals
     * arriving at all. */
    const raw = localStorage.getItem(key(studyId));
    if (raw == null) return DEFAULT_STEER;
    const level = Number(raw);
    return isSteerLevel(level) ? level : DEFAULT_STEER;
  } catch {
    // A browser with storage denied still gets a working dial for the
    // session; only the memory of it across reloads is lost.
    return DEFAULT_STEER;
  }
}

export function writeSteer(studyId: string, level: SteerLevel): void {
  try {
    localStorage.setItem(key(studyId), String(level));
  } catch {
    /* see readSteer */
  }
}

function isSteerLevel(n: number): n is SteerLevel {
  return Number.isInteger(n) && n >= 0 && n <= 3;
}
