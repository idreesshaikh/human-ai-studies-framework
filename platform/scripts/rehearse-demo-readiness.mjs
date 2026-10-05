import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import assert from "node:assert/strict";
import { readFile, mkdir } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createRehearsalProject, rehearsalUrl } from "./rehearsal-project.mjs";

const base = rehearsalUrl();
const artifacts = process.env.REHEARSAL_ARTIFACTS || join(tmpdir(), "phoenix-demo-readiness-review");
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ headless: Boolean(process.env.CI) });
let rehearsal;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  const errors = [];
  const checks = [];
  page.on("pageerror", error => errors.push(error.message));
  rehearsal = await createRehearsalProject(page.request, base, `Synthetic readiness ${Date.now()}`);
  const { project, study } = rehearsal;
  const route = `${base}/p/${project.slug}/studies/${study.id}`;
  const quick = await page.request.post(`${base}/studies/${study.id}/quick-protocol`, { data: {
    title: "AI-assisted debugging", researchQuestions: ["Does assistance change completion time?"],
    design: "within-subjects", conditions: ["ai-assisted", "unassisted"],
    participantDescription: "Novice Python developers", plannedParticipants: 12,
    taskDescription: "Repair a Python bug", sessionMinutes: 45,
    measures: ["task completion time"], counterbalanced: true,
  } });
  assert.equal(quick.status(), 200, await quick.text());
  const { compilationId } = await quick.json();
  assert.equal((await page.request.post(`${base}/studies/${study.id}/conversation/approve`, { data: { compilationId } })).status(), 200);
  assert.equal((await page.request.post(`${base}/studies/${study.id}/simulate`, { data: { count: 2, seed: 17 } })).status(), 200);
  await page.goto(route);
  const composer = page.getByRole("textbox", { name: "Message the design assistant" });
  await composer.waitFor();

  // Real tabs, both themes, touch/desktop breakpoints, and actual tab-owned scroll containers.
  for (const theme of ["light", "dark"]) {
    if (theme === "dark") await page.getByRole("button", { name: "Theme: light", exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    for (const width of [320, 390, 768, 1024, 1440, 2048]) {
      await page.setViewportSize({ width, height: width <= 390 ? 844 : 900 });
      for (const tab of ["Setup", "Evidence", "Plan", "Run", "Data"]) {
        await page.getByRole("button", { name: tab, exact: true }).click();
        if (tab === "Setup") await composer.waitFor();
        if (tab === "Plan") await expect(page.getByRole("button", { name: "Refresh plan" })).toBeEnabled();
        if (tab === "Data") await page.getByRole("checkbox", { name: /Include dry-run/ }).waitFor();
        const overflow = await page.evaluate(() => [...document.querySelectorAll("body *")].filter(el => {
          const rect = el.getBoundingClientRect();
          return rect.width > 0 && (rect.right > innerWidth + 1 || rect.left < -1) && getComputedStyle(el).position !== "fixed";
        }).slice(0, 12).map(el => ({ tag: el.tagName, text: el.textContent.slice(0, 70), class: el.className })));
        if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) {
          await page.screenshot({ path: join(artifacts, `overflow-${theme}-${width}-${tab}.png`), fullPage: true });
          assert.fail(`${theme}/${width}/${tab}: overflow ${JSON.stringify(overflow)}`);
        }
        const axe = await new AxeBuilder({ page }).analyze();
        assert.deepEqual(axe.violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })), [], `${theme}/${width}/${tab}`);
        const scroll = await page.evaluate(() => {
          const containers = [...document.querySelectorAll("main *")].filter(el =>
            el instanceof HTMLElement && el.offsetHeight > 0 && /auto|scroll/.test(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight + 1);
          return containers.map(el => { el.scrollTop = el.scrollHeight; const moved = el.scrollTop > 0; el.scrollTop = 0; return moved; });
        });
        assert(scroll.every(Boolean), `${theme}/${width}/${tab}: blocked scroll`);
        checks.push({ theme, width, tab, axe: 0, scrollContainers: scroll.length });
      }
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole("button", { name: "Theme: dark", exact: true }).click();
  await page.getByRole("button", { name: "Setup", exact: true }).click();
  const headerBox = await page.getByRole("heading", { name: "Study design chat" }).locator("..").boundingBox();
  const formBox = await page.locator("form").filter({ has: composer }).boundingBox();
  assert(Math.abs(headerBox.x - formBox.x) < 1 && Math.abs(headerBox.width - formBox.width) < 1, "Chat header and composer must share their reading column");
  await composer.fill(Array.from({ length: 30 }, (_, i) => `Line ${i + 1}: research question, participants and measures.`).join("\n"));
  assert((await composer.boundingBox()).height <= 160);
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeInViewport();
  await composer.fill("");
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeDisabled();
  const review = page.getByRole("button", { name: "Review draft", exact: true });
  await review.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Review draft" });
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Tab");
  assert(await page.evaluate(() => Boolean(document.activeElement.closest('[role="dialog"]'))));
  await page.keyboard.press("Escape");
  await expect(review).toBeFocused();

  // The tour borrows the workspace and must restore the starting tab.
  await page.getByRole("button", { name: "Plan", exact: true }).click();
  await page.getByText("Sample size estimates", { exact: true }).click();
  const planBody = page.getByRole("region", { name: "Planning", exact: true });
  await planBody.hover();
  await page.mouse.wheel(0, 600);
  await expect.poll(() => planBody.evaluate(el => el.scrollTop)).toBeGreaterThan(0);
  await expect(page.getByRole("button", { name: "Plan", exact: true })).toBeInViewport();
  await planBody.focus();
  await page.keyboard.press("Home");
  await page.getByText("Sample size estimates", { exact: true }).click();
  await page.getByRole("button", { name: "How this workspace works" }).click();
  await expect(page.getByRole("dialog", { name: "Getting started" })).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Plan", exact: true })).toHaveAttribute("aria-current", "page");

  // Every researcher export must produce an actual, nonempty download.
  for (const name of [/^Data \(\.zip\)/, /^Replication kit/, /^Elicitation record/, /^Starter notebook/]) {
    await page.getByRole("button", { name: "Share and export" }).click();
    const downloaded = page.waitForEvent("download");
    await page.getByRole("menuitem", { name }).click();
    const download = await downloaded;
    assert.equal(await download.failure(), null);
    const bytes = await readFile(await download.path());
    assert(bytes.length > 0, `${name}: empty export`);
    if (download.suggestedFilename().endsWith(".zip")) assert.equal(bytes.subarray(0, 2).toString(), "PK");
    if (download.suggestedFilename().endsWith(".ipynb")) assert(Array.isArray(JSON.parse(bytes.toString()).cells));
    checks.push({ export: download.suggestedFilename(), bytes: bytes.length });
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ result: "PASS", checks }, null, 2));
} finally {
  try { await rehearsal?.cleanup(); } finally { await browser.close(); }
}
