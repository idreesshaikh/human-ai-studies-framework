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
import { apiBase, onUnauthorized, setTokenProvider } from "./api.ts";

/* Sign-in state for the app shell (FR-OPS-5, D29).
 *
 * The middleware announces its sign-in mode via GET /auth/config; any 401
 * from the API flips `needed` and `Shell` (App.tsx) renders the sign-in
 * surface instead of letting project pages fail one by one.
 *
 * - token mode: signing in stores the bearer token where the API client
 *   already looks (`middleware.token`, see api.ts's tokenProvider default).
 * - clerk mode: clerk-js is hot-loaded from the Clerk instance's own domain
 *   (Clerk's documented pattern for non-React apps  -  the npm package's ESM
 *   build ships without the UI renderer, so self-bundling mounts nothing;
 *   @clerk/clerk-js stays a types-only devDependency, never a runtime one).
 *   Since clerk-js v6 the component renderer lives in a second script,
 *   @clerk/ui: it must load first (it sets window.__internal_ClerkUICtor)
 *   and the constructor is passed to Clerk.load({ ui: { ClerkUI } })  -  a
 *   bare load() initializes headless and mountSignIn throws "not loaded
 *   with Ui components". Once loaded, the API client gets a live token
 *   getter (Clerk session JWTs are short-lived; clerk-js refreshes them, we
 *   fetch one per request via setTokenProvider). If the script can't load,
 *   the paste-a-token fallback still works  -  a manually issued session
 *   token verifies server-side the same way. */

export interface AuthConfig {
  mode: "none" | "token" | "clerk";
  clerkPublishableKey?: string;
}

interface ClerkUser {
  id: string;
  label: string;
  email?: string;
  imageUrl?: string;
}

/** The handful of Clerk instance members this module actually calls  -  typed
 * by hand so no runtime dependency on @clerk/clerk-js is needed (the real
 * object arrives via the hotloaded script, never imported). */
interface ClerkInstance {
  user?: {
    id: string;
    primaryEmailAddress?: { emailAddress?: string };
    username?: string | null;
    firstName?: string | null;
    lastName?: string | null;
    imageUrl?: string | null;
  } | null;
  session?: { getToken(): Promise<string | null> };
  load(opts?: {
    ui?: { ClerkUI: unknown };
    appearance?: Record<string, unknown>;
  }): Promise<void>;
  mountSignIn(el: HTMLDivElement, opts: Record<string, unknown>): void;
  unmountSignIn(el: HTMLDivElement): void;
  addListener(cb: (payload: { session: unknown }) => void): void;
  signOut(): Promise<void>;
}

/** Themes the hosted Clerk widget to match Phoenix's own design tokens
 * (tokens.css) instead of Clerk's stock look. Clerk's components mount as
 * plain DOM in this page (no iframe, no shadow root), so `var(--x)` values
 * resolve live off `:root` / `[data-theme]`  -  the widget re-themes for free
 * when the app's light/dark toggle flips `data-theme`, with no rebuild or
 * remount needed. `header`/`headerTitle`/`headerSubtitle` are hidden since
 * `SignInScreen` renders the matching heading itself, once, above every
 * sign-in surface (Clerk widget or token-paste fallback alike). */
