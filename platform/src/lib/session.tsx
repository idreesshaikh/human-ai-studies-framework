import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createApi, type Api, type Me, type Preferences } from "./api.ts";
import { applyTheme } from "./theme";
import { CREDENTIAL_READY_EVENT } from "./auth.tsx";

const ApiContext = createContext<Api | null>(null);

export function ApiProvider({
  api,
  children,
}: {
  api?: Api;
  children: ReactNode;
}) {

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

  updatePreferences: (prefs: Partial<Preferences>) => Promise<void>;

  setThemePreference: (theme: Preferences["theme"]) => Promise<void>;
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

      setMe(null);
    } finally {
      setLoading(false);
    }
  }, [api]);

  const updatePreferences = useCallback(
    async (prefs: Partial<Preferences>) => {
      await api.updatePreferences(prefs);
      await refresh();
    },
    [api, refresh],
  );

  const setThemePreference = useCallback(
    async (theme: Preferences["theme"]) => {

      if (theme) applyTheme(theme === "dark" ? "dark" : "light");
      try {
        await updatePreferences({ theme });
      } catch {
        /* offline / unauthenticated  -  local theme still applies */
      }
    },
    [updatePreferences],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onReady = () => {
      void refresh();
    };
    window.addEventListener(CREDENTIAL_READY_EVENT, onReady);
    return () => window.removeEventListener(CREDENTIAL_READY_EVENT, onReady);
  }, [refresh]);

  const appliedTheme = useRef(false);
  useEffect(() => {
    if (appliedTheme.current) return;
    const t = me?.preferences?.theme;
    if (t) {
      applyTheme(t === "dark" ? "dark" : "light");
      appliedTheme.current = true;
    }
  }, [me]);

  const value = useMemo(
    () => ({ me, loading, refresh, updatePreferences, setThemePreference }),
    [me, loading, refresh, updatePreferences, setThemePreference],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
