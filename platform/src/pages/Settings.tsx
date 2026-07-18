import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RoleGate } from "@/components/shell/RoleGate";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { ApiError } from "@/lib/api.ts";
import type { Role } from "@/lib/capabilities.ts";

/* Project settings: rename, and an owner-only danger zone whose delete
 * requires typing the slug to confirm. */
export function Settings() {
  const api = useApi();
  const { me, refresh } = useSession();
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const { data } = useAsync(() => api.projectHome(slug), [api, slug]);
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const mine = (me?.memberships.find((m) => m.projectSlug === slug)?.role ??
    "viewer") as Role;

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
      await refresh();
      navigate("/projects");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not delete.");
    }
  };

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
      <h1 className="font-display text-2xl text-text">Settings</h1>

      <RoleGate
        role={mine}
        capability="manage_members"
        fallback={<p className="text-sm text-text-muted">Only owners can change settings.</p>}
      >
        <Card>
          <CardContent className="flex flex-col gap-3 p-4">
            <Label htmlFor="rename">Project name</Label>
            <div className="flex gap-2">
              <Input
                id="rename"
                placeholder={data?.name ?? "Project name"}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <Button onClick={rename} disabled={!name.trim()}>
                Save
              </Button>
            </div>
            {msg && <p className="text-sm text-grounded">{msg}</p>}
          </CardContent>
        </Card>

        <RoleGate role={mine} capability="delete">
          <Card className="border-unsourced">
            <CardContent className="flex flex-col gap-3 p-4">
              <div>
                <h2 className="font-medium text-text">Danger zone</h2>
                <p className="text-sm text-text-muted">
                  Deleting a project removes its memberships and invitations.
                  Type <span className="font-mono">{slug}</span> to confirm.
                </p>
              </div>
              <div className="flex gap-2">
                <Input
                  placeholder={slug}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  aria-label="Type the project slug to confirm deletion"
                />
                <Button
                  variant="outline"
                  onClick={remove}
                  disabled={confirm !== slug}
                  className="border-unsourced text-unsourced"
                >
                  Delete project
                </Button>
              </div>
            </CardContent>
          </Card>
        </RoleGate>
      </RoleGate>

      {err && <p className="text-sm text-unsourced">{err}</p>}
    </div>
  );
}
