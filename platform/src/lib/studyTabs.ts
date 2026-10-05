/* The study workspace's tab ids, and the names people actually use for them.
 * The ids are stable (deep links, the tour); the aliases let `?tab=run` work
 * because the tab is labelled Run. */
export type StudyTab = "conversation" | "library" | "data" | "planning" | "enrollment";

export const STUDY_TAB_IDS: StudyTab[] = [
  "conversation",
  "library",
  "planning",
  "enrollment",
  "data",
];

const ALIASES: Record<string, StudyTab> = {
  setup: "conversation",
  evidence: "library",
  plan: "planning",
  run: "enrollment",
};

export function resolveStudyTab(param: string | null): StudyTab {
  if (!param) return "conversation";
  if ((STUDY_TAB_IDS as string[]).includes(param)) return param as StudyTab;
  return ALIASES[param] ?? "conversation";
}
