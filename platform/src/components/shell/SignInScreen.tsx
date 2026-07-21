import { useEffect, useRef, useState } from "react";
import { KeyRound, Moon, Sun, Monitor } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth.tsx";
import { getTheme, nextTheme, applyTheme, type Theme } from "@/lib/theme";

const THEME_ICON = { system: Monitor, light: Sun, dark: Moon };

/* The sign-in gate for the multi-researcher shell (FR-OPS-5). `Shell`
 * (App.tsx) renders this instead of the project chrome whenever no
 * credential is present. Clerk mode mounts the hosted sign-in UI once its
 * script has loaded, themed to the app's own tokens (see auth.tsx's
 * CLERK_APPEARANCE) so it never reads as a foreign, unstyled widget; every
 * mode also accepts a pasted session token, so a broken CDN or a
 * self-hosted `token` deployment never dead-ends. */
export function SignInScreen() {
  const { config, clerkReady, mountSignIn } = useAuth();
  const mountRef = useRef<HTMLDivElement>(null);
  const showClerkWidget = config.mode === "clerk" && clerkReady;
  const [theme, setTheme] = useState<Theme>(() => getTheme());
  const ThemeIcon = THEME_ICON[theme];

  useEffect(() => {
    if (showClerkWidget && mountRef.current) mountSignIn(mountRef.current);
  }, [showClerkWidget, mountSignIn]);

  return (
    <div
      data-agent="sign-in"
      className="relative mx-auto flex min-h-screen max-w-md flex-col justify-center p-6"
    >
      <Button
        variant="ghost"
        size="icon"
        className="absolute right-4 top-4"
        onClick={() => {
          const next = nextTheme(theme);
          setTheme(next);
          applyTheme(next);
        }}
        aria-label={`Theme: ${theme}`}
      >
        <ThemeIcon aria-hidden />
      </Button>

      <div className="mb-6 flex flex-col items-center gap-2 text-center">
        <span
          aria-hidden
          className="inline-grid size-9 shrink-0 place-items-center rounded-input border border-border-strong bg-accent font-serif text-lg font-medium text-accent-contrast shadow-brutal-sm"
        >
          S
        </span>
        <span className="font-serif text-xl font-medium tracking-tight text-text">
          The Study Desk
        </span>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 p-8">
          <div>
            <h1 className="font-serif text-2xl font-medium text-text">Sign in</h1>
            <p className="text-sm text-text-muted">
              {showClerkWidget
                ? "See your projects and pick up a study where you left off."
                : "Paste the session token this instance issued."}
            </p>
          </div>
          {showClerkWidget ? (
            <div ref={mountRef} />
          ) : (
            <TokenForm awaitingClerk={config.mode === "clerk"} />
          )}
        </CardContent>
      </Card>
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
          Clerk's sign-in widget couldn't load — check your connection, or ask
          an admin for a session token.
        </p>
      )}
    </form>
  );
}
