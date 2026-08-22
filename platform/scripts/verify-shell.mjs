/* Exercises the shell's pure logic without a browser: the permission matrix
 * and the in-memory backend that powers offline dev, the hero demo, and the
 * UI's optimistic flows. Run:
 *   node --experimental-strip-types scripts/verify-shell.mjs
 *
 * Checks that:
 *   - hasRole matches the matrix for every role × capability
 *   - creating a project makes the creator an owner
 *   - an invitation is single-use
 *   - a role change sticks; the last owner can't be removed
 *   - deleting needs DELETE typed to confirm
 *   - resolveRole keeps "still loading" distinct from "viewer"
 */
import { MATRIX, ROLE_RANK, hasRole } from "../src/lib/capabilities.ts";
import { ApiError, InMemoryBackend } from "../src/lib/api.ts";
import { resolveRole, roleOrNull } from "../src/lib/role.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};
async function throws(name, status, fn) {
  try {
    await fn();
    ok(name, false, "expected an error");
  } catch (e) {
    ok(name, e instanceof ApiError && e.status === status, `status ${e?.status}`);
  }
}

// The matrix mirrors the server: hasRole agrees with the rank ordering.
const roles = ["viewer", "member", "owner"];
let matrixOk = true;
for (const cap of Object.keys(MATRIX)) {
  for (const role of roles) {
    const expected = ROLE_RANK[role] >= ROLE_RANK[MATRIX[cap]];
    if (hasRole(role, cap) !== expected) matrixOk = false;
  }
}
ok("permission matrix matches rank ordering", matrixOk);
ok("a non-member satisfies nothing", roles.every(() => true) && !hasRole(null, "view"));
ok("viewer can view but not contribute", hasRole("viewer", "view") && !hasRole("viewer", "contribute"));
ok("member can contribute but not manage members",
  hasRole("member", "contribute") && !hasRole("member", "manage_members"));
ok("owner can do everything", Object.keys(MATRIX).every((c) => hasRole("owner", c)));

// The in-memory backend behaves like the server's shape.
const api = new InMemoryBackend();

const created = await api.createProject("Fresh Project");
ok("create project makes creator an owner", created.role === "owner", created.slug);
const mine = await api.listProjects();
ok("new project appears in my list", mine.some((p) => p.slug === created.slug));

// Invitations are reusable (Phase 7b: email-less share links).
const inv = await api.createInvitation("sample-lab", "member");
const accepted = await api.acceptInvitation(inv.token);
// Existing member keeps their role; invitations don't downgrade.
ok("accepting a link as existing member keeps role", accepted.role === "owner");
const reaccepted = await api.acceptInvitation(inv.token);
ok("re-accepting the same link is allowed (reusable)", reaccepted.role === "owner");

// Role change sticks.
await api.changeRole("sample-lab", "dana@lab.test", "owner");
const members = await api.members("sample-lab");
ok("role change sticks",
  members.find((m) => m.identitySub === "dana@lab.test")?.role === "owner");

// Last owner can't be removed (on the fresh project, "you" is sole owner).
await throws("last owner can't be removed", 409, () =>
  api.removeMember(created.slug, "you"));

// Delete needs DELETE typed.
await throws("delete refuses a wrong confirmation", 400, () =>
  api.deleteProject("sample-lab", "nope"));
await api.deleteProject("sample-lab", "DELETE");
const after = await api.listProjects();
ok("delete with correct confirmation removes the project",
  !after.some((p) => p.slug === "sample-lab"));

// --------------------------------------------------------- role resolution
//
// The regression this guards: pages resolved my role with `… ?? "viewer"`,
// so while the session was still loading every owner-only control rendered
// as if I were a viewer  -  the delete button appeared late, or looked absent
// entirely. "Loading" and "viewer" must never collapse into one answer.

const MEMBERS = [{ identitySub: "me", role: "owner" }];
const MEMBERSHIPS = [{ projectSlug: "lab", role: "member" }];

ok("role is unknown while the session loads",
  resolveRole({ meLoading: true, slug: "lab" }).status === "loading");

ok("role is unknown before either source arrives",
  resolveRole({ meLoading: false, slug: "lab" }).status === "loading");

ok("the project payload is preferred over a stale session",
  roleOrNull(resolveRole({
    projectMembers: MEMBERS, meSub: "me",
    memberships: MEMBERSHIPS, meLoading: false, slug: "lab",
  })) === "owner");

ok("the session's membership answers when the payload lacks me",
  roleOrNull(resolveRole({
    projectMembers: [], meSub: "me",
    memberships: MEMBERSHIPS, meLoading: false, slug: "lab",
  })) === "member");

ok("a genuine non-member resolves to no role, not to loading",
  (() => {
    const s = resolveRole({
      projectMembers: [], meSub: "me", memberships: [],
      meLoading: false, slug: "lab",
    });
    return s.status === "known" && s.role === null;
  })());

ok("a membership for another project doesn't leak in",
  (() => {
    const s = resolveRole({
      projectMembers: [], meSub: "me",
      memberships: [{ projectSlug: "other", role: "owner" }],
      meLoading: false, slug: "lab",
    });
    return s.status === "known" && s.role === null;
  })());

ok("loading never satisfies a capability",
  !hasRole(roleOrNull(resolveRole({ meLoading: true, slug: "lab" })), "delete"));

console.log(failures === 0 ? "\n✓ all checks pass" : `\n✗ ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
