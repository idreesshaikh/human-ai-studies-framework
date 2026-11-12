/* The role and UI capability subset used to show or hide controls. The server
 * remains the authorization boundary. */

export type Role = "owner" | "member" | "viewer";

export type Capability =
  | "view"
  | "contribute"
  | "apply_draft"
  | "run_recipe"
  | "delete"
  | "mint_token"
  | "toggle_capture";

export const ROLE_RANK: Record<Role, number> = {
  viewer: 0,
  member: 1,
  owner: 2,
};

/** The minimum role each capability needs. */
export const MATRIX: Record<Capability, Role> = {
  view: "viewer",
  contribute: "member",
  apply_draft: "member",
  run_recipe: "member",
  delete: "owner",
  mint_token: "member",
  toggle_capture: "member",
};

/** True if `role` can exercise `capability`. Missing access satisfies nothing. */
export function hasRole(role: Role | null | undefined, capability: Capability): boolean {
  if (!role) return false;
  return ROLE_RANK[role] >= ROLE_RANK[MATRIX[capability]];
}
