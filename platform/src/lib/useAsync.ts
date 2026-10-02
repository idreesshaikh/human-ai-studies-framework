import { useCallback, useEffect, useRef, useState } from "react";
import { CREDENTIAL_READY_EVENT } from "./auth.tsx";

interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);

  const run = useCallback(load, deps);

  const reload = useCallback(() => {
    const id = ++request.current;
    setLoading(true);
    setData(null);
    setError(null);
    run()
      .then((d) => id === request.current && setData(d))
      .catch((e) => id === request.current && setError(e?.message ?? "Could not load this information. Try again."))
      .finally(() => id === request.current && setLoading(false));
  }, [run]);

  useEffect(() => {
    reload();
    return () => { request.current += 1; };
  }, [reload]);

  useEffect(() => {
    window.addEventListener(CREDENTIAL_READY_EVENT, reload);
    return () => window.removeEventListener(CREDENTIAL_READY_EVENT, reload);
  }, [reload]);

  return { data, loading, error, reload };
}
