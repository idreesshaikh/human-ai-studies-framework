import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createApi, type Api, type Me } from "./api.ts";

/* Provides the API client and the signed-in identity to the tree. In
 * none/token auth modes `me.mode` tells the shell to hide project UI
 * (single-facilitator continuity); in clerk mode the full shell shows. */

const ApiContext = createContext<Api | null>(null);

export function ApiProvider({
  api,
  children,
}: {
  api?: Api;
  children: ReactNode;
}) {
  // One client for the app's lifetime (or an injected one, for tests).
  const value = useMemo(() => api ?? createApi(), [api]);
  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>;
}

export function useApi(): Api {
  const api = useContext(ApiContext);
  if (!api) throw new Error("useApi must be used inside <ApiProvider>");
  return api;
}

interface SessionState {
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setMe(await api.me());
    } catch {
      // Not signed in (401) — the auth layer's `onUnauthorized` listener
      // shows the sign-in surface; this just avoids an unhandled rejection.
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(() => ({ me, loading, refresh }), [me, loading, refresh]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
