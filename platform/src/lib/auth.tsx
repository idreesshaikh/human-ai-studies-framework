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
import { onUnauthorized, setTokenProvider } from "./api.ts";

/* Sign-in state for the app shell (FR-OPS-5, D29).
 *
 * The middleware announces its sign-in mode via GET /auth/config; any 401
 * from the API flips `needed` and `Shell` (App.tsx) renders the sign-in
 * surface instead of letting project pages fail one by one.
 *
 * - token mode: signing in stores the bearer token where the API client
 *   already looks (`middleware.token`, see api.ts's tokenProvider default).
 * - clerk mode: clerk-js is hot-loaded from the Clerk instance's own domain
 *   (Clerk's documented pattern for non-React apps — the npm package's ESM
 *   build ships without the UI renderer, so self-bundling mounts nothing;
 *   @clerk/clerk-js stays a types-only devDependency, never a runtime one).
 *   Since clerk-js v6 the component renderer lives in a second script,
 *   @clerk/ui: it must load first (it sets window.__internal_ClerkUICtor)
 *   and the constructor is passed to Clerk.load({ ui: { ClerkUI } }) — a
 *   bare load() initializes headless and mountSignIn throws "not loaded
 *   with Ui components". Once loaded, the API client gets a live token
 *   getter (Clerk session JWTs are short-lived; clerk-js refreshes them, we
 *   fetch one per request via setTokenProvider). If the script can't load,
 *   the paste-a-token fallback still works — a manually issued session
 *   token verifies server-side the same way. */

export interface AuthConfig {
  mode: "none" | "token" | "clerk";
  clerkPublishableKey?: string;
}

interface ClerkUser {
  id: string;
  label: string;
}

/** The handful of Clerk instance members this module actually calls — typed
 * by hand so no runtime dependency on @clerk/clerk-js is needed (the real
 * object arrives via the hotloaded script, never imported). */
interface ClerkInstance {
  user?: {
    id: string;
    primaryEmailAddress?: { emailAddress?: string };
    username?: string | null;
  } | null;
  session?: { getToken(): Promise<string | null> };
  load(opts?: { ui?: { ClerkUI: unknown } }): Promise<void>;
  mountSignIn(el: HTMLDivElement, opts: Record<string, unknown>): void;
  addListener(cb: (payload: { session: unknown }) => void): void;
  signOut(): Promise<void>;
}

/** The instance's Frontend API domain, encoded in the publishable key
 * (`pk_test_<base64 of "domain$">`). */
function frontendApiFromKey(publishableKey: string): string {
  const b64 = publishableKey.split("_").slice(2).join("_");
  return atob(b64).replace(/\$$/, "");
}

function injectScript(src: string, configure?: (s: HTMLScriptElement) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.crossOrigin = "anonymous";
    configure?.(script);
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`failed to load ${src}`));
    document.head.appendChild(script);
  });
}

/** Inject Clerk's hotload scripts from the instance domain — @clerk/ui first
 * (the component renderer), then clerk-js core; resolves to the
 * auto-instantiated window.Clerk plus the UI constructor to pass into
 * Clerk.load(). */
async function loadClerkScript(
  publishableKey: string,
): Promise<{ clerk: ClerkInstance; ui: unknown }> {
  const w = window as unknown as { Clerk?: ClerkInstance; __internal_ClerkUICtor?: unknown };
  const base = `https://${frontendApiFromKey(publishableKey)}/npm`;
  if (!w.__internal_ClerkUICtor) {
    // Best-effort: without the UI script the token-paste fallback remains.
    await injectScript(`${base}/@clerk/ui@1/dist/ui.browser.js`).catch(() => {});
  }
  if (!w.Clerk) {
    await injectScript(`${base}/@clerk/clerk-js@6/dist/clerk.browser.js`, (s) =>
      s.setAttribute("data-clerk-publishable-key", publishableKey),
    );
  }
  if (!w.Clerk) throw new Error("clerk-js did not initialize");
  return { clerk: w.Clerk, ui: w.__internal_ClerkUICtor };
}

