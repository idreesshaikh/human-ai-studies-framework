import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RoleGate } from "@/components/shell/RoleGate";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { ApiError } from "@/lib/api.ts";
import { resolveRole, roleOrNull } from "@/lib/role";

export function ProjectSettings() {
  const api = useApi();
  const { me, loading: meLoading, refresh } = useSession();
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const { data } = useAsync(() => api.projectHome(slug), [api, slug]);

  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const roleState = resolveRole({
    projectMembers: data?.members,
    meSub: me?.sub,
    memberships: me?.memberships,
    meLoading,
    slug,
  });
  const mine = roleOrNull(roleState);
  const rolePending = roleState.status === "loading";

  const rename = async () => {
    setErr("");
    setMsg("");
    try {
      await api.renameProject(slug, name);
      setMsg("Renamed.");
      await refresh();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not rename.");
    }
  };

  const remove = async () => {
    setErr("");
    try {
      await api.deleteProject(slug, confirm);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not delete.");
      return;
    }

    await refresh().catch(() => {});
    navigate("/home");
  };

  return (
    <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
      <h1 className="type-title text-text">Project settings</h1>

      <RoleGate
        role={mine}
        capability="manage_members"
        pending={rolePending}
        fallback={<p className="type-body text-text-muted">Only owners can change settings.</p>}
      >
        <Card>
          <CardContent className="flex flex-col gap-3 p-4">
            <Label htmlFor="rename">Project name</Label>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <Input
                id="rename"
                placeholder={data?.name ?? "Project name"}
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="min-h-11"
              />
              <Button onClick={rename} disabled={!name.trim()} className="min-h-11">
                Save
              </Button>
            </div>

            <p className="type-caption text-text-muted">
              The URL (<span className="type-quantity identifier">/{data?.slug}</span>) stays the
              same so existing links keep working. Only the display name changes.
            </p>
            {msg && <p className="type-caption text-text-muted">{msg}</p>}
          </CardContent>
        </Card>

        <RoleGate role={mine} capability="delete" pending={rolePending}>

          <Card className="border-critical/40">
            <CardContent className="flex flex-col gap-3 p-4">
              <div>

                <h2 className="type-subhead text-text">Delete this project</h2>
                <p className="type-body text-text-muted">
                  This removes the project, its memberships and its
                  invitations. Studies inside it go too, and none of it can be
                  brought back. Type{" "}
                  <span className="type-quantity identifier">DELETE</span> to
                  confirm.
                </p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <Input
                  placeholder="DELETE"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  aria-label="Type DELETE to confirm deletion"
                  className="min-h-11"
                />
                <Button
                  variant="danger"
                  onClick={remove}
                  disabled={confirm !== "DELETE"}
                  className="min-h-11"
                >
                  Delete project
                </Button>
              </div>
            </CardContent>
          </Card>
        </RoleGate>
      </RoleGate>

      {err && <Notice kind="problem">{err}</Notice>}
    </div>
  );
}
