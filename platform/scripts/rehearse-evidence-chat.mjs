import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRehearsalProject, rehearsalUrl } from "./rehearsal-project.mjs";

const BASE = rehearsalUrl();
const fixturePath = new URL("../../protocol/examples/evidence-workflow-demo.json", import.meta.url);
const fixture = JSON.parse(await readFile(fixturePath, "utf8"));
const browser = await chromium.launch({ headless: Boolean(process.env.CI) });
let rehearsal;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const name = `Synthetic evidence rehearsal ${Date.now()}`;
  rehearsal = await createRehearsalProject(page.request, BASE, name);
  const { project, study } = rehearsal;
  const route = `${BASE}/p/${project.slug}/studies/${study.id}`;
  await page.goto(route);
  await page.getByRole("heading", { name: "What would you like to study?" }).waitFor();
  const composer = page.getByRole("textbox", { name: "Message the design assistant" });
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Add known details", exact: true })).not.toBeVisible();
  await page.getByRole("button", { name: "Research tools", exact: true }).click();
  await expect(page.getByRole("menuitem", { name: "Show details", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.screenshot({ path: join(tmpdir(), `phoenix-chat-${width}.png`), fullPage: true });
    assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), []);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.getByRole("button", { name: /^Steer mode:/ }).click();
    await expect(page.getByRole("dialog", { name: "Choose steer mode" })).toBeVisible();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Choose steer mode" })).toHaveCount(0);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await composer.fill("First line");
  await composer.press("Shift+Enter");
  await composer.pressSequentially("Second line");
  await expect(composer).toHaveValue("First line\nSecond line");
  await composer.fill("");
  await page.getByText("Examples and study tools", { exact: true }).click();
  await page.getByText("Try an example", { exact: true }).click();
  await page.getByRole("button", { name: "Compare how long debugging takes with and without an AI pair." }).click();
  await expect(composer).toHaveValue("Compare how long debugging takes with and without an AI pair.");
  await composer.fill("");
  // Offline model responses must preserve the user's message, with a manual recovery.
  const outage = route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic model outage. Enter the details manually." }) });
  await page.route("**/conversation/turns/stream", outage);
  await page.route("**/conversation/turns", outage);
  await composer.fill("Does assistance change completion time?");
  await composer.press("Enter");
  await expect(page.getByText("Does assistance change completion time?", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Enter details manually", exact: true }).waitFor();
  await page.unroute("**/conversation/turns/stream");
  await page.unroute("**/conversation/turns");

  // Import through the UI, including invalid-file recovery.
  await page.getByRole("button", { name: "Research tools", exact: true }).click();
  await page.getByRole("menuitem", { name: "Method evidence", exact: true }).click();
  await page.getByLabel("Import an evidence map (JSON)").setInputFiles({ name: "invalid.json", mimeType: "application/json", buffer: Buffer.from("{}") });
  await page.getByRole("alert").filter({ hasText: "Invalid evidence map" }).waitFor();
  await page.getByLabel("Import an evidence map (JSON)").setInputFiles({ name: "synthetic-map.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(fixture)) });
  await page.getByText("DEMONSTRATION ONLY.", { exact: false }).waitFor();
  const population = page.getByLabel("Population", { exact: true });
  await expect(population).toHaveAttribute("list", "evidence-population-options");
  await expect(page.locator("#evidence-population-options option")).toHaveCount(1);
  await expect(page.locator("#evidence-population-options option")).toHaveAttribute("value", "Novice Python developers");
  for (const [label, value] of [
    ["Research question", "Does AI assistance change completion time?"],
    ["Population", "Novice Python developers"], ["Task", "Fix a Python bug"],
    ["Construct", "completion-time"], ["Available producers (comma-separated)", "task-harness"],
    ["Available instruments (comma-separated)", "task-harness"],
  ]) await page.getByLabel(label, { exact: true }).fill(value);
  await page.getByRole("button", { name: "Compare methods", exact: true }).click();
  const alternatives = page.getByRole("list", { name: "Method alternatives" });
  await expect(alternatives.getByText("More evidence needed", { exact: true })).toHaveCount(2);
  const between = alternatives.locator("li").filter({ has: page.getByRole("heading", { name: "between-subjects", exact: true }) });
  if (!await between.getByRole("checkbox").isVisible()) await between.getByText("Sources, limits and capture requirements", { exact: true }).click();
  await expect(between.getByText("Invented fixture paragraph 1", { exact: false })).toBeVisible();
  await expect(between.getByText("Recommendation · conditional applicability", { exact: true })).toBeVisible();
  await expect(between.getByText("Evidence quality: unknown", { exact: false })).toBeVisible();
  await expect(between.getByText("Simulates a reviewed row", { exact: false })).toBeVisible();
  let releaseComparison;
  let comparisonStarted;
  const comparisonHeld = new Promise(resolve => { releaseComparison = resolve; });
  const comparisonRequest = new Promise(resolve => { comparisonStarted = resolve; });
  await page.route("**/evidence-map/candidates", async intercepted => {
    comparisonStarted();
    await comparisonHeld;
    await intercepted.continue();
  });
  await between.getByRole("checkbox").focus();
  await page.keyboard.press("Space");
  await comparisonRequest;
  await expect(between.getByRole("checkbox")).toBeFocused();
  await expect(between.getByRole("button", { name: "Review this choice in chat" })).toBeDisabled();
  releaseComparison();
  await expect(between.getByText("Conditional", { exact: true })).toBeVisible();
  await expect(between.getByRole("checkbox")).toBeFocused();
  await page.unroute("**/evidence-map/candidates");

  // A changed constraint invalidates the old results and prevents proposing.
  await page.getByLabel("Available producers (comma-separated)").fill("metrics");
  await expect(alternatives).toHaveCount(0);
  await page.getByRole("button", { name: "Compare methods", exact: true }).click();
  await expect(alternatives.getByText("Incompatible", { exact: true })).toHaveCount(2);
  await expect(between.getByRole("button", { name: "Review this choice in chat" })).toBeDisabled();
  await page.getByLabel("Available producers (comma-separated)").fill("task-harness");
  // Verify a comparison outage has an explicit retry, with no stale success.
  await page.route("**/evidence-map/candidates", route => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic comparison outage" }) }));
  await page.getByRole("button", { name: "Compare methods", exact: true }).click();
  await page.getByRole("alert").filter({ hasText: "Synthetic comparison outage" }).waitFor();
  await expect(alternatives).toHaveCount(0);
  await page.unroute("**/evidence-map/candidates");
  await page.getByRole("button", { name: "Retry comparison", exact: true }).click();
  await expect(alternatives.getByText("More evidence needed", { exact: true })).toHaveCount(2);
  if (!await between.getByRole("checkbox").isVisible()) await between.getByText("Sources, limits and capture requirements", { exact: true }).click();
  await between.getByRole("checkbox").check();
  await expect(between.getByText("Conditional", { exact: true })).toBeVisible();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
    await page.screenshot({ path: join(tmpdir(), `phoenix-evidence-${width}.png`), fullPage: true });
    assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), []);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  }
  // A verified manual base lets the evidence choice use the real compiler.
  const quick = await page.request.post(`${BASE}/studies/${study.id}/quick-protocol`, { data: {
    title: name, researchQuestions: ["Does AI assistance change completion time?"],
    design: "within-subjects", conditions: ["ai-assisted", "unassisted"],
    participantDescription: "Novice Python developers", plannedParticipants: 12,
    taskDescription: "Fix a Python bug", sessionMinutes: 45,
    measures: ["task completion time"], counterbalanced: true,
  } });
  assert.equal(quick.status(), 200, await quick.text());
  await between.getByRole("button", { name: "Review this choice in chat" }).click();
  const move = page.locator("[data-move-id]").filter({
    has: page.getByText("Use a between-subjects design.", { exact: true }),
  });
  await expect(move).toBeVisible();
  await expect(move).toBeFocused();
  await move.getByText("Evidence and conditions", { exact: false }).click();
  await expect(move.getByText("DEMONSTRATION ONLY.", { exact: false })).toBeVisible();
  await move.focus();
  for (const key of ["Control+a", "Meta+a", "Alt+r"]) {
    await page.keyboard.press(key);
    await expect(move.getByRole("button", { name: "Accept", exact: true })).toBeVisible();
  }
  await move.getByRole("button", { name: "Reject", exact: true }).focus();
  await page.keyboard.press("a");
  await expect(move.getByRole("button", { name: "Accept", exact: true })).toBeVisible();
  await move.focus();
  await page.keyboard.press("a");
  await page.getByText("Decisions (1)", { exact: true }).click();
  await expect(move.getByText("Accepted", { exact: true })).toBeVisible();
  let releaseCompile;
  let compileStarted;
  const compileHeld = new Promise(resolve => { releaseCompile = resolve; });
  const compileRequest = new Promise(resolve => { compileStarted = resolve; });
  await page.route("**/conversation/compile", async intercepted => {
    compileStarted();
    await compileHeld;
    await intercepted.continue();
  });
  await page.getByRole("button", { name: "Review draft", exact: true }).click();
  await compileRequest;
  await expect(page.getByRole("button", { name: "Apply protocol", exact: true })).toBeDisabled();
  releaseCompile();
  await expect(page.getByRole("button", { name: "Apply protocol", exact: true })).toBeEnabled();
  await page.unroute("**/conversation/compile");
  const approved = page.waitForResponse(response => response.url().endsWith("/conversation/approve"));
  await page.getByRole("button", { name: "Apply protocol", exact: true }).click();
  const approvalResponse = await approved;
  assert.equal(approvalResponse.status(), 200, await approvalResponse.text());
  const record = await (await page.request.get(`${BASE}/studies/${study.id}/conversation/export`)).json();
  const evidenceMove = record.turns.flatMap(t => t.moves).find(m => m.grounding.some(g => g.evidence));
  assert.equal(evidenceMove.status, "accepted");
  assert.equal(evidenceMove.grounding[0].evidence.candidate.designFamily, "between-subjects");
  assert.equal(record.approvals.length, 1);
  const protocol = await (await page.request.get(`${BASE}/studies/${study.id}/protocol`)).json();
  assert.equal(protocol.document.participants.design, "between-subjects");
  assert.deepEqual(protocol.document.analysisPlan[0].recipes, ["two-group-nonparametric"]);
  assert.deepEqual(errors, []);
  console.log(`PASS: chat, import, sources, constraints, outage recovery, keyboard approval, desktop/mobile accessibility. ${route}`);
} finally {
  try { await rehearsal?.cleanup(); } finally { await browser.close(); }
}
