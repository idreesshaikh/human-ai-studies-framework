import { Card, CardContent } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { useSession } from "@/lib/session";
import type { Theme } from "@/lib/theme";

/* Account settings: preferences persisted server-side so they follow the
 * person across devices, rather than living in one browser's storage. */
export function AccountSettings() {
  const { me, setThemePreference } = useSession();

  const prefs = me?.preferences ?? {};

  return (
    <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
      <div>
        <h1 className="type-title text-text">Account settings</h1>
        <p className="type-body mt-1 max-w-reading text-text-muted">
          Manage your preferences across all projects.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 p-4">
          <div>
            <h2 className="type-subhead text-text">Display</h2>
            <p className="type-caption text-text-muted">
              These settings apply to all your projects.
            </p>
          </div>
          <Field id="theme" label="Theme">
            <Select
              value={prefs.theme ?? "light"}
              onValueChange={(v) => void setThemePreference(v as Theme)}
              options={[
                { value: "light", label: "Light" },
                { value: "dark", label: "Dark" },
              ]}
            />
          </Field>
        </CardContent>
      </Card>
    </div>
  );
}
