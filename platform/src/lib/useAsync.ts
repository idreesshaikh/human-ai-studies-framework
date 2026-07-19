import { useCallback, useEffect, useState } from "react";

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

  return { data, loading, error, reload };
}
