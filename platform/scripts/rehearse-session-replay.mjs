import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import assert from "node:assert/strict";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRehearsalProject, rehearsalUrl } from "./rehearsal-project.mjs";

const BASE = rehearsalUrl();
const browser = await chromium.launch({ headless: Boolean(process.env.CI) });
let rehearsal;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const name = `Synthetic replay rehearsal ${Date.now()}`;
  rehearsal = await createRehearsalProject(page.request, BASE, name);
  const { project, study } = rehearsal;
  const quick = await page.request.post(`${BASE}/studies/${study.id}/quick-protocol`, { data: {
    title: name, researchQuestions: ["Does assistance change completion time?"],
    design: "within-subjects", conditions: ["ai-assisted", "unassisted"],
    participantDescription: "Novice developers", plannedParticipants: 4,
    taskDescription: "Repair a Python bug", sessionMinutes: 45,
    measures: ["task completion time"], counterbalanced: true,
  } });
  assert.equal(quick.status(), 200, await quick.text());
  const compiled = await (await page.request.post(`${BASE}/studies/${study.id}/conversation/compile`, { data: {} })).json();
  const approved = await page.request.post(`${BASE}/studies/${study.id}/conversation/approve`, { data: { compilationId: compiled.compilationId, approvedBy: "Synthetic rehearsal" } });
  assert.equal(approved.status(), 200, await approved.text());
  const simulated = await page.request.post(`${BASE}/studies/${study.id}/simulate`, { data: { count: 1, seed: 17 } });
  assert.equal(simulated.status(), 200, await simulated.text());
  await page.goto(`${BASE}/p/${project.slug}/studies/${study.id}?tab=data`);
  const scope = page.getByRole("checkbox", { name: /synthetic/i });
  await scope.check();
  const sessions = page.getByRole("button").filter({ hasText: /P01/ });
  await sessions.first().click();
  await page.getByRole("button", { name: "Replay session", exact: true }).click();
  const replay = page.getByRole("region", { name: "Session replay" });
  await expect(replay.getByText(/Code diffs are disabled/)).toBeVisible();
  await expect(replay.getByRole("button", { name: "Previous event" })).toBeDisabled();
  const slider = replay.getByRole("slider", { name: "Replay position" });
  await slider.focus();
  await page.keyboard.press("ArrowRight");
  await expect(slider).toHaveValue("1");
  await replay.getByRole("button", { name: "Play replay" }).click();
  await expect(slider).not.toHaveValue("1");
  await replay.getByRole("button", { name: "Pause replay" }).click();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.screenshot({ path: join(tmpdir(), `phoenix-replay-${width}.png`), fullPage: true });
    assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), []);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  }
  await page.route("**/replay", route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic replay outage" }) }));
  await page.getByRole("button", { name: "Close replay", exact: true }).click();
  await page.getByRole("button", { name: "Replay session", exact: true }).click();
  await replay.getByRole("alert").filter({ hasText: "Synthetic replay outage" }).waitFor();
  await page.unroute("**/replay");
  await replay.getByRole("button", { name: "Retry replay" }).click();
  await expect(slider).toBeVisible();
  assert.deepEqual(errors, []);
  console.log("PASS: scoped capture -> deterministic replay -> keyboard seek -> playback/pause -> policy -> desktop/mobile accessibility -> outage/retry");
} finally {
  try { await rehearsal?.cleanup(); } finally { await browser.close(); }
}
