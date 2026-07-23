import { useParams } from "react-router-dom";
import { Clock } from "lucide-react";
import { MembersTable } from "@/components/members/MembersTable";
import { InviteDialog } from "@/components/members/InviteDialog";
import { RoleGate } from "@/components/shell/RoleGate";
import { Badge } from "@/components/ui/badge";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { ROLE_LABELS, type Role } from "@/lib/capabilities.ts";

/* Members + pending invitations. Owners see the invite action and the
 * per-member role menu; everyone else sees a read-only roster. */
export function Members() {
  const api = useApi();
  const { me } = useSession();
  const { slug = "" } = useParams();
  const { data, loading, error, reload } = useAsync(
    () => api.projectHome(slug),
    [api, slug],
  );

  if (loading) return <p className="p-6 text-sm text-text-muted">Loading…</p>;
  if (error) return <p className="p-6 text-sm text-unsourced">{error}</p>;
  if (!data) return null;

  // The caller's role comes from their own memberships (the server enforces
  // regardless; this only decides which controls to show).
  const mine = (me?.memberships.find((m) => m.projectSlug === slug)?.role ??
    "viewer") as Role;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl font-medium tracking-tight text-text">Members</h1>
          <p className="text-sm text-text-muted">Who can see and shape this project.</p>
        </div>
        <RoleGate role={mine} capability="invite_member">
          <InviteDialog slug={slug} onInvited={reload} />
        </RoleGate>
      </div>

      <MembersTable slug={slug} myRole={mine} members={data.members} onChanged={reload} />

      {data.invitations.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="flex items-center gap-2 text-sm font-medium text-text">
            <Clock className="size-4 text-text-muted" aria-hidden /> Pending invitations
          </h2>
          <div className="flex flex-col gap-2">
            {data.invitations.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center gap-2 rounded-input border border-border px-3 py-2 text-sm"
              >
                <span className="text-text">{inv.email}</span>
                <Badge variant="outline">{ROLE_LABELS[inv.role]}</Badge>
                <span className="ml-auto text-xs text-text-muted">
                  expires {inv.expiresAt.slice(0, 10)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
