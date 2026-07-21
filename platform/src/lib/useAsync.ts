import { useCallback, useEffect, useState } from "react";
import { CREDENTIAL_READY_EVENT } from "./auth.tsx";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/* Run an async loader, tracking loading/error and exposing a reload. Keeps
 * the pages free of repeated try/catch/useEffect boilerplate. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // `deps` is the caller's declared dependency list for `load`.
  const run = useCallback(load, deps);

  const reload = useCallback(() => {
    let live = true;
    setLoading(true);
    setError(null);
    run()
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e?.message ?? "Something went wrong."))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [run]);

  useEffect(reload, [reload]);

  // A page can mount and fire its first load before Clerk finishes loading
  // (setTokenProvider hasn't been installed yet), 401, and be left showing
  // that stale error forever — nothing else re-triggers it once a real
  // credential exists. Retry once auth catches up, same signal `session.tsx`
  // uses for its own `/me` call, generalized to every `useAsync` caller.
  useEffect(() => {
    window.addEventListener(CREDENTIAL_READY_EVENT, reload);
    return () => window.removeEventListener(CREDENTIAL_READY_EVENT, reload);
  }, [reload]);

  return { data, loading, error, reload };
}
