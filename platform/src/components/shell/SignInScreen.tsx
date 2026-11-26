import { useId, useState, useSyncExternalStore } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { KeyRound, Moon, Sun } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { PhoenixMark } from "@/components/brand/PhoenixMark";
import { useAuth } from "@/lib/auth.tsx";
import { getTheme, nextTheme, applyTheme, subscribeTheme, themeToggleLabel } from "@/lib/theme";
import { safeNext } from "@/lib/returnTo";

const THEME_ICON = { light: Sun, dark: Moon };

/* The sign-in gate (FR-OPS-5). `Shell` (App.tsx) renders this instead of the
 * app shell when the server runs in token mode and no token is stored. */
export function SignInScreen() {
  const { hasCredential, resolving } = useAuth();
  const theme = useSyncExternalStore(subscribeTheme, getTheme, getTheme);
  const ThemeIcon = THEME_ICON[theme];
  const [searchParams] = useSearchParams();
  const next = safeNext(searchParams.get("next"));

  /* Wait for auth to resolve, then replace the sign-in URL with its saved return path. */
  if (!resolving && hasCredential) {
    return <Navigate to={next} replace />;
  }

  return (
    /* The page is full width and the CONTENT is measured. These were the same
     * element  -  `relative mx-auto max-w-narrow`  -  so the theme toggle's
     * `right-4` resolved against a 26rem column rather than the window, and
     * it hung in open space a third of the way across the screen instead of
     * sitting in the corner it was written for. */
    <main
      className="relative flex min-h-screen flex-col justify-center p-6"
    >
      <div className="absolute right-4 top-4 flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => applyTheme(nextTheme(theme))}
          aria-label={themeToggleLabel(theme)}
        >
          <ThemeIcon aria-hidden />
        </Button>
      </div>

      <div className="mx-auto flex w-full max-w-narrow flex-col">
        <div className="mb-8 flex flex-col items-center gap-3 text-center">
          <PhoenixMark size={36} />
          <span className="type-section text-text">StudyLoop</span>
          <p className="type-note text-text-muted">Design evidence-grounded developer studies</p>
        </div>

        <Card>
          <CardContent className="flex flex-col gap-4 p-8">
            <h1 className="type-title text-text">Sign in</h1>
            <TokenForm />
          </CardContent>
        </Card>

        <p className="mt-6 text-center type-caption text-text-muted">
          StudyLoop helps researchers configure, run and inspect human–AI developer studies.
        </p>
      </div>
    </main>
  );
}

function TokenForm() {
  const { signInWithToken } = useAuth();
  const [token, setToken] = useState("");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const fieldId = useId();

  return (
    <form
      className="form-stack"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!token.trim() || checking) return;
        setChecking(true);
        setError("");
        try {
          await signInWithToken(token);
        } catch (error) {
          setError(error instanceof Error ? error.message : "Could not sign in. Try again.");
        } finally {
          setChecking(false);
        }
      }}
    >
      {/* A visible label and a stated source. The field carried its name in a
       * placeholder and an aria-label only, so the one instruction on the
       * page vanished the moment you typed into it  -  and it named the thing
       * ("Session token") without ever saying where a researcher is supposed
       * to get one, which is the only question anyone actually has here. */}
      <Field
        id={fieldId}
        label="Session token"
        required
        error={error}
        hint={
          <>
            This instance signs in with a token rather than an account. Ask
            whoever runs it for yours  -  it is the value of{" "}
            {/* An identifier, so it is set in the measurement voice, the same
              * as every other literal a reader has to match exactly. */}
            <span className="font-mono text-text">MIDDLEWARE_TOKEN</span> on the
            server.
          </>
        }
      >
        <Input
          type="password"
          autoComplete="current-password"
          value={token}
          readOnly={checking}
          onChange={(e) => {
            setToken(e.target.value);
            setError("");
          }}
        />
      </Field>
      <Button type="submit" disabled={!token.trim() || checking} className="mt-1">
        <KeyRound aria-hidden /> {checking ? "Checking token…" : "Sign in"}
      </Button>
    </form>
  );
}
