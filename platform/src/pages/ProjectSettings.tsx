import { useState } from "react";
import { Field } from "@/components/ui/field";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
import { NAME_MAX_LENGTH } from "@/lib/uiText";
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
  const { data, loading, error: loadError, reload } = useAsync(() => api.projectHome(slug), [api, slug]);

  const [name, setName] = useState<string | null>(null);
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const projectName = name ?? data?.name ?? "";

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
    if (busy || !projectName.trim()) return;
    setBusy(true);
    setErr("");
    setMsg("");
    try {
      await api.renameProject(slug, projectName.trim());
      setName(projectName.trim());
      setMsg("Project name saved.");
      reload();
      await refresh().catch(() => {});
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not rename.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (busy || confirm !== "DELETE") return;
    setBusy(true);
    setErr("");
    try {
      await api.deleteProject(slug, confirm);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not delete.");
      setBusy(false);
      return;
    }
    await refresh().catch(() => {});
    navigate("/home");
  };

  return (
    <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
      <h1 className="type-title text-text">Project settings</h1>

      {!data && loading && <p role="status" className="type-body text-text-muted">Loading project settings…</p>}
      {loadError && <Notice kind="problem">{loadError} <Button variant="subtle" size="sm" onClick={reload}>Try again</Button></Notice>}

      <RoleGate
        role={mine}
        capability="manage_members"
        pending={rolePending || !data}
        fallback={<p className="type-body text-text-muted">Only owners can change settings.</p>}
      >
        <Card>
          <CardContent className="flex flex-col gap-3 p-4">
            <form onSubmit={(event) => { event.preventDefault(); void rename(); }} className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <Field id="rename" label="Project name" className="flex-1">
                <Input
                  value={projectName}
                  onChange={(e) => { setName(e.target.value); setMsg(""); }}
                  disabled={busy}
                  maxLength={NAME_MAX_LENGTH}
                />
              </Field>
              <Button type="submit" size="field" disabled={busy || loading || !projectName.trim() || projectName.trim() === data?.name}>
                {busy ? "Saving…" : "Save"}
              </Button>
            </form>
            <p className="type-note text-text-muted">
              The URL (<span className="type-quantity identifier">/{data?.slug}</span>) stays the
              same so existing links keep working. Only the display name changes.
            </p>
            {msg && <Notice kind="note" role="status">{msg}</Notice>}
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
                  disabled={busy}
                  aria-label="Type DELETE to confirm deletion"
                />
                <Button
                  variant="danger"
                  size="field"
                  onClick={remove}
                  disabled={busy || confirm !== "DELETE"}
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
