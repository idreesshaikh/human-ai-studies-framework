/* Steer maps assistant response style to the server's researcher profiles. */

/** 0 answers only; 3 drafts the plan. The numbers are kept from the earlier
 * four-stop dial so a saved choice still reads back (see `readSteer`). */
export type SteerLevel = 0 | 3;

export interface SteerStop {
  level: SteerLevel;
  /** Sent to the middleware; joins `profile` on the turn payload. */
  id: "checks" | "leads";
  label: string;
  /** What changes about the next turn. */
  summary: string;
  /** The register this stop speaks in (elicitation.PROFILES key). */
  profile: "student" | "experienced";
}

/* Two styles that behave differently, not four that read alike: one turns
 * the conversation into plan cards, the other only answers and never changes
 * the draft. The default comes first. */
export const STEER_STOPS: readonly SteerStop[] = [
  {
    level: 3,
    id: "leads",
    label: "Drafts the plan",
    summary: "Turns what you say into plan cards you accept or reject.",
    profile: "student",
  },
  {
    level: 0,
    id: "checks",
    label: "Answers only",
    summary: "Answers questions and flags risks. Never changes the draft.",
    profile: "experienced",
  },
] as const;

/** Where a researcher who has never chosen a style starts. Matches
 * `elicitation.DEFAULT_STEER` on the server. */
export const DEFAULT_STEER: SteerLevel = 3;

export function steerStop(level: SteerLevel): SteerStop {
  return (
    STEER_STOPS.find((stop) => stop.level === level) ??
    STEER_STOPS.find((stop) => stop.level === DEFAULT_STEER)!
  );
}

/** Per-study, because the amount of help you want belongs to the study you
 * are in the middle of. */
function key(studyId: string): string {
  return `phoenix.steer.${studyId}`;
}

export function readSteer(
  studyId: string,
  fallback: SteerLevel = DEFAULT_STEER,
): SteerLevel {
  try {
    /* Read the string first and test it for absence explicitly. `Number(null)`
     * is 0, and 0 is a valid level  -  so coercing first silently turned "this
     * researcher has never touched the dial" into "this researcher asked for
     * the quietest setting", which is the one stop that stops proposals
     * arriving at all. */
    const raw = localStorage.getItem(key(studyId));
    if (raw == null) return fallback;
    const level = Number(raw);
    if (!Number.isInteger(level) || level < 0 || level > 3) return fallback;
    // The earlier dial had four stops. Only its quietest one withheld
    // proposals; the other three all proposed, so they map to drafting.
    return level === 0 ? 0 : 3;
  } catch {
    // A browser with storage denied still gets a working dial for the
    // session; only the memory of it across reloads is lost.
    return fallback;
  }
}

export function writeSteer(studyId: string, level: SteerLevel): void {
  try {
    localStorage.setItem(key(studyId), String(level));
  } catch {
    /* see readSteer */
  }
}
