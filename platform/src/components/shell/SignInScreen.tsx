import {
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { KeyRound, Moon, Sun } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PhoenixMark } from "@/components/brand/PhoenixMark";
import { useAuth } from "@/lib/auth.tsx";
import { getTheme, nextTheme, applyTheme, subscribeTheme } from "@/lib/theme";
import { safeNext } from "@/lib/returnTo";

const THEME_ICON = { light: Sun, dark: Moon };

/* The sign-in gate for the multi-researcher shell (FR-OPS-5). `Shell`
 * (App.tsx) renders this instead of the project chrome whenever no
 * credential is present. Clerk mode mounts the hosted sign-in UI once its
 * script has loaded, themed to the app's own tokens (see auth.tsx's
 * CLERK_APPEARANCE) so it never reads as a foreign, unstyled widget; every
 * mode also accepts a pasted session token, so a broken CDN or a
 * self-hosted `token` deployment never dead-ends. */
export function SignInScreen() {
  const { config, clerkReady, mountSignIn, unmountSignIn, hasCredential, resolving } =
    useAuth();
  const mountRef = useRef<HTMLDivElement>(null);
  const showClerkWidget = config.mode === "clerk" && clerkReady;
  const theme = useSyncExternalStore(subscribeTheme, getTheme, getTheme);
  const ThemeIcon = THEME_ICON[theme];
  const [searchParams] = useSearchParams();
  const next = safeNext(searchParams.get("next"));

  useEffect(() => {
    if (!showClerkWidget || !mountRef.current) return;
    const el = mountRef.current;
    mountSignIn(el);
    // Without this, StrictMode's dev-only double-invoke mounts a second
    // widget instance into the same node without tearing down the first,
    // and the two overlap (Clerk's step content is absolutely positioned)
    // instead of stacking — read as clipped/ghosted content.
    return () => unmountSignIn(el);
  }, [showClerkWidget, mountSignIn, unmountSignIn]);

  /* Already signed in: forward, don't frame a sign-in card.
   *
   * This is the whole return-to mechanism. Signing in ends in
   * `location.reload()`, so the browser comes back to this same URL —
   * `/signin?next=/repertoire` — and by then the credential exists. Reading
   * `next` here and redirecting is what carries the researcher back to the
   * page they left, across a reload that destroys every other kind of state.
   *
   * `resolving` is respected for the same reason `Shell` does: in clerk mode
   * `hasCredential` reads false until clerk-js has checked the session, and
   * forwarding on that transient false would bounce an already-signed-in
   * visitor. `replace` so Back does not return to a sign-in page that would
   * only forward again. */
  if (!resolving && hasCredential) {
    return <Navigate to={next} replace />;
  }

  return (
    /* The page is full width and the CONTENT is measured. These were the same
     * element — `relative mx-auto max-w-narrow` — so the theme toggle's
     * `right-4` resolved against a 26rem column rather than the window, and
     * it hung in open space a third of the way across the screen instead of
     * sitting in the corner it was written for. */
    <div
      data-agent="sign-in"
      className="relative flex min-h-screen flex-col justify-center p-6"
    >
      <div className="absolute right-4 top-4 flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => applyTheme(nextTheme(theme))}
          aria-label={`Theme: ${theme}`}
        >
          <ThemeIcon aria-hidden />
        </Button>
      </div>

      <div className="mx-auto flex w-full max-w-narrow flex-col">
        <Link
          to="/"
          className="mb-8 flex flex-col items-center gap-2 text-center"
          aria-label="Phoenix, back to home"
        >
          <PhoenixMark size={40} />
          <span className="type-section text-text">Phoenix</span>
        </Link>

        {/* One clean card is the sign-in frame. Clerk's hosted widget mounts
         * inside it rendered transparent (CLERK_APPEARANCE strips its own card
         * chrome and hides its heading, auth.tsx), so there's a single frame,
         * not a card-within-a-card, and our own "Sign in" heading shows once. */}
        <Card>
          <CardContent className="flex flex-col gap-4 p-8">
            <h1 className="type-title text-text">Sign in</h1>
            {showClerkWidget ? (
              /* `relative`: Clerk's internal step-transition wrapper is
               * absolutely positioned; without a positioned ancestor here it
               * anchors to the outer screen wrapper (also `relative`) instead,
               * floating the widget free of this card. */
              <div ref={mountRef} className="clerk-embed relative" />
            ) : (
              <TokenForm awaitingClerk={config.mode === "clerk"} />
            )}
          </CardContent>
        </Card>

        <Link
          to="/"
          className="mt-8 text-center type-body text-text-muted hover:text-text"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}

function TokenForm({ awaitingClerk }: { awaitingClerk: boolean }) {
  const { signInWithToken } = useAuth();
  const [token, setToken] = useState("");
  const fieldId = useId();
  const hintId = `${fieldId}-hint`;

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (token.trim()) signInWithToken(token);
      }}
    >
      {/* A visible label and a stated source. The field carried its name in a
       * placeholder and an aria-label only, so the one instruction on the
       * page vanished the moment you typed into it — and it named the thing
       * ("Session token") without ever saying where a researcher is supposed
       * to get one, which is the only question anyone actually has here. */}
      <Label htmlFor={fieldId}>Session token</Label>
      <Input
        id={fieldId}
        type="password"
        autoComplete="current-password"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        aria-describedby={hintId}
      />
      <p id={hintId} className="type-caption text-text-muted">
        {awaitingClerk ? (
          "The sign-in widget couldn't load. Check your connection, or ask whoever runs this deployment for a session token."
        ) : (
          <>
            This deployment signs in with a token rather than an account. Ask
            whoever runs it for yours — it is the value of{" "}
            {/* An identifier, so it is set in the measurement voice, the same
              * as every other literal a reader has to match exactly. */}
            <span className="font-mono text-text">MIDDLEWARE_TOKEN</span> on the
            server.
          </>
        )}
      </p>
      <Button type="submit" disabled={!token.trim()} className="mt-1">
        <KeyRound aria-hidden /> Sign in
      </Button>
    </form>
  );
}
