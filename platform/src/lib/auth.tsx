import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { onUnauthorized } from "./api.ts";

/* Resolve sign-in mode from the server. "none" is a local, single-user
 * workspace; "token" asks once for the shared bearer token and stores it. */

export interface AuthConfig {
  mode: "none" | "token";
}

interface AuthState {
  config: AuthConfig;
  /** True until the server's sign-in mode is known. `Shell` renders neither
   * the app nor the sign-in screen meanwhile, so a reload never flashes the
   * sign-in card. */
  resolving: boolean;
  /** Whether the browser has a credential that the server hasn't rejected. */
  hasCredential: boolean;
  signInWithToken: (token: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AuthConfig>({ mode: "none" });
  const [credentialRejected, setCredentialRejected] = useState(false);
  const [resolving, setResolving] = useState(true);

  useEffect(() => onUnauthorized(() => setCredentialRejected(true)), []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      let cfg: AuthConfig = { mode: "none" };
      try {
        const res = await fetch("/auth/config", {
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

  const signInWithToken = useCallback(async (token: string) => {
    const candidate = token.trim();
    const response = await fetch("/me", {
      headers: { Authorization: `Bearer ${candidate}` },
      credentials: "include",
    }).catch(() => null);
    if (response?.status === 401 || response?.status === 403) {
      throw new Error("That session token wasn’t accepted. Check it and try again.");
    }
    if (!response?.ok || !response.headers.get("content-type")?.includes("application/json")) {
      throw new Error("Could not verify the session token. Try again in a moment.");
    }
    localStorage.setItem("middleware.token", candidate);
    // Views cache failed loads; a clean reload restarts them signed in.
    location.reload();
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem("middleware.token");
    location.reload();
  }, []);

  const hasCredential =
    config.mode === "none" ||
    (!credentialRejected && localStorage.getItem("middleware.token") !== null);

  const value = useMemo(
    () => ({
      config,
      resolving,
      hasCredential,
      signInWithToken,
      signOut,
    }),
    [config, resolving, hasCredential, signInWithToken, signOut],
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
