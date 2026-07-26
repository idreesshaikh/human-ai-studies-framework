import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PartyPopper } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useApi, useSession } from "@/lib/session";
import { ApiError } from "@/lib/api.ts";
import { ROLE_LABELS, type Role } from "@/lib/capabilities.ts";

/* The landing route for an invitation link. Accepting joins the project and
 * drops the newcomer straight into it — the one celebratory moment in the
 * shell. Expired/used tokens fail with a human explanation. */
export function InviteAccept() {
  const api = useApi();
  const { refresh } = useSession();
  const navigate = useNavigate();
  const { token = "" } = useParams();
  const [state, setState] = useState<"idle" | "joining" | "joined">("idle");
  const [role, setRole] = useState<Role | null>(null);
  const [error, setError] = useState("");

  const accept = async () => {
    setState("joining");
    setError("");
    try {
      const res = await api.acceptInvitation(token);
      setRole(res.role);
      setState("joined");
      await refresh();
      setTimeout(() => navigate(`/p/${res.projectSlug}`), 1200);
    } catch (e) {
      setState("idle");
      setError(
        e instanceof ApiError
          ? e.message
          : "This invitation could not be accepted.",
      );
    }
  };

  return (
    <div className="mx-auto flex min-h-full max-w-narrow flex-col justify-center p-8">
      <Card>
        <CardContent className="flex flex-col items-center gap-4 p-8 text-center">
          {state === "joined" ? (
            <>
              <PartyPopper className="size-10 text-accent animate-in zoom-in duration-entrance" aria-hidden />
              <h1 className="type-title text-text">You're in</h1>
              <p className="text-sm text-text-muted">
                Joined as {role ? ROLE_LABELS[role] : "a member"}. Taking you
                to the project…
              </p>
            </>
          ) : (
            <>
              <h1 className="type-title text-text">
                You've been invited to a project
              </h1>
              <p className="text-sm text-text-muted">
                Accept to join and start collaborating.
              </p>
              {error && (
                <p className="text-sm text-unsourced">
                  {error} <Link to="/home" className="underline">Go to your projects</Link>.
                </p>
              )}
              <Button onClick={accept} disabled={state === "joining"}>
                {state === "joining" ? "Joining…" : "Accept invitation"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
