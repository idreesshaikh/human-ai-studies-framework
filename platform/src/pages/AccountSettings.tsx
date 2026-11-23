import { useSyncExternalStore } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { useSession } from "@/lib/session";
import { getTheme, subscribeTheme, type Theme } from "@/lib/theme";

/* Account settings: preferences persisted server-side so they follow the
 * person across devices, rather than living in one browser's storage. */
export function AccountSettings() {
  const { setThemePreference } = useSession();
  // The applied theme, not the saved preference: they differ when a theme was
  // applied without a save (sign-in toggle, failed save) or before /me loads.
  const theme = useSyncExternalStore(subscribeTheme, getTheme, getTheme);

  return (
    <div className="mx-auto flex max-w-reading flex-col gap-section p-gutter">
      <div>
        <h1 className="type-title text-text">Account settings</h1>
        <p className="type-body mt-1 max-w-reading text-text-muted">
          Your preferences apply to your account.
        </p>
      </div>

      <Card>
        <CardContent className="flex flex-col gap-4 p-4">
          <h2 className="type-subhead text-text">Appearance</h2>
          <Field id="theme" label="Theme">
            <Select
              value={theme}
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
