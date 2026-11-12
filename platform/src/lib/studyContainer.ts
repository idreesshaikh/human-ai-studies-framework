import { hasRole } from "./capabilities.ts";
import type { Api, Me } from "./api.ts";

/** Find the researcher's existing study container or create the private one. */
export async function studyContainer(
  api: Api,
  me: Me | null,
  refresh: () => Promise<void>,
): Promise<string> {
  const membership = me?.memberships.find((item) =>
    hasRole(item.role, "contribute"),
  );
  if (membership) return membership.projectSlug;

  const container = await api.ensurePersonalContainer();
  await refresh();
  return container.slug;
}
