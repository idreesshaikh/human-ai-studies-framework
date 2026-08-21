import { useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuCheckItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { RoleGate } from "@/components/shell/RoleGate";
import { useApi } from "@/lib/session";
import { useAuth } from "@/lib/auth.tsx";
import { ROLE_LABELS, type Role } from "@/lib/capabilities.ts";
import { ApiError, type Member } from "@/lib/api.ts";
import { memberLabel } from "@/lib/memberLabel";
import { Notice } from "@/components/ui/notice";

const ROLES: Role[] = ["owner", "researcher", "viewer"];

/* The members table. Roles are facts, so role chips are static; owners get
 * an actions menu that edits a role optimistically and reconciles with the
 * server (reverting on error). */
export function MembersTable({
  slug,
  myRole,
  members,
  onChanged,
}: {
  slug: string;
  myRole: Role;
  members: Member[];
  onChanged: () => void;
}) {
  const api = useApi();
  const { user } = useAuth();
  const [rows, setRows] = useState(members);
  const [error, setError] = useState("");

  const setRole = async (sub: string, role: Role) => {
    const prev = rows;
    setRows((r) => r.map((m) => (m.identitySub === sub ? { ...m, role } : m)));
    setError("");
    try {
      await api.changeRole(slug, sub, role);
      onChanged();
    } catch (e) {
      setRows(prev); // reconcile: the server said no
      setError(e instanceof ApiError ? e.message : "Could not change the role.");
    }
  };

  const remove = async (sub: string) => {
    const prev = rows;
    setRows((r) => r.filter((m) => m.identitySub !== sub));
    setError("");
    try {
      await api.removeMember(slug, sub);
      onChanged();
    } catch (e) {
      setRows(prev);
      setError(e instanceof ApiError ? e.message : "Could not remove the member.");
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {error && <Notice kind="problem">{error}</Notice>}
      <div className="hidden sm:block">
        <Table>
          <THead>
            <TR>
              <TH>Member</TH>
              <TH>Role</TH>
              <TH>Joined</TH>
              <TH className="w-10" />
            </TR>
          </THead>
          <TBody>
            {rows.map((m) => (
              <TR key={m.identitySub}>
                <TD>
                  <span className="flex items-center gap-2">
                    <Avatar name={memberLabel(m, user)} />
                    <span className="truncate">{memberLabel(m, user)}</span>
                  </span>
                </TD>
                <TD>
                  <Badge variant="outline">{ROLE_LABELS[m.role]}</Badge>
                </TD>
                <TD className="tabular text-text-muted">
                  {m.joinedAt ? m.joinedAt.slice(0, 10) : "-"}
                </TD>
                <TD>
                  <RoleGate role={myRole} capability="manage_members">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          data-agent="member-actions"
                          className="rounded-input p-2 text-text-muted hover:bg-zone-9"
                          aria-label={`Actions for ${memberLabel(m, user)}`}
                        >
                          <MoreHorizontal className="size-4" aria-hidden />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Set role</DropdownMenuLabel>
                        {ROLES.map((r) => (
                          <DropdownMenuCheckItem
                            key={r}
                            checked={m.role === r}
                            onSelect={() => setRole(m.identitySub, r)}
                          >
                            {ROLE_LABELS[r]}
                          </DropdownMenuCheckItem>
                        ))}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem destructive onSelect={() => remove(m.identitySub)}>
                          Remove from project
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </RoleGate>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>
      <div className="flex flex-col gap-2 sm:hidden">
        {rows.map((m) => (
          <div key={m.identitySub} className="rounded-input border border-border bg-surface p-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 min-w-0">
                <Avatar name={memberLabel(m, user)} />
                <span className="truncate type-body">{memberLabel(m, user)}</span>
              </span>
              <RoleGate role={myRole} capability="manage_members">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      data-agent="member-actions"
                      className="rounded-input p-2 text-text-muted hover:bg-zone-9 min-h-11 min-w-11"
                      aria-label={`Actions for ${memberLabel(m, user)}`}
                    >
                      <MoreHorizontal className="size-4" aria-hidden />
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuLabel>Set role</DropdownMenuLabel>
                    {ROLES.map((r) => (
                      <DropdownMenuCheckItem
                        key={r}
                        checked={m.role === r}
                        onSelect={() => setRole(m.identitySub, r)}
                      >
                        {ROLE_LABELS[r]}
                      </DropdownMenuCheckItem>
                    ))}
                    <DropdownMenuSeparator />
                    <DropdownMenuItem destructive onSelect={() => remove(m.identitySub)}>
                      Remove from project
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </RoleGate>
            </div>
            <div className="mt-2 flex items-center gap-3 type-caption text-text-muted">
              <Badge variant="outline">{ROLE_LABELS[m.role]}</Badge>
              <span className="tabular">{m.joinedAt ? m.joinedAt.slice(0, 10) : "-"}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