const CLERK_APPEARANCE = {
  /* Matches the `clerk` layer named in index.css's @layer order  -  without
   * it, Clerk's own (unlayered) CSS always beats our Tailwind v4 utility
   * classes below (bg-transparent, shadow-none, w-full…) regardless of
   * specificity, since Tailwind v4 utilities live inside a cascade layer
   * and unlayered rules automatically outrank any layer. */
  cssLayerName: "clerk",
  variables: {
    colorPrimary: "var(--accent)",
    colorBackground: "var(--surface)",
    colorInputBackground: "var(--bg)",
    colorInputText: "var(--text)",
    colorText: "var(--text)",
    colorTextSecondary: "var(--text-muted)",
    colorDanger: "var(--status-critical)",
    colorSuccess: "var(--grounded)",
    colorNeutral: "var(--text-muted)",
    colorShimmer: "var(--border)",
    borderRadius: "var(--radius-input)",
    fontFamily: "var(--font-sans)",
    fontFamilyButtons: "var(--font-sans)",
    fontSize: "0.875rem",
  },
  elements: {
    rootBox: "w-full",
    cardBox: "w-full shadow-none border-none bg-transparent",
    card: "border-none bg-transparent p-0 shadow-none w-full",
    header: "hidden",
    headerTitle: "hidden",
    headerSubtitle: "hidden",
    footer: "bg-transparent",
    // Establishes this as the containing block for its own decorative
    // dev-mode-banner overlay (see the CSS backstop in index.css), and adds
    // the margin-top the row above it doesn't otherwise reserve.
    footerItem: "relative mt-2",
    // Just drop the "last used" indicator outright  -  pulling it into flow
    // (a prior attempt) still crowded the button row and truncated its
    // label, and it's cosmetic, not load-bearing for the sign-in flow.
    lastAuthenticationStrategyBadge: "hidden",
    /* Clerk sizes this to a viewport-fit budget for its usual modal/popover
     * use case; in this full-page card it just clips a sliver off the top
     * and bottom of the step content with no visible scrollbar cue. */
    scrollBox: "!overflow-visible !max-h-none",
    footerActionLink: "text-accent hover:text-accent",
    socialButtonsBlockButton:
      "border border-border-strong bg-surface text-text shadow-mark rounded-input type-control normal-case hover:bg-zone-9",
    socialButtonsBlockButtonText: "type-label normal-case",
    dividerLine: "bg-border",
    dividerText: "type-legend text-text-muted",
    formFieldLabel:
      "type-legend text-text-muted",
    formFieldInput:
      "rounded-input border border-border-strong bg-surface-raised type-body text-text focus:border-accent",
    formButtonPrimary:
      "rounded-input border control-primary shadow-mark type-control normal-case",
    identityPreviewText: "type-body text-text",
    identityPreviewEditButton: "text-accent",
    otpCodeFieldInput: "border-border-strong bg-surface-raised type-quantity text-text",
    formResendCodeLink: "text-accent",
  },
} as const;

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

