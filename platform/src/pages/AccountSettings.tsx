import { Card, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useSession } from "@/lib/session";
import { useAsync } from "@/lib/useAsync";
import { useApi } from "@/lib/session";
import { ApiError } from "@/lib/api";
import type { Theme } from "@/lib/theme";
import { useState } from "react";

/* Account settings: theme and default assistant model preferences,
 * persisted server-side so they follow the person across devices. */
export function AccountSettings() {
  const api = useApi();
  const { me, setThemePreference, updatePreferences } = useSession();
  const models = useAsync(() => api.assistantModels(), [api]);
  const [err, setErr] = useState("");

  const prefs = me?.preferences ?? {};
  const modelOptions = models.data?.models ?? [];

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
      <h1 className="type-title text-text">Account settings</h1>

      <Card>
        <CardContent className="flex flex-col gap-4 p-4">
          <div>
            <h2 className="type-subhead text-text">Your preferences</h2>
            <p className="type-body text-text-muted">
              Settings are saved to your account and follow you across devices.
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
          {err && <p className="type-caption text-critical">{err}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
