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

const CLERK_APPEARANCE = {

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

    footerItem: "relative mt-2",

    lastAuthenticationStrategyBadge: "hidden",

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

async function loadClerkScript(
  publishableKey: string,
): Promise<{ clerk: ClerkInstance; ui: unknown }> {
  const w = window as unknown as { Clerk?: ClerkInstance; __internal_ClerkUICtor?: unknown };
  const base = `https://${frontendApiFromKey(publishableKey)}/npm`;
  if (!w.__internal_ClerkUICtor) {

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

  needed: boolean;

  clerkReady: boolean;
  user: ClerkUser | null;

  resolving: boolean;

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

  const [resolving, setResolving] = useState(true);
  const clerkRef = useRef<ClerkInstance | null>(null);

  const hadSessionRef = useRef(false);

  useEffect(() => onUnauthorized(() => setNeeded(true)), []);

  const initClerk = useCallback(async (publishableKey: string) => {
    try {
      const { clerk, ui } = await loadClerkScript(publishableKey);
      await clerk.load(
        ui ? { ui: { ClerkUI: ui }, appearance: CLERK_APPEARANCE } : undefined,
      );
      clerkRef.current = clerk;

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

        window.dispatchEvent(new Event(CREDENTIAL_READY_EVENT));
      }

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

        const res = await fetch(`${apiBase()}/auth/config`, {
          credentials: "include",
        });
        if (res.ok) {
          cfg = await res.json();
        } else if (res.status === 404) {

          cfg = { mode: "token" };
        }
      } catch {
        cfg = { mode: "none" };
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

    clerkRef.current?.mountSignIn(el, {
      appearance: CLERK_APPEARANCE,
      fallbackRedirectUrl: "/home",
      signInForceRedirectUrl: "/home",
      afterSignInUrl: "/home",
    });
  }, []);

  const unmountSignIn = useCallback((el: HTMLDivElement) => {
    clerkRef.current?.unmountSignIn(el);
  }, []);

  const signInWithToken = useCallback((token: string) => {
    localStorage.setItem("middleware.token", token.trim());
    setNeeded(false);

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

export const CREDENTIAL_READY_EVENT = "auth:credential-ready";
