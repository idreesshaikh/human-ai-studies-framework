import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createRehearsalProject, rehearsalUrl } from "./rehearsal-project.mjs";

const base = rehearsalUrl();
const artifacts = process.env.REHEARSAL_ARTIFACTS || join(tmpdir(), "phoenix-workspace-review");
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ headless: Boolean(process.env.CI) });
let rehearsal;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  rehearsal = await createRehearsalProject(page.request, base, `Usability rehearsal ${Date.now()}`);
  const { project, study } = rehearsal;
  const route = `${base}/p/${project.slug}/studies/${study.id}`;
  const quick = await page.request.post(`${base}/studies/${study.id}/quick-protocol`, { data: {
    title: "Debugging with AI", researchQuestions: ["Does AI assistance change completion time?"],
    design: "within-subjects", conditions: ["ai-assisted", "unassisted"],
    participantDescription: "Novice Python developers", plannedParticipants: 12,
    taskDescription: "Fix a Python bug", sessionMinutes: 45,
    measures: ["task completion time"], counterbalanced: true,
  } });
  assert.equal(quick.status(), 200, await quick.text());
  const compiled = await quick.json();
  assert.equal((await page.request.post(`${base}/studies/${study.id}/conversation/approve`, { data: { compilationId: compiled.compilationId } })).status(), 200);

  // Faster calculations must not flash in front of a slower run overview.
  let release;
  const held = new Promise(resolve => { release = resolve; });
  await page.route("**/run-plan?**", async intercepted => { await held; await intercepted.continue(); });
  await page.goto(`${route}?tab=planning`);
  await page.getByRole("status", { name: "Loading study plan" }).waitFor();
  await expect(page.getByText("Sample size estimates", { exact: true })).not.toBeVisible();
  release();
  await page.getByLabel("Preview assignment for").waitFor();
  await page.unroute("**/run-plan?**");
  await page.getByText("Sample size estimates", { exact: true }).click();
  await expect(page.getByText("alpha (two-sided)", { exact: true })).toBeVisible();
  await page.getByText("Sample size estimates", { exact: true }).click();
  const select = page.getByLabel("Preview assignment for");
  await select.click();
  await page.getByRole("menuitem", { name: "Participant 2", exact: true }).click();
  await expect(page.getByRole("button", { name: "Refresh plan" })).toBeEnabled();
  await page.getByRole("button", { name: "Setup", exact: true }).click();
  await page.getByRole("button", { name: "Show protocol draft", exact: true }).click();
  await expect(page.getByRole("button", { name: "Hide protocol draft", exact: true })).toBeVisible();
  assert((await page.getByRole("complementary").boundingBox()).width > 300, "Expanded draft must have a readable width");
  await expect(page.getByRole("button", { name: "Apply protocol", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Review draft", exact: true }).filter({ visible: true })).toHaveCount(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "Review draft", exact: true })).toBeVisible();
  await page.screenshot({ path: join(artifacts, "setup-mobile-expanded-pref-390.png"), fullPage: true });
  assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), []);
  await page.getByRole("button", { name: "Review draft", exact: true }).click();
  await expect(page.getByRole("dialog", { name: "Prepare your protocol draft" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Hide protocol draft", exact: true }).click();
  await page.getByRole("button", { name: "Plan", exact: true }).click();
  await expect(select).toHaveText("Participant 2");
  await expect(page.getByRole("status", { name: "Loading study plan" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Refresh plan" })).toBeEnabled();

  for (const width of [1440, 390, 2048]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    for (const tab of ["Plan", "Setup"]) {
      await page.getByRole("button", { name: tab, exact: true }).click();
      if (tab === "Plan") await expect(page.getByRole("button", { name: "Refresh plan" })).toBeEnabled();
      else await page.getByRole("textbox", { name: "Message the design assistant" }).waitFor();
      await page.screenshot({ path: join(artifacts, `${tab.toLowerCase()}-${width}.png`), fullPage: true });
      assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.html) })), [], `${tab}/${width}`);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      if (tab === "Setup") {
        const composer = await page.locator("form").filter({ has: page.getByRole("textbox", { name: "Message the design assistant" }) }).boundingBox();
        assert(composer.height < 100, "The composer must not consume the conversation viewport");
      }
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("button", { name: "Show protocol draft", exact: true }).click();
  await page.screenshot({ path: join(artifacts, "setup-expanded-1440.png"), fullPage: true });
  assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), []);
  assert.deepEqual(errors, []);
  console.log(`PASS: stable Plan loading, retained assignment, labelled rail, one review action, compact composer, desktop/mobile/wide accessibility. ${artifacts}`);
} finally {
  try { await rehearsal?.cleanup(); } finally { await browser.close(); }
}
