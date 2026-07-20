import { useEffect, useRef, useState } from "react";
import { KeyRound } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth.tsx";

/* The sign-in gate for the multi-researcher shell (FR-OPS-5). `Shell`
 * (App.tsx) renders this instead of the project chrome whenever no
 * credential is present. Clerk mode mounts the hosted sign-in UI once its
 * script has loaded; every mode also accepts a pasted session token, so a
 * broken CDN or a self-hosted `token` deployment never dead-ends. */
export function SignInScreen() {
  const { config, clerkReady, mountSignIn } = useAuth();
  const mountRef = useRef<HTMLDivElement>(null);
  const showClerkWidget = config.mode === "clerk" && clerkReady;

  useEffect(() => {
    if (showClerkWidget && mountRef.current) mountSignIn(mountRef.current);
  }, [showClerkWidget, mountSignIn]);

  return (
    <div
      data-agent="sign-in"
      className="mx-auto flex min-h-full max-w-md flex-col justify-center p-6"
    >
      <Card>
        <CardContent className="flex flex-col gap-4 p-8">
          <div>
            <h1 className="font-serif text-2xl font-medium text-text">Sign in</h1>
            <p className="text-sm text-text-muted">
              {showClerkWidget
                ? "Sign in to see your projects and studies."
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