interface AuthState {
  config: AuthConfig;
  /** True once a 401 has come back and no sign-in surface is showing yet. */
  needed: boolean;
  /** True once clerk-js (+ its UI renderer) has loaded and can mount. */
  clerkReady: boolean;
  user: ClerkUser | null;
  /** Whether *some* credential exists — a signed-in Clerk user or a pasted
   * token — so `Shell` can gate before the first round-trip 401s. */
  hasCredential: boolean;
  mountSignIn: (el: HTMLDivElement) => void;
  signInWithToken: (token: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AuthConfig>({ mode: "none" });
  const [needed, setNeeded] = useState(false);
  const [clerkReady, setClerkReady] = useState(false);
  const [user, setUser] = useState<ClerkUser | null>(null);
  const clerkRef = useRef<ClerkInstance | null>(null);

  useEffect(() => onUnauthorized(() => setNeeded(true)), []);

  const initClerk = useCallback(async (publishableKey: string) => {
    try {
      const { clerk, ui } = await loadClerkScript(publishableKey);
      await clerk.load(ui ? { ui: { ClerkUI: ui } } : undefined);
      clerkRef.current = clerk;
      // Without the UI renderer, mountSignIn throws; keep the token-paste
      // fallback surface instead of an empty scrim.
      setClerkReady(ui !== undefined);
      if (clerk.user) {
        setUser({
          id: clerk.user.id,
          label:
            clerk.user.primaryEmailAddress?.emailAddress ?? clerk.user.username ?? clerk.user.id,
        });
        setTokenProvider(async () => (await clerk.session?.getToken()) ?? null);
        setNeeded(false);
      }
      // The mounted sign-in UI completes in-page: once a session appears,
      // reload so every view restarts signed in.
      clerk.addListener(({ session }) => {
        if (session) location.reload();
      });
    } catch {
      // clerk-js unreachable (offline, blocked CDN…) — the token-paste
      // fallback surface stays usable; never a hard failure.
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      let cfg: AuthConfig = { mode: "none" };
      try {
        const res = await fetch("/auth/config", { credentials: "include" });
        if (res.ok) {
          cfg = await res.json();
        } else if (res.status === 404) {
          // A reachable server that predates /auth/config: assume token
          // mode so a 401 still gets a sign-in surface rather than a dead
          // page.
          cfg = { mode: "token" };
        }
      } catch {
        // No server reachable at all (local dev with nothing on :8000, a
        // static preview) — stay in "none". createApi() already falls back
        // to the offline in-memory demo for this exact case, so the shell
        // should stay unlocked rather than show a sign-in dead end.
      }
      if (cancelled) return;
      setConfig(cfg);
      if (cfg.mode === "clerk" && cfg.clerkPublishableKey) {
        await initClerk(cfg.clerkPublishableKey);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initClerk]);

  const mountSignIn = useCallback((el: HTMLDivElement) => {
    clerkRef.current?.mountSignIn(el, {});
  }, []);

  const signInWithToken = useCallback((token: string) => {
    localStorage.setItem("middleware.token", token.trim());
    setNeeded(false);
    // Views cache failed loads; a clean reload restarts them signed in.
    location.reload();
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem("middleware.token");
    const clerk = clerkRef.current;
    if (clerk?.user) {
      void clerk.signOut().finally(() => location.reload());
    } else {
      location.reload();
    }
  }, []);

  const hasCredential =
    config.mode === "none" || user !== null || localStorage.getItem("middleware.token") !== null;

  const value = useMemo(
    () => ({
      config,
      needed,
      clerkReady,
      user,
      hasCredential,
      mountSignIn,
      signInWithToken,
      signOut,
    }),
    [config, needed, clerkReady, user, hasCredential, mountSignIn, signInWithToken, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
