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
import type { Theme } from "@/lib/theme";
import type { ResearcherProfile } from "@/lib/api";

/* Project settings: rename, and an owner-only danger zone whose delete
 * requires typing the slug to confirm. Plus the signed-in identity's own
 * profile (FR-OPS-7) — theme + default assistant model, persisted
 * server-side so they follow the person across devices. */
export function Settings() {
  const api = useApi();
  const { me, refresh, updatePreferences } = useSession();
  const navigate = useNavigate();
  const { slug = "" } = useParams();
  const { data } = useAsync(() => api.projectHome(slug), [api, slug]);
  const models = useAsync(() => api.assistantModels(), [api]);
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  // The caller's role. Prefer the freshly-loaded project payload (its members
  // carry the real role) over the session's `me`, which can be stale for a
  // project created this session — a stale "viewer" would wrongly hide the
  // owner-only danger zone (the "delete doesn't work" symptom).
  const mine: Role =
    data?.members.find((m) => m.identitySub === me?.sub)?.role ??
    me?.memberships.find((m) => m.projectSlug === slug)?.role ??
    "viewer";

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
      await refresh();
      navigate("/home");
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not delete.");
    }
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
    <div className="mx-auto flex max-w-reading flex-col gap-8 p-8">
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
            <select
              id="theme"
              className="rounded-input border border-border-strong bg-surface px-2 py-1.5 text-sm text-text"
              value={prefs.theme ?? "system"}
              onChange={(e) =>
                void updatePreferences({ theme: e.target.value as Theme })
              }
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="researcher-profile">Your research experience</Label>
            <select
              id="researcher-profile"
              className="rounded-input border border-border-strong bg-surface px-2 py-1.5 text-sm text-text"
              value={prefs.researcherProfile ?? ""}
              onChange={(e) =>
                void updatePreferences({
                  researcherProfile:
                    (e.target.value || undefined) as ResearcherProfile | undefined,
                })
              }
            >
              <option value="">Not saying</option>
              <option value="student">Student — learning research methods</option>
              <option value="new-researcher">
                New researcher — first empirical studies here
              </option>
              <option value="experienced">
                Experienced researcher — I design studies regularly
              </option>
              <option value="industry">
                Industry — studying engineers inside a company
              </option>
            </select>
            <p className="text-xs text-text-muted">
              The design conversation adapts how it talks to you: how much it
              explains, how fast it moves, and which trade-offs it raises. What
              counts as a sound design never changes.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="model">Default assistant model</Label>
            <select
              id="model"
              className="rounded-input border border-border-strong bg-surface px-2 py-1.5 text-sm text-text"
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
            </select>
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

        <RoleGate role={mine} capability="delete">
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
