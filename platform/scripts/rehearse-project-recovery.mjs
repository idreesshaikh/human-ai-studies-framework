import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import assert from "node:assert/strict";
import { rehearsalUrl } from "./rehearsal-project.mjs";

const base = rehearsalUrl();
const browser = await chromium.launch({ headless: Boolean(process.env.CI) });
const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
const page = await context.newPage();
const projectName = `Synthetic project recovery ${Date.now()}`;
const question = "Compare debugging with and without assistance.";
let project;
let projectRequests = 0;
page.on("request", request => {
  if (request.url() === `${base}/projects` && request.method() === "POST") projectRequests++;
});
try {
  await page.goto(`${base}/home?new=1`);
  const name = page.getByLabel("Name the project", { exact: true });
  const brief = page.getByLabel("What do you want to run?", { exact: true });
  await name.fill(projectName);
  await brief.fill(question);
  await page.route("**/projects/*/studies", route => route.request().method() === "POST"
    ? route.fulfill({ status: 503, json: { detail: "Synthetic study creation outage" } })
    : route.continue());
  const saved = page.waitForResponse(response => response.url() === `${base}/projects` && response.request().method() === "POST");
  await page.getByRole("button", { name: "Create and start", exact: true }).click();
  project = await (await saved).json();
  assert.equal(project.name, projectName);
  assert.match(project.slug, /^synthetic-project-recovery-/);
  await expect(page.getByRole("alert")).toContainText("Synthetic study creation outage");
  await expect(name).toHaveValue(projectName);
  await expect(brief).toHaveValue(question);
  await expect(name).toHaveAttribute("readonly", "");
  assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), []);
  await page.unroute("**/projects/*/studies");
  await page.getByRole("button", { name: "Retry study creation", exact: true }).click();
  await page.waitForURL(`**/p/${project.slug}/studies/*`);
  await page.getByRole("heading", { name: "Study design chat" }).waitFor();
  assert.equal(projectRequests, 1, "Retry must reuse the saved project");
  const savedProject = await (await page.request.get(`${base}/projects/${project.slug}`)).json();
  assert.equal(savedProject.studies.length, 1);
  console.log("PASS: failed first-study creation preserves the name and brief, announces the error, and retries in the same project without duplicates.");
} finally {
  try {
    if (project) {
      assert.equal(project.name, projectName);
      assert.match(project.slug, /^synthetic-project-recovery-/);
      const deleted = await page.request.delete(`${base}/projects/${project.slug}`, { data: { confirm: "DELETE" } });
      assert.equal(deleted.status(), 200);
      await expect.poll(async () => (await page.request.get(`${base}/projects/${project.slug}`)).status()).toBe(404);
    }
  } finally { await browser.close(); }
}
