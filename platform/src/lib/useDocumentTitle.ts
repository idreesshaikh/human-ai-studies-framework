import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { documentTitle, type TitleInput } from "./documentTitle.ts";

/** Sets document.title for the current route. Pass the names the route knows
 * (project, study) once they have loaded. */
export function useRouteTitle(names: Pick<TitleInput, "projectName" | "studyName"> = {}) {
  const { pathname, search } = useLocation();
  const { projectName, studyName } = names;
  useEffect(() => {
    document.title = documentTitle({ pathname, search, projectName, studyName });
  }, [pathname, search, projectName, studyName]);
}
