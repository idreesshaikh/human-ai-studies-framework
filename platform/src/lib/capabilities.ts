/* The permission matrix, mirrored from the server so the UI can reflect it.
 *
 * The server is the enforcement — this copy exists only so the shell can
 * show or hide controls a role can't use, and never as the security
 * boundary. Keep it in step with middleware/authz.py's CAPABILITIES; a
 * mismatch just means a button appears that the server then refuses (safe,
 * if untidy). */

export type Role = "owner" | "researcher" | "viewer";

export type Capability =
  | "view"
  | "contribute"
  | "apply_draft"
  | "run_recipe"
  | "freeze"
  | "manage_members"
  | "delete"
  | "mint_token";

export const ROLE_RANK: Record<Role, number> = {
  viewer: 0,
  researcher: 1,
  owner: 2,
};

/** The minimum role each capability needs. */
export const MATRIX: Record<Capability, Role> = {
  view: "viewer",
  contribute: "researcher",
  apply_draft: "researcher",
  run_recipe: "researcher",
  freeze: "owner",
  manage_members: "owner",
  delete: "owner",
  mint_token: "researcher",
};

/** True if `role` can exercise `capability`. A missing role (non-member)
 * satisfies nothing. */
export function hasRole(role: Role | null | undefined, capability: Capability): boolean {
  if (!role) return false;
  return ROLE_RANK[role] >= ROLE_RANK[MATRIX[capability]];
}

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Owner",
  researcher: "Researcher",
  viewer: "Viewer",
};