/** Inject Clerk's hotload scripts from the instance domain  -  @clerk/ui first
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
  /** True until the credential check has actually run once  -  false/loading
   * for clerk mode while clerk-js is still loading. `Shell` should render
   * neither the app nor the sign-in screen while this is true, or a signed-
   * in reload flashes the sign-in card for the resolution window. */
  resolving: boolean;
  /** Whether *some* credential exists  -  a signed-in Clerk user or a pasted
   * token  -  so `Shell` can gate before the first round-trip 401s. */
  hasCredential: boolean;
  mountSignIn: (el: HTMLDivElement) => void;
  unmountSignIn: (el: HTMLDivElement) => void;
  signInWithToken: (token: string) => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AuthConfig>({ mode: "none" });
  const [needed, setNeeded] = useState(false);
  const [clerkReady, setClerkReady] = useState(false);
  const [user, setUser] = useState<ClerkUser | null>(null);
  // True until we actually know whether a credential exists. In clerk mode,
  // `hasCredential` reads false the instant `config.mode` flips to "clerk"
  // but before clerk-js has loaded and checked the session cookie  -  without
  // this gate, `Shell` reads that transient "no credential yet" as "sign
  // in needed" and flashes the token-paste sign-in card on every refresh of
  // an already-signed-in session, for as long as clerk-js takes to load.
  const [resolving, setResolving] = useState(true);
  const clerkRef = useRef<ClerkInstance | null>(null);
  // Clerk's addListener fires immediately with the *current* state on
  // registration, not only on real changes  -  without this guard, a user who
  // is already signed in (the common case: every reload) gets reloaded
  // again the instant the listener registers, forever (the "kept
  // refreshing" bug). Only reload on a genuine falsy->truthy transition.
  const hadSessionRef = useRef(false);

  useEffect(() => onUnauthorized(() => setNeeded(true)), []);

  const initClerk = useCallback(async (publishableKey: string) => {
    try {
      const { clerk, ui } = await loadClerkScript(publishableKey);
      await clerk.load(
        ui ? { ui: { ClerkUI: ui }, appearance: CLERK_APPEARANCE } : undefined,
      );
      clerkRef.current = clerk;
      // Without the UI renderer, mountSignIn throws; keep the token-paste
      // fallback surface instead of an empty scrim.
      setClerkReady(ui !== undefined);
      hadSessionRef.current = Boolean(clerk.user);
      if (clerk.user) {
        const u = clerk.user;
        const label =
          u.firstName || u.lastName
            ? [u.firstName, u.lastName].filter(Boolean).join(" ")
            : (u.primaryEmailAddress?.emailAddress ?? u.username ?? u.id);
        setUser({
          id: u.id,
          label,
          email: u.primaryEmailAddress?.emailAddress,
          imageUrl: u.imageUrl ?? undefined,
        });
        setTokenProvider(async () => (await clerk.session?.getToken()) ?? null);
        setNeeded(false);
        // Tell the session layer a live token now exists so it can re-fetch
        // /me (its first call may have 401'd before Clerk finished loading).
        window.dispatchEvent(new Event(CREDENTIAL_READY_EVENT));
      }
      // The mounted sign-in UI completes in-page: once a *new* session
      // appears (not the already-active one this listener is immediately
      // handed on registration), reload so every view restarts signed in.
      clerk.addListener(({ session }) => {
        if (session && !hadSessionRef.current) {
          hadSessionRef.current = true;
          location.reload();
        } else if (!session) {
          hadSessionRef.current = false;
        }
      });
    } catch {
      // clerk-js unreachable (offline, blocked CDN…)  -  the token-paste
      // fallback surface stays usable; never a hard failure.
    } finally {
      setResolving(false);
    }
  }, []);

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
          cfg = await res.json();
        } else if (res.status === 404) {
          // A reachable server that predates /auth/config: assume token
          // mode so a 401 still gets a sign-in surface rather than a dead
          // page.
          cfg = { mode: "token" };
        }
      } catch {
        // No server reachable at all (local dev with nothing on :8000, a
        // static preview)  -  stay in "none". createApi() already falls back
        // to the offline in-memory demo for this exact case, so the shell
        // should stay unlocked rather than show a sign-in dead end.
      }
      if (cancelled) return;
      setConfig(cfg);
      if (cfg.mode === "clerk" && cfg.clerkPublishableKey) {
        await initClerk(cfg.clerkPublishableKey);
      } else {
        setResolving(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initClerk]);

  const mountSignIn = useCallback((el: HTMLDivElement) => {
    // Land a freshly-signed-in user on the projects page, not the public hero.
    // Without an explicit target Clerk applies its default afterSignInUrl of
    // "/" (the Hero), so the reload in the session listener just re-lands there.
    clerkRef.current?.mountSignIn(el, {
      appearance: CLERK_APPEARANCE,
      fallbackRedirectUrl: "/home",
      signInForceRedirectUrl: "/home",
      afterSignInUrl: "/home",
    });
  }, []);

  // Paired with mountSignIn as StrictMode's cleanup (SignInScreen's effect):
  // without it, StrictMode's dev-only double-invoke (mount -> cleanup ->
  // mount) mounts a second widget instance into the same node without ever
  // tearing down the first, and since Clerk's internal step content is
  // absolutely positioned, the two instances overlap instead of stacking  -
  // read as clipped/ghosted content, not a doubled layout.
  const unmountSignIn = useCallback((el: HTMLDivElement) => {
    clerkRef.current?.unmountSignIn(el);
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
      resolving,
      hasCredential,
      mountSignIn,
      unmountSignIn,
      signInWithToken,
      signOut,
    }),
    [
      config,
      needed,
      clerkReady,
      user,
      resolving,
      hasCredential,
      mountSignIn,
      unmountSignIn,
      signInWithToken,
      signOut,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Fired (on `window`) once a credential is live so the session layer can
 * re-fetch `/me` with the new token. Without it, the session's first `/me`
 * (fired before Clerk finishes loading) would 401 and leave `me` stale
 * after a Clerk sign-in reload. */
export const CREDENTIAL_READY_EVENT = "auth:credential-ready";
