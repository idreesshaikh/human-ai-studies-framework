import type { Role } from "./capabilities.ts";

export type RoleState =
  | { status: "loading" }
  | { status: "known"; role: Role | null };

export interface RoleInputs {

  projectMembers?: { identitySub: string; role: Role }[] | null;

  meSub?: string | null;

  memberships?: { projectSlug: string; role: Role }[] | null;

  meLoading: boolean;
  slug: string;
}

export function resolveRole(input: RoleInputs): RoleState {
  const { projectMembers, meSub, memberships, meLoading, slug } = input;

  if (projectMembers && meSub) {
    const mine = projectMembers.find((m) => m.identitySub === meSub);
    if (mine) return { status: "known", role: mine.role };
  }

  const membership = memberships?.find((m) => m.projectSlug === slug);
  if (membership) return { status: "known", role: membership.role };

  if (meLoading || !memberships || !projectMembers) return { status: "loading" };

  return { status: "known", role: null };
}

export function roleOrNull(state: RoleState): Role | null {
  return state.status === "known" ? state.role : null;
}
