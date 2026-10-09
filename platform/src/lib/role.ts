import type { Role } from "./capabilities.ts";

/* Keep a loading identity distinct from a known project role. */

export type RoleState =
  | { status: "loading" }
  | { status: "known"; role: Role | null };

export interface RoleInputs {
  /** The project payload's member list, when it has loaded. */
  projectMembers?: { identitySub: string; role: Role }[] | null;
  /** My identity's sub, when the session has loaded. */
  meSub?: string | null;
  /** My memberships from the session, when it has loaded. */
  memberships?: { projectSlug: string; role: Role }[] | null;
  /** Whether the session request is still in flight. */
  meLoading: boolean;
  slug: string;
}

/** My role in `slug`, or that it isn't known yet.
 *
 * Precedence is freshest-first: the project payload carries the *server's*
 * current answer for this project, while the session's memberships can be a
 * session old  -  stale for a project joined or created moments ago.
 */
export function resolveRole(input: RoleInputs): RoleState {
  const { projectMembers, meSub, memberships, meLoading, slug } = input;

  if (projectMembers && meSub) {
    const mine = projectMembers.find((m) => m.identitySub === meSub);
    if (mine) return { status: "known", role: mine.role };
  }

  const membership = memberships?.find((m) => m.projectSlug === slug);
  if (membership) return { status: "known", role: membership.role };

  // Nothing found  -  but absence only means something once both sources have
  // actually arrived. Until then the honest answer is "I don't know".
  if (meLoading || !memberships || !projectMembers) return { status: "loading" };

  return { status: "known", role: null };
}

/** The role to hand a `RoleGate`, treating "still loading" as no role  -  the
 * gate's `pending` flag is what keeps the control from flickering. */
export function roleOrNull(state: RoleState): Role | null {
  return state.status === "known" ? state.role : null;
}

/** Whether a page may fire the compile call (a contribute-level POST) as it
 * opens, with no user action. Never while the role is unknown, never for a
 * viewer (the server would 403 it on every visit). A non-member is left to the
 * server: local dev mode has no accounts to check, and a real non-member never
 * reaches the study. */
export function compileOnOpenAllowed(state: RoleState): boolean {
  if (state.status === "loading") return false;
  return state.role !== "viewer";
}
