import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { RoleGate } from "@/components/shell/RoleGate";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { ApiError } from "@/lib/api.ts";
import { resolveRole, roleOrNull } from "@/lib/role";
import type { Theme } from "@/lib/theme";

/* Project settings: rename, and an owner-only danger zone whose delete
 * requires typing DELETE to confirm. Plus the signed-in identity's own
 * profile (FR-OPS-7) — theme + default assistant model, persisted
 * server-side so they follow the person across devices. */
export function Settings() {
  const api = useApi();
  const { me, loading: meLoading, refresh, updatePreferences, setThemePreference } =
    useSession();
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const { data } = useAsync(() => api.projectHome(slug), [api, slug]);
  const models = useAsync(() => api.assistantModels(), [api]);
  // The server's own `elicitation.PROFILES` is the source of truth — this
  // used to be four hardcoded options here that had already drifted from it
  // (e.g. "Industry" vs the server's "Industry practitioner"). Falls back to
  // the same catalogue offline rather than an empty select.
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  // My role here, with "not known yet" kept distinct from "viewer" — see
  // lib/role.ts. Defaulting to viewer while the session loaded is what made
  // the owner-only danger zone flicker in and out.
  const roleState = resolveRole({
    projectMembers: data?.members,
    meSub: me?.sub,
    memberships: me?.memberships,
    meLoading,
    slug,
  });
  const mine = roleOrNull(roleState);
  const rolePending = roleState.status === "loading";

  const prefs = me?.preferences ?? {};
  const modelOptions = models.data?.models ?? [];

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
    // The project is gone. Refreshing the session is housekeeping after the
    // fact — if it fails, that must not be reported as a failed delete, which
    // is what happened while this sat inside the try above.
    await refresh().catch(() => {});
    navigate("/home");
  };

  const saveModel = async (value: string) => {
    setErr("");
    try {
      await updatePreferences({ defaultAssistantModel: value || undefined });
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not save preference.");
    }
  };

  return (
    <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
      <h1 className="type-title text-text">Settings</h1>

      <Card>
        <CardContent className="flex flex-col gap-4 p-4">
          <div>
            <h2 className="type-subhead text-text">Your profile</h2>
            <p className="type-body text-text-muted">
              Preferences are saved to your account and follow you across devices.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label>Theme</Label>
            <Select
              value={prefs.theme ?? "light"}
              onValueChange={(v) => void setThemePreference(v as Theme)}
              options={[
                { value: "light", label: "Light" },
                { value: "dark", label: "Dark" },
              ]}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label>Default assistant model</Label>
            <Select
              value={prefs.defaultAssistantModel ?? models.data?.defaultModel ?? ""}
              onValueChange={(v) => void saveModel(v)}
              options={[
                ...(modelOptions.length > 0
                  ? []
                  : [
                      {
                        value: "",
                        label: "Use deployment default",
                      },
                    ]),
                ...modelOptions.map((m) => ({ value: m, label: m })),
              ]}
              disabled={modelOptions.length === 0}
              placeholder="Select model…"
            />
            {modelOptions.length === 0 && (
              <p className="type-caption text-text-muted">
                No assistant models are configured on this deployment.
              </p>
            )}
          </div>
        </CardContent>
      </Card>

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
            {/* The slug is set once at creation and never follows a rename —
             * intentional, so bookmarks and shared invite links never break.
             * Called out here so that stays a design decision, not a bug
             * report. */}
            <p className="type-caption text-text-muted">
              The URL (<span className="type-quantity identifier">/{data?.slug}</span>) stays the
              same so existing links keep working. Only the display name changes.
            </p>
            {msg && <p className="type-caption text-text-muted">{msg}</p>}
          </CardContent>
        </Card>

        <RoleGate role={mine} capability="delete" pending={rolePending}>
          {/* Framed in critical, not in `--unsourced`. Unsourced is this
            * world's mark for "logged, your call, not wrong"; wearing it on a
            * destructive control said the opposite of what deleting a project
            * means, and spent a provenance signal on something that carries no
            * provenance. */}
          <Card className="border-critical/40">
            <CardContent className="flex flex-col gap-3 p-4">
              <div>
                {/* Named for what it does. "Danger zone" is borrowed copy that
                  * describes the box rather than the action inside it. */}
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
