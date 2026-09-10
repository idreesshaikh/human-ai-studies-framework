/* Checks shell permissions, role resolution, and the HTTP client boundary. */
import { MATRIX, ROLE_RANK, hasRole } from "../src/lib/capabilities.ts";
import { ApiError, OfflineError, createApi, setTokenProvider, onUnauthorized } from "../src/lib/api.ts";
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

// A failed server write must never succeed in a temporary local backend.
const api = createApi();
const originalFetch = globalThis.fetch;
setTokenProvider(async () => "test-token");
try {
  let request;
  globalThis.fetch = async (url, init) => {
    request = { url, ...init };
    return Response.json({ slug: "saved-study", role: "owner" });
  };
  const created = await api.createProject("Saved study");
  ok("create returns the server response", created.slug === "saved-study");
  ok("create sends its payload and credential",
    request.url === "/projects" && request.method === "POST" &&
    JSON.parse(request.body).name === "Saved study" &&
    request.headers.Authorization === "Bearer test-token");

  globalThis.fetch = async () => { throw new TypeError("network unavailable"); };
  for (const [name, call] of [
    ["project creation", () => api.createProject("Unsaved")],
    ["invitations", () => api.createInvitation("lab", "member")],
    ["participant links", () => api.mintEnrollmentTokens("study", 1, "participant")],
    ["project listing", () => api.listProjects()],
  ]) {
    try {
      await call();
      ok(name + " fails when offline", false);
    } catch (error) {
      ok(name + " fails when offline", error instanceof OfflineError);
    }
  }

  globalThis.fetch = async () => new Response("<html>SPA</html>", {
    headers: { "content-type": "text/html" },
  });
  try {
    await api.createProject("Unsaved");
    ok("an HTML response cannot confirm a save", false);
  } catch (error) {
    ok("an HTML response cannot confirm a save", error instanceof OfflineError);
  }

  let unauthorized = false;
  const unsubscribe = onUnauthorized(() => { unauthorized = true; });
  globalThis.fetch = async () => Response.json(
    { detail: "Sign in required" }, { status: 401 },
  );
  await throws("authentication errors are preserved", 401, () => api.listProjects());
  ok("401 notifies the sign-in layer", unauthorized);
  unsubscribe();

  globalThis.fetch = async () => Response.json(
    { detail: "Study not found" }, { status: 404 },
  );
  await throws("real 404 responses are preserved", 404, () => api.projectHome("missing"));
} finally {
  globalThis.fetch = originalFetch;
}

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
