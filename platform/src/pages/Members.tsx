import { useParams } from "react-router-dom";
import { Clock, Loader2, Trash2 } from "lucide-react";
import { MembersTable } from "@/components/members/MembersTable";
import { InviteDialog } from "@/components/members/InviteDialog";
import { RoleGate } from "@/components/shell/RoleGate";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { ROLE_LABELS, type Role } from "@/lib/capabilities.ts";
import { Notice } from "@/components/ui/notice";

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

  if (loading) {
    return (
      <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
        <p className="flex items-center gap-2 type-body text-text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading members…
        </p>
      </div>
    );
  }
  if (error) return <div className="p-gutter"><Notice kind="problem">{error}</Notice></div>;
  if (!data) return null;

  // The caller's role comes from their own memberships (the server enforces
  // regardless; this only decides which controls to show).
  const mine = (me?.memberships.find((m) => m.projectSlug === slug)?.role ??
    "viewer") as Role;

  return (
    <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="type-title text-text">Members</h1>
          <p className="type-body text-text-muted">Who can see and shape this project.</p>
        </div>
        <RoleGate role={mine} capability="invite_member">
          <InviteDialog slug={slug} onInvited={reload} />
        </RoleGate>
      </div>

      <MembersTable slug={slug} myRole={mine} members={data.members} onChanged={reload} />

      {data.invitations.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="type-subhead flex items-center gap-2 text-text">
            <Clock className="size-4 text-text-muted" aria-hidden /> Share links
          </h2>
          <div className="flex flex-col gap-2">
            {data.invitations.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center gap-2 rounded-input border border-border px-3 py-2 type-body"
              >
                <Badge variant="outline">{ROLE_LABELS[inv.role]}</Badge>
                <span className="type-caption text-text-muted">
                  created {inv.createdAt?.slice(0, 10)} · expires {inv.expiresAt.slice(0, 10)}
                </span>
                <RoleGate role={mine} capability="manage_members">
                  <Button
                    size="sm"
                    variant="subtle"
                    aria-label={`Revoke invite link for ${ROLE_LABELS[inv.role]}`}
                    onClick={() => {
                      void api.revokeInvitation(slug, inv.id).then(reload);
                    }}
                  >
                    <Trash2 aria-hidden className="size-3.5" />
                    Revoke
                  </Button>
                </RoleGate>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
