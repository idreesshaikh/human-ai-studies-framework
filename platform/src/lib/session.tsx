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
  /** Persist part of this identity's profile (FR-OPS-7) and refresh `me`. */
  updatePreferences: (prefs: Partial<Preferences>) => Promise<void>;
  /** Apply a theme preference locally and persist it to the profile. */
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
      // Not signed in (401)  -  the auth layer's `onUnauthorized` listener
      // shows the sign-in surface; this just avoids an unhandled rejection.
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
      // Local change first so the chrome reacts instantly; persist is
      // best-effort and doesn't block the UI. A legacy "system" preference
      // resolves to light  -  the app no longer auto-follows the OS.
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

  // When the auth layer establishes a live credential (e.g. after a Clerk
  // sign-in reload), the session's first /me may have 401'd  -  re-fetch now
  // that a token is available.
  useEffect(() => {
    const onReady = () => {
      void refresh();
    };
    window.addEventListener(CREDENTIAL_READY_EVENT, onReady);
    return () => window.removeEventListener(CREDENTIAL_READY_EVENT, onReady);
  }, [refresh]);

  // Server profile is authoritative for the initial theme (FR-OPS-7): when a
  // signed-in identity has a saved theme, honour it over the local default.
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
