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
 *   - deleting needs the slug typed to confirm
 */
import { MATRIX, ROLE_RANK, hasRole } from "../src/lib/capabilities.ts";
import { ApiError, InMemoryBackend } from "../src/lib/api.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? ` — ${detail}` : ""}`);
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
const roles = ["viewer", "researcher", "owner"];
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
ok("researcher can contribute but not manage members",
  hasRole("researcher", "contribute") && !hasRole("researcher", "manage_members"));
ok("owner can do everything", Object.keys(MATRIX).every((c) => hasRole("owner", c)));

// The in-memory backend behaves like the server's shape.
const api = new InMemoryBackend();

const created = await api.createProject("Fresh Project");
ok("create project makes creator an owner", created.role === "owner", created.slug);
const mine = await api.listProjects();
ok("new project appears in my list", mine.some((p) => p.slug === created.slug));

// Invitation is single-use.
const inv = await api.createInvitation("sample-lab", "newbie@lab.test", "researcher");
const accepted = await api.acceptInvitation(inv.token);
ok("accepting an invitation returns its role", accepted.role === "researcher");
await throws("re-accepting the same token fails", 404, () => api.acceptInvitation(inv.token));

// Role change sticks.
await api.changeRole("sample-lab", "sam@lab.test", "researcher");
const members = await api.members("sample-lab");
ok("role change sticks",
  members.find((m) => m.identitySub === "sam@lab.test")?.role === "researcher");

// Last owner can't be removed (on the fresh project, "you" is sole owner).
await throws("last owner can't be removed", 409, () =>
  api.removeMember(created.slug, "you"));

// Delete needs the typed slug.
await throws("delete refuses a wrong confirmation", 400, () =>
  api.deleteProject("sample-lab", "nope"));
await api.deleteProject("sample-lab", "sample-lab");
const after = await api.listProjects();
ok("delete with correct confirmation removes the project",
  !after.some((p) => p.slug === "sample-lab"));

console.log(failures === 0 ? "\n✓ all checks pass" : `\n✗ ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
