import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { apiBase, onUnauthorized } from "./api.ts";

/* Resolve sign-in mode from the server. "none" is a local, single-user
 * workspace; "token" asks once for the shared bearer token and stores it. */

export interface AuthConfig {
  mode: "none" | "token";
}

interface AuthState {
  config: AuthConfig;
  /** True once a 401 has come back and no sign-in surface is showing yet. */
  needed: boolean;
  /** True until the server's sign-in mode is known. `Shell` renders neither
   * the app nor the sign-in screen meanwhile, so a reload never flashes the
   * sign-in card. */
  resolving: boolean;
  /** Whether a credential exists, so `Shell` can gate before the first
   * round-trip 401s. */
  hasCredential: boolean;
  signInWithToken: (token: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AuthConfig>({ mode: "none" });
  const [needed, setNeeded] = useState(false);
  const [resolving, setResolving] = useState(true);

  useEffect(() => onUnauthorized(() => setNeeded(true)), []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      let cfg: AuthConfig = { mode: "none" };
      try {
        // Against the API's base, not a bare relative path  -  see apiBase().
        const res = await fetch(`${apiBase()}/auth/config`, {
          credentials: "include",
        });
        if (res.ok) {
          const body = (await res.json()) as { mode?: string };
          cfg = { mode: body.mode === "token" ? "token" : "none" };
        } else if (res.status === 404) {
          // A reachable server that predates /auth/config: assume token
          // mode so a 401 still gets a sign-in surface rather than a dead
          // page.
          cfg = { mode: "token" };
        }
      } catch {
        // Keep local auth while the server is unavailable; API loaders report
        // the connection failure instead of sending the user to sign-in.
      }
      if (cancelled) return;
      setConfig(cfg);
      setResolving(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const signInWithToken = useCallback((token: string) => {
    localStorage.setItem("middleware.token", token.trim());
    setNeeded(false);
    // Views cache failed loads; a clean reload restarts them signed in.
    location.reload();
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem("middleware.token");
    location.reload();
  }, []);

  const hasCredential =
    config.mode === "none" || localStorage.getItem("middleware.token") !== null;

  const value = useMemo(
    () => ({
      config,
      needed,
      resolving,
      hasCredential,
      signInWithToken,
      signOut,
    }),
    [config, needed, resolving, hasCredential, signInWithToken, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Fired (on `window`) once a credential is live so the session layer can
 * re-fetch `/me` with the new token. */
export const CREDENTIAL_READY_EVENT = "auth:credential-ready";
