

export type SteerLevel = 0 | 1 | 2 | 3;

export interface SteerStop {
  level: SteerLevel;

  id: "checks" | "assists" | "guides" | "leads";
  label: string;

  summary: string;

  profile: "student" | "new-researcher" | "experienced";
}

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
    summary: "Keeps one useful next step visible. You can redirect or defer.",
    profile: "student",
  },
] as const;

export const DEFAULT_STEER: SteerLevel = 3;

export function defaultSteerFor(profile?: string | null): SteerLevel {
  return profile === "experienced" ? 2 : DEFAULT_STEER;
}

export function steerStop(level: SteerLevel): SteerStop {
  return STEER_STOPS[level] ?? STEER_STOPS[DEFAULT_STEER];
}

function key(studyId: string): string {
  return `phoenix.steer.${studyId}`;
}

export function readSteer(
  studyId: string,
  fallback: SteerLevel = DEFAULT_STEER,
): SteerLevel {
  try {

    const raw = localStorage.getItem(key(studyId));
    if (raw == null) return fallback;
    const level = Number(raw);
    return isSteerLevel(level) ? level : fallback;
  } catch {

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

function isSteerLevel(n: number): n is SteerLevel {
  return Number.isInteger(n) && n >= 0 && n <= 3;
}
