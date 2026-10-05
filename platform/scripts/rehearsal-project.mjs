import assert from "node:assert/strict";

export function rehearsalUrl(env = process.env) {
  const url = new URL(env.REHEARSAL_URL || "http://invalid");
  assert(
    env.REHEARSAL_ISOLATED === "1" && url.protocol === "http:" &&
    ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname) &&
    !url.username && !url.password && url.pathname === "/" && !url.search && !url.hash,
    "Use REHEARSAL_ISOLATED=1 and REHEARSAL_URL=http://127.0.0.1:<port> only after starting a server with a separate synthetic database.",
  );
  return url.origin;
}

export async function createRehearsalProject(request, base, name, env = process.env) {
  assert.match(name, /^(Synthetic |Usability rehearsal )/, "Only synthetic rehearsal projects may be created or cleaned up");
  const response = await request.post(`${base}/projects`, { data: { name } });
  assert.equal(response.status(), 200, "Synthetic project creation failed");
  const project = await response.json();
  assert.equal(project.name, name);
  assert.match(project.slug, /^(synthetic-|usability-rehearsal-)[a-z0-9-]+$/);
  const cleanup = async () => {
    if (env.REHEARSAL_KEEP === "1") {
      console.log(`Retained synthetic project: ${base}/p/${project.slug}`);
      return;
    }
    const deleted = await request.delete(`${base}/projects/${project.slug}`, { data: { confirm: "DELETE" } });
    assert.equal(deleted.status(), 200, `Cleanup failed for synthetic project ${project.slug}`);
    assert.equal((await deleted.json()).deleted, project.slug);
    assert.equal((await request.get(`${base}/projects/${project.slug}`)).status(), 404);
    console.log(`Removed only this rehearsal's synthetic project: ${project.slug}`);
  };
  try {
    const created = await request.post(`${base}/projects/${project.slug}/studies`, { data: { name } });
    assert.equal(created.status(), 200, "Synthetic study creation failed");
    return { project, study: await created.json(), cleanup };
  } catch (error) {
    try { await cleanup(); } catch (cleanupError) {
      throw new AggregateError([error, cleanupError], "Study creation and cleanup failed");
    }
    throw error;
  }
}
