import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { RoleGate } from "@/components/shell/RoleGate";
import { useApi, useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { ApiError } from "@/lib/api.ts";
import { resolveRole, roleOrNull } from "@/lib/role";
import type { Theme } from "@/lib/theme";
import { FALLBACK_RESEARCHER_PROFILES, type ResearcherProfile } from "@/lib/api";

/* Project settings: rename, and an owner-only danger zone whose delete
 * requires typing the slug to confirm. Plus the signed-in identity's own
 * profile (FR-OPS-7) — theme + default assistant model, persisted
 * server-side so they follow the person across devices. */
export function Settings() {
  const api = useApi();
  const { me, loading: meLoading, refresh, updatePreferences } = useSession();
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const { data } = useAsync(() => api.projectHome(slug), [api, slug]);
  const models = useAsync(() => api.assistantModels(), [api]);
  // The server's own `elicitation.PROFILES` is the source of truth — this
  // used to be four hardcoded options here that had already drifted from it
  // (e.g. "Industry" vs the server's "Industry practitioner"). Falls back to
  // the same catalogue offline rather than an empty select.
  const researcherProfiles = useAsync(() => api.researcherProfiles(), [api]);
  const profileOptions = researcherProfiles.data?.profiles ?? FALLBACK_RESEARCHER_PROFILES;
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
            <p className="text-sm text-text-muted">
              Preferences are saved to your account and follow you across devices.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="theme">Theme</Label>
            <Select
              id="theme"
              value={prefs.theme ?? "system"}
              onChange={(e) =>
                void updatePreferences({ theme: e.target.value as Theme })
              }
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </Select>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="researcher-profile">Your research experience</Label>
            <Select
              id="researcher-profile"
              value={prefs.researcherProfile ?? ""}
              onChange={(e) =>
                void updatePreferences({
                  researcherProfile:
                    (e.target.value || undefined) as ResearcherProfile | undefined,
                })
              }
            >
              <option value="">Not saying</option>
              {profileOptions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}: {p.description}
                </option>
              ))}
            </Select>
            <p className="text-xs text-text-muted">
              The design conversation adapts how it talks to you: how much it
              explains, how fast it moves, and which trade-offs it raises. What
              counts as a sound design never changes.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="model">Default assistant model</Label>
            <Select
              id="model"
              value={prefs.defaultAssistantModel ?? models.data?.defaultModel ?? ""}
              onChange={(e) => void saveModel(e.target.value)}
              disabled={modelOptions.length === 0}
            >
              {!prefs.defaultAssistantModel && (
                <option value="">Use deployment default</option>
              )}
              {modelOptions.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
            {modelOptions.length === 0 && (
              <p className="text-xs text-text-muted">
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
        fallback={<p className="text-sm text-text-muted">Only owners can change settings.</p>}
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
            {msg && <p className="text-sm text-grounded">{msg}</p>}
          </CardContent>
        </Card>

        <RoleGate role={mine} capability="delete" pending={rolePending}>
          <Card className="border-unsourced">
            <CardContent className="flex flex-col gap-3 p-4">
              <div>
                <h2 className="type-subhead text-text">Danger zone</h2>
                <p className="text-sm text-text-muted">
                  Deleting a project removes its memberships and invitations.
                  Type <span className="font-mono">{slug}</span> to confirm.
                </p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                <Input
                  placeholder={slug}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  aria-label="Type the project slug to confirm deletion"
                  className="min-h-11"
                />
                <Button
                  variant="outline"
                  onClick={remove}
                  disabled={confirm !== slug}
                  className="border-unsourced text-unsourced min-h-11"
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
