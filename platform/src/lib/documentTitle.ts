/* One document title per route, so a tab, a history entry and a screen
 * reader's "page loaded" announcement all say where the researcher is. Pure:
 * the hook that applies it lives in useDocumentTitle.ts. */
import { STUDY_TAB_LABELS, resolveStudyTab } from "./studyTabs.ts";

export const SITE_NAME = "Phoenix";
export const LANDING_TITLE = "Phoenix: run a defensible developer study";

export interface TitleInput {
  pathname: string;
  search?: string;
  /** The loaded project's name, when known. */
  projectName?: string;
  /** The study's name as displayed (studyNames.ts), when on a study. */
  studyName?: string;
}

function page(name: string): string {
  return `${name} · ${SITE_NAME}`;
}

export function documentTitle({ pathname, search = "", projectName, studyName }: TitleInput): string {
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  if (path === "/") return LANDING_TITLE;
  if (path === "/home") return page("Projects");
  if (path === "/start") return page("Start a study");
  if (path === "/settings") return page("Account settings");
  if (path === "/repertoire") return page("Templates");
  if (path === "/signin") return page("Sign in");
  if (/^\/invitations\/[^/]+$/.test(path)) return page("Project invitation");
  if (/^\/p\/[^/]+$/.test(path)) return page(projectName?.trim() || "Project");
  if (/^\/p\/[^/]+\/members$/.test(path)) return page("Members");
  if (/^\/p\/[^/]+\/settings$/.test(path)) return page("Project settings");
  if (/^\/p\/[^/]+\/studies\/[^/]+$/.test(path)) {
    const tab = STUDY_TAB_LABELS[resolveStudyTab(new URLSearchParams(search).get("tab"))];
    return page(`${studyName?.trim() || "Study"} · ${tab}`);
  }
  return page("Page not found");
}
