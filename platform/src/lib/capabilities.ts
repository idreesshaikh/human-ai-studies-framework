

export type Role = "owner" | "member" | "viewer";

export type Capability =
  | "view"
  | "contribute"
  | "apply_draft"
  | "run_recipe"
  | "invite_member"
  | "manage_members"
  | "delete"
  | "mint_token"
  | "toggle_capture";

export const ROLE_RANK: Record<Role, number> = {
  viewer: 0,
  member: 1,
  owner: 2,
};

export const MATRIX: Record<Capability, Role> = {
  view: "viewer",
  contribute: "member",
  apply_draft: "member",
  run_recipe: "member",
  invite_member: "member",
  manage_members: "owner",
  delete: "owner",
  mint_token: "member",
  toggle_capture: "member",
};

export function hasRole(role: Role | null | undefined, capability: Capability): boolean {
  if (!role) return false;
  return ROLE_RANK[role] >= ROLE_RANK[MATRIX[capability]];
}

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Owner",
  member: "Member",
  viewer: "Viewer",
};
