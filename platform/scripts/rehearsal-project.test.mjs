import assert from "node:assert/strict";
import { test } from "node:test";
import { createRehearsalProject, rehearsalUrl } from "./rehearsal-project.mjs";

test("rehearsals require an explicit isolated loopback server", () => {
  for (const env of [{}, { REHEARSAL_URL: "http://localhost:8011" }, { REHEARSAL_ISOLATED: "1", REHEARSAL_URL: "https://example.org" }]) {
    assert.throws(() => rehearsalUrl(env));
  }
  assert.equal(rehearsalUrl({ REHEARSAL_ISOLATED: "1", REHEARSAL_URL: "http://127.0.0.1:8011" }), "http://127.0.0.1:8011");
});

for (const failStudy of [false, true]) {
  test(`cleanup targets only the newly created project (study failure: ${failStudy})`, async () => {
    const calls = [];
    const reply = (status, body) => ({ status: () => status, json: async () => body });
    const request = {
      post: async url => url.endsWith("/projects") ? reply(200, { slug: "synthetic-new", name: "Synthetic new" }) : reply(failStudy ? 503 : 200, { id: "new-study" }),
      delete: async (url, options) => { calls.push([url, options]); return reply(200, { deleted: "synthetic-new" }); },
      get: async () => reply(404, {}),
    };
    if (failStudy) await assert.rejects(createRehearsalProject(request, "http://localhost:8011", "Synthetic new", {}));
    else await (await createRehearsalProject(request, "http://localhost:8011", "Synthetic new", {})).cleanup();
    assert.deepEqual(calls, [["http://localhost:8011/projects/synthetic-new", { data: { confirm: "DELETE" } }]]);
  });
}

test("explicit keep preserves a synthetic presentation fixture", async () => {
  const request = {
    post: async url => ({ status: () => 200, json: async () => url.endsWith("/projects") ? { slug: "synthetic-new", name: "Synthetic new" } : { id: "new-study" } }),
    delete: async () => assert.fail("Kept fixtures must not be deleted"),
  };
  await (await createRehearsalProject(request, "http://localhost:8011", "Synthetic new", { REHEARSAL_KEEP: "1" })).cleanup();
});

test("personal projects cannot enter the cleanup workflow", async () => {
  await assert.rejects(createRehearsalProject({ post: () => assert.fail("Must not call API") }, "http://localhost:8011", "Personal", {}));
});
