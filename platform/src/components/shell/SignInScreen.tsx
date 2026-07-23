import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { KeyRound, Moon, Sun } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { KiteMark } from "@/components/brand/KiteMark";
import { useAuth } from "@/lib/auth.tsx";
import { getTheme, nextTheme, applyTheme, type Theme } from "@/lib/theme";

const THEME_ICON = { light: Sun, dark: Moon };

/* The sign-in gate for the multi-researcher shell (FR-OPS-5). `Shell`
 * (App.tsx) renders this instead of the project chrome whenever no
 * credential is present. Clerk mode mounts the hosted sign-in UI once its
 * script has loaded, themed to the app's own tokens (see auth.tsx's
 * CLERK_APPEARANCE) so it never reads as a foreign, unstyled widget; every
 * mode also accepts a pasted session token, so a broken CDN or a
 * self-hosted `token` deployment never dead-ends. */
export function SignInScreen() {
  const { config, clerkReady, mountSignIn, unmountSignIn } = useAuth();
  const mountRef = useRef<HTMLDivElement>(null);
  const showClerkWidget = config.mode === "clerk" && clerkReady;
  const [theme, setTheme] = useState<Theme>(() => getTheme());
  const ThemeIcon = THEME_ICON[theme];

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

  return (
    <div
      data-agent="sign-in"
      className="relative mx-auto flex min-h-screen max-w-md flex-col justify-center p-6"
    >
      <div className="absolute right-4 top-4 flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => {
            const next = nextTheme(theme);
            setTheme(next);
            applyTheme(next);
          }}
          aria-label={`Theme: ${theme}`}
        >
          <ThemeIcon aria-hidden />
        </Button>
      </div>

      <Link
        to="/"
        className="mb-8 flex flex-col items-center gap-2 text-center"
        aria-label="Phoenix, back to home"
      >
        <KiteMark size={40} />
        <span className="font-serif text-xl font-medium tracking-tight text-text">
          Phoenix
        </span>
      </Link>

      {/* One clean card is the sign-in frame. Clerk's hosted widget mounts
       * inside it rendered transparent (CLERK_APPEARANCE strips its own card
       * chrome and hides its heading, auth.tsx), so there's a single frame,
       * not a card-within-a-card, and our own "Sign in" heading shows once. */}
      <Card>
        <CardContent className="flex flex-col gap-4 p-8">
          <h1 className="font-serif text-2xl font-medium text-text">Sign in</h1>
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
        className="mt-8 text-center text-sm text-text-muted hover:text-text"
      >
        Back to home
      </Link>
    </div>
  );
}

function TokenForm({ awaitingClerk }: { awaitingClerk: boolean }) {
  const { signInWithToken } = useAuth();
  const [token, setToken] = useState("");

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (token.trim()) signInWithToken(token);
      }}
    >
      <Input
        type="password"
        placeholder="Session token"
        value={token}
        onChange={(e) => setToken(e.target.value)}
        aria-label="Session token"
      />
      <Button type="submit" disabled={!token.trim()}>
        <KeyRound aria-hidden /> Sign in
      </Button>
      {awaitingClerk && (
        <p className="text-xs text-text-muted">
          The sign-in widget couldn't load. Check your connection, or ask an
          admin for a session token.
        </p>
      )}
    </form>
  );
}
