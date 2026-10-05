import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createRehearsalProject, rehearsalUrl } from "./rehearsal-project.mjs";

const base = rehearsalUrl();
const browser = await chromium.launch({ headless: Boolean(process.env.CI) });
let rehearsal;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  rehearsal = await createRehearsalProject(page.request, base, `Synthetic human workflow ${Date.now()}`);
  const { project, study } = rehearsal;
  const api = `${base}/studies/${study.id}`;
  const route = `${base}/p/${project.slug}/studies/${study.id}`;
  const quick = await page.request.post(`${api}/quick-protocol`, { data: {
    title: "Human workflow rehearsal", researchQuestions: ["Does assistance change completion time?"],
    design: "within-subjects", conditions: ["ai-assisted", "unassisted"],
    participantDescription: "Python developers", plannedParticipants: 12,
    taskDescription: "Repair a Python bug", sessionMinutes: 45,
    measures: ["task completion time"], counterbalanced: true,
  } });
  assert.equal(quick.status(), 200);
  assert.equal((await page.request.post(`${api}/conversation/approve`, {
    data: { compilationId: (await quick.json()).compilationId },
  })).status(), 200);

  await page.goto(`${route}?tab=run`);
  await page.getByRole("button", { name: "Create participant links", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Create participant links" });
  const count = dialog.getByLabel("How many", { exact: true });
  const artifactDir = process.env.REHEARSAL_ARTIFACTS || join(tmpdir(), "phoenix-participant-links");
  await mkdir(artifactDir, { recursive: true });
  const settings = dialog.getByRole("region", { name: "Participant link settings" });
  const grain = dialog.getByRole("radiogroup", { name: "Link type" });
  await grain.getByRole("radio", { name: "Per participant", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(grain.getByRole("radio", { name: "Per session", exact: true })).toBeFocused();
  await expect(dialog.getByText("Single use: create a new link for each session.", { exact: true })).toBeVisible();
  await page.keyboard.press("Home");
  await expect(grain.getByRole("radio", { name: "Per participant", exact: true })).toHaveAttribute("aria-checked", "true");
  for (const theme of ["light", "dark"]) {
    await page.evaluate(theme => {
      localStorage.setItem("platform-theme", theme);
      document.documentElement.setAttribute("data-theme", theme);
    }, theme);
    for (const [width, height] of [[1440, 900], [320, 568], [390, 844], [844, 390]]) {
      await page.setViewportSize({ width, height });
      for (const scroll of [0, 10000]) {
        await settings.evaluate((el, top) => { el.scrollTop = top; }, scroll);
        for (const chrome of [dialog.getByRole("heading"), dialog.getByRole("button", { name: "Close", exact: true }), dialog.getByRole("button", { name: "Create 1 link", exact: true })]) {
          const box = await chrome.boundingBox();
          assert(box && box.y >= 0 && box.y + box.height <= height, `Hidden participant dialog chrome: ${theme}/${width}/${height}`);
        }
      }
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.evaluate(async () => {
        await Promise.all(document.getAnimations().filter(a => a.effect?.getComputedTiming().endTime !== Infinity).map(a => a.finished.catch(() => {})));
      });
      assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), []);
      await page.screenshot({ path: join(artifactDir, `${theme}-${width}-${height}.png`) });
    }
  }
  await page.evaluate(() => {
    localStorage.setItem("platform-theme", "light");
    document.documentElement.setAttribute("data-theme", "light");
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  // Optional capture settings are discoverable, keyboard-operable and reversible.
  await dialog.getByText("Capture settings", { exact: true }).click();
  const switches = dialog.getByRole("checkbox");
  await switches.first().waitFor();
  for (const toggle of await switches.all()) {
    const initial = await toggle.isChecked();
    await toggle.focus();
    await page.keyboard.press("Space");
    assert.equal(await toggle.isChecked(), !initial);
    await page.keyboard.press("Space");
    assert.equal(await toggle.isChecked(), initial);
  }
  assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), []);
  await dialog.getByText("Capture settings", { exact: true }).click();
  const folder = dialog.getByLabel("Study folder", { exact: true });
  await folder.fill("/home/participant/rehearsal-task");
  await dialog.getByRole("button", { name: "Save path", exact: true }).click();
  await expect(dialog.locator("#study-folder-status")).toContainText("/home/participant/rehearsal-task");
  await dialog.getByRole("button", { name: "Clear", exact: true }).click();
  await expect(dialog.locator("#study-folder-status")).toContainText("No study folder set");
  for (const value of ["", "0", "101", "2.5"]) {
    await count.fill(value);
    await dialog.getByRole("button", { name: "Create links", exact: true }).click();
    await expect(count).toHaveAttribute("aria-invalid", "true");
    assert.equal((await (await page.request.get(`${api}/enrollment/tokens`)).json()).length, 0);
  }
  await count.fill("2");
  await dialog.getByRole("button", { name: "Create 2 links", exact: true }).click();
  await expect(dialog.getByLabel("Connection link for P01", { exact: true })).toBeVisible();
  assert.equal((await (await page.request.get(`${api}/enrollment/tokens`)).json()).length, 2);
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", {
    configurable: true, value: { writeText: async () => { throw new Error("Denied"); } },
  }));
  await dialog.getByRole("button", { name: "Copy", exact: true }).first().click();
  await expect(dialog.getByRole("alert")).toContainText("Select and copy it manually");
  const link = dialog.getByLabel("Connection link for P01", { exact: true });
  await link.focus();
  assert(await link.evaluate(el => el.selectionEnd - el.selectionStart === el.value.length));
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), []);
  }
  await page.keyboard.press("Escape");

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  for (const tab of ["Setup", "Evidence", "Plan", "Run", "Data"]) {
    await page.getByRole("button", { name: tab, exact: true }).click();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `200% text: ${tab}`);
  }
  await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
  const touchContext = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
  const touchPage = await touchContext.newPage();
  await touchPage.goto(`${route}?tab=setup`);
  await touchPage.getByRole("textbox", { name: "Message the design assistant" }).waitFor();
  assert(await touchPage.evaluate(() => matchMedia("(pointer: coarse)").matches));
  const tinyTargets = await touchPage.getByRole("button").evaluateAll(buttons => buttons.filter(button => {
    const box = button.getBoundingClientRect();
    return box.width > 0 && box.height > 0 && getComputedStyle(button).visibility !== "hidden" && box.height < 44;
  }).map(button => button.getAttribute("aria-label") || button.textContent));
  assert.deepEqual(tinyTargets, [], "Touch buttons need 44px targets");
  await touchContext.close();

  // Controlled transport isolates reading/scrolling and cancellation from model latency.
  // Actual minting, protocol approval and permissions above use the real backend.
  await page.setViewportSize({ width: 1440, height: 900 });
  const history = Array.from({ length: 30 }, (_, i) => ({
    turnId: `history-${i}`, role: i % 2 ? "platform" : "researcher", author: "Researcher",
    text: `Earlier study decision ${i}. ${"Review the study details carefully. ".repeat(5)}`,
    moves: [], recommendations: [], source: "llm",
  }));
  history.at(-1).moves = [{
    moveId: "controlled-citation", kind: "caution", status: "proposed", target: "design",
    proposal: "Inspect the source before deciding.",
    grounding: [{ ref: "doi:10.0000/rehearsal", title: "Controlled research citation",
      year: 2026, confidence: 0.8, why: "Synthetic interaction fixture, not research evidence." }],
  }];
  await page.route(`**/studies/${study.id}/conversation`, intercepted => intercepted.fulfill({ json: { turns: history } }));
  const requests = [];
  let release;
  let held = new Promise(resolve => { release = resolve; });
  await page.route("**/conversation/turns/stream", async intercepted => {
    const request = intercepted.request().postDataJSON();
    requests.push(request);
    await held;
    const reply = { researcherTurnId: "rehearsal-user", platformTurnId: "rehearsal-assistant",
      text: "A controlled rehearsal response.", moves: [], recommendations: [], source: "llm" };
    try {
      await intercepted.fulfill({ contentType: "text/event-stream", body:
        `event: token\ndata: ${JSON.stringify({ text: reply.text })}\n\nevent: done\ndata: ${JSON.stringify(reply)}\n\n` });
    } catch { /* A stopped request is intentionally cancelled. */ }
  });
  await page.goto(`${route}?tab=setup`);
  await page.getByRole("button", { name: "Show protocol draft", exact: true }).click();
  const railChoices = page.getByRole("radiogroup", { name: "Right panel: literature or protocol draft" });
  await railChoices.getByRole("radio", { name: "Protocol draft", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(railChoices.getByRole("radio", { name: "Literature", exact: true })).toBeFocused();
  await expect(railChoices.getByRole("radio", { name: "Literature", exact: true })).toHaveAttribute("aria-checked", "true");
  await page.keyboard.press("Home");
  await expect(railChoices.getByRole("radio", { name: "Protocol draft", exact: true })).toBeFocused();
  await page.keyboard.press("End");
  await expect(railChoices.getByRole("radio", { name: "Literature", exact: true })).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(railChoices.getByRole("radio", { name: "Protocol draft", exact: true })).toBeFocused();
  await page.getByRole("button", { name: "Hide protocol draft", exact: true }).click();
  const composer = page.getByRole("textbox", { name: "Message the design assistant" });
  const citation = page.getByRole("button", { name: /^Grounded citation: Controlled research citation/ });
  await citation.click();
  await expect(page.getByRole("tooltip")).toContainText("Controlled research citation");
  await expect(page.getByRole("button", { name: "Noted", exact: true })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("tooltip")).toHaveCount(0);
  await composer.fill("Check this design");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByRole("button", { name: "Stop reply", exact: true }).waitFor();
  const thread = page.locator(".chat-workspace section > div.overflow-auto").first();
  await expect.poll(() => thread.evaluate(el => el.scrollTop)).toBeGreaterThan(100);
  await thread.hover();
  await page.mouse.wheel(0, -10000);
  await expect.poll(() => thread.evaluate(el => el.scrollTop)).toBe(0);
  release();
  await expect(page.getByRole("button", { name: "Stop reply", exact: true })).toHaveCount(0);
  await expect.poll(() => thread.evaluate(el => el.scrollTop)).toBe(0);

  held = new Promise(resolve => { release = resolve; });
  await composer.fill("Keep my unfinished message");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect.poll(() => requests.length).toBe(2);
  await page.getByRole("button", { name: "Stop reply", exact: true }).click();
  await expect(composer).toHaveValue("Keep my unfinished message");
  await expect(page.getByText("Stopped.", { exact: false })).toBeVisible();
  assert.equal(requests.length, 2, "Stop must not turn into an implicit Send");
  release();
  held = Promise.resolve();
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect.poll(() => requests.length).toBe(3);
  assert.equal(requests[1].requestId, requests[2].requestId, "Retry must reuse its idempotency key");
  await expect(page.getByText("Stopped.", { exact: false })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Stop reply", exact: true })).toHaveCount(0);
  // Decisions remain usable during a reply; only the final card asks a follow-up.
  history.at(-1).moves = ["first", "last"].map((id, index) => ({
    moveId: `controlled-${id}`, kind: "set-field", status: "proposed", target: "design",
    proposal: `Controlled decision ${index + 1}.`, grounding: [],
  }));
  await page.route("**/conversation/moves/controlled-*/decision", async intercepted => {
    const id = decodeURIComponent(intercepted.request().url().split("/").at(-2));
    const { status } = intercepted.request().postDataJSON();
    history.at(-1).moves.find(move => move.moveId === id).status = status;
    await intercepted.fulfill({ json: { moveId: id, status } });
  });
  await page.goto(`${route}?tab=setup`);
  const firstChoice = page.locator('[data-move-id="controlled-first"]');
  const lastChoice = page.locator('[data-move-id="controlled-last"]');
  await firstChoice.focus();
  await page.keyboard.press("a");
  await expect(lastChoice).toBeFocused();
  assert.equal(requests.length, 3, "Resolving one of several cards must not request a reply");
  held = new Promise(resolve => { release = resolve; });
  await composer.fill("Check the remaining choice");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect.poll(() => requests.length).toBe(4);
  await lastChoice.focus();
  await page.keyboard.press("r");
  await expect(page.getByRole("status").filter({ hasText: "Saved. The assistant will answer" })).toBeVisible();
  assert.equal(requests.length, 4, "A decision follow-up must wait for the active reply");
  assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => v.id), [], "Active reply accessibility");
  release();
  await expect.poll(() => requests.length).toBe(5);
  assert.deepEqual(requests[4].decision, { moveId: "controlled-last", action: "rejected" });
  await expect(page.getByRole("button", { name: "Stop reply", exact: true })).toHaveCount(0);
  await firstChoice.locator('xpath=ancestor::details').last().locator(':scope > summary').click();
  const undo = page.locator('[data-move-undo="controlled-first"]');
  await undo.focus();
  await page.keyboard.press("Enter");
  await expect(firstChoice).toBeFocused();
  await expect(firstChoice.getByRole("button", { name: "Accept", exact: true })).toBeVisible();
  assert.equal(requests.length, 5, "Undo must not request another reply");
  assert.deepEqual(errors, []);
  console.log("PASS: real mint validation, selectable links, denied clipboard, responsive dialogs, 200% text, touch targets, preserved reading position, Stop, idempotent retry, decision focus, queued final follow-up and Undo focus.");
} finally {
  try { await rehearsal?.cleanup(); } finally { await browser.close(); }
}
