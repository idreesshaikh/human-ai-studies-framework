import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { documentTitle, type TitleInput } from "./documentTitle.ts";

/** Sets the document title for the current route. */
export function useRouteTitle(names: Pick<TitleInput, "studyName"> = {}) {
  const { pathname, search } = useLocation();
  const { studyName } = names;
  useEffect(() => {
    document.title = documentTitle({ pathname, search, studyName });
  }, [pathname, search, studyName]);
}
