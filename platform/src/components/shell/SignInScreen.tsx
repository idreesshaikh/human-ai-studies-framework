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

    return () => unmountSignIn(el);
  }, [showClerkWidget, mountSignIn, unmountSignIn]);

  if (!resolving && hasCredential) {
    return <Navigate to={next} replace />;
  }

  return (

    <div
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

        <Card>
          <CardContent className="flex flex-col gap-4 p-8">
            <h1 className="type-title text-text">Sign in</h1>
            {showClerkWidget ? (

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
            whoever runs it for yours  -  it is the value of{" "}

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
