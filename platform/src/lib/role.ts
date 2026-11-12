import type { Role } from "./capabilities.ts";

/* Keep a loading identity distinct from a known study role. */

export type RoleState =
  | { status: "loading" }
  | { status: "known"; role: Role | null };

/** Read the resolved access role; loading stays distinct until the server
 * answers so controls do not flicker into view. */
export function roleOrNull(state: RoleState): Role | null {
  return state.status === "known" ? state.role : null;
}

/** Whether a page may fire the compile call (a contribute-level POST) as it
 * opens, with no user action. Never while access is unknown or for a viewer;
 * the server remains the final authorization check. */
export function compileOnOpenAllowed(state: RoleState): boolean {
  if (state.status === "loading") return false;
  return state.role !== "viewer";
}
