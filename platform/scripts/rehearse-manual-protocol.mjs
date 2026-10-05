import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRehearsalProject, rehearsalUrl } from "./rehearsal-project.mjs";

const base = rehearsalUrl();
const artifacts = process.env.REHEARSAL_ARTIFACTS || join(tmpdir(), "phoenix-manual-protocol");
await mkdir(artifacts, { recursive: true });
const browser = await chromium.launch({ headless: Boolean(process.env.CI) });
let fixture;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  fixture = await createRehearsalProject(page.request, base, `Synthetic manual form ${Date.now()}`);
  await page.goto(`${base}/p/${fixture.project.slug}/studies/${fixture.study.id}`);
  const tools = page.getByRole("button", { name: "Research tools", exact: true });
  await tools.click();
  await page.getByRole("menuitem", { name: "Enter protocol manually", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "Enter protocol details" });
  const body = dialog.getByRole("region", { name: "Protocol fields" });
  const title = dialog.getByRole("heading", { name: "Enter protocol details" });
  const save = dialog.getByRole("button", { name: "Save draft", exact: true });
  let cases = 0;
  for (const theme of ["light", "dark"]) {
    await page.evaluate(theme => {
      localStorage.setItem("platform-theme", theme);
      document.documentElement.setAttribute("data-theme", theme);
    }, theme);
    for (const [width, height, scale] of [[1440, 900, 1], [320, 568, 1], [390, 844, 1], [844, 390, 1], [1440, 900, 2]]) {
      await page.setViewportSize({ width, height });
      await page.evaluate(scale => { document.documentElement.style.fontSize = scale === 2 ? "200%" : ""; }, scale);
      const assertChrome = async () => {
        for (const control of [title, save, dialog.getByRole("button", { name: "Close", exact: true })]) {
          const box = await control.boundingBox();
          assert(box && box.y >= 0 && box.y + box.height <= height, `Hidden dialog chrome: ${theme}/${width}/${height}/${scale}`);
        }
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      };
      await body.evaluate(el => { el.scrollTop = 0; });
      await assertChrome();
      await body.evaluate(el => { el.scrollTop = el.scrollHeight; });
      assert(await body.evaluate(el => el.scrollTop > 0), "Fields must scroll independently");
      await assertChrome();
      await page.evaluate(async () => {
        await Promise.all(document.getAnimations().filter(a => a.effect?.getComputedTiming().endTime !== Infinity).map(a => a.finished.catch(() => {})));
      });
      await page.screenshot({ path: join(artifacts, `${theme}-${width}-${height}-${scale}.png`) });
      const violations = (await new AxeBuilder({ page }).analyze()).violations;
      if (violations.length) console.log(await page.evaluate(() => ({ theme: document.documentElement.dataset.theme, dialogs: [...document.querySelectorAll('[role="dialog"]')].map(el => ({ color: getComputedStyle(el).color, bg: getComputedStyle(el).backgroundColor, opacity: getComputedStyle(el).opacity, hiddenRoot: document.querySelector('#root')?.getAttribute('aria-hidden') })) })));
      assert.deepEqual(violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => ({ target: n.target, summary: n.failureSummary })) })), [], `${theme}/${width}/${height}/${scale}`);
      cases++;
    }
  }
  await page.evaluate(() => { document.documentElement.style.fontSize = ""; document.documentElement.setAttribute("data-theme", "light"); });
  await page.setViewportSize({ width: 1440, height: 900 });
  await save.click();
  await expect(dialog.getByRole("alert")).toContainText("problems to fix");
  await dialog.getByRole("link", { name: "Study name", exact: true }).click();
  await expect(dialog.getByLabel(/^Study name/)).toBeFocused();
  await dialog.getByLabel(/^Study name/).fill("Rewrite behaviour study");
  await dialog.getByLabel(/^Research question 1/).fill("Does AI assistance change how much code developers rewrite?");
  await dialog.getByRole("button", { name: "Add research question" }).click();
  await dialog.getByLabel(/^Research question 2/).fill("How do developers perceive the rewriting process?");
  await dialog.getByRole("button", { name: "Remove research question 2" }).click();
  await expect(dialog.getByLabel(/^Research question 2/)).toHaveCount(0);
  await dialog.getByLabel(/^Planned participants/).fill("12");
  await dialog.getByRole("button", { name: "Increase Planned participants", exact: true }).click();
  await expect(dialog.getByLabel(/^Planned participants/)).toHaveValue("13");
  await dialog.getByRole("button", { name: "Decrease Planned participants", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(dialog.getByLabel(/^Planned participants/)).toHaveValue("12");
  await dialog.getByLabel(/^Condition 1/).fill("ai-assisted");
  await dialog.getByLabel(/^Condition 2/).fill("unassisted");
  await dialog.getByLabel(/^Who takes part/).fill("Python developers");
  await dialog.getByLabel(/^Session length/).fill("45");
  await dialog.getByRole("button", { name: "Increase Session length", exact: true }).click();
  await expect(dialog.getByLabel(/^Session length/)).toHaveValue("50");
  await dialog.getByRole("button", { name: "Decrease Session length", exact: true }).click();
  await expect(dialog.getByLabel(/^Session length/)).toHaveValue("45");
  await dialog.getByLabel(/^What participants do/).fill("Repair the supplied Python application.");
  await dialog.getByLabel(/^Planned participants/).fill("12.5");
  await save.click();
  await expect(dialog.getByLabel(/^Planned participants/)).toHaveAttribute("aria-invalid", "true");
  await expect(dialog.getByRole("alert")).toContainText("Enter a whole number from 4 to 1000.");
  await dialog.getByLabel(/^Planned participants/).fill("12");
  await save.click();
  await expect(dialog.getByRole("alert")).toContainText("Choose between one and six outcomes.");
  await expect(dialog.getByRole("alert")).toBeFocused();
  await dialog.getByRole("checkbox", { name: "task completion time", exact: true }).check();
  assert(await dialog.getByRole("checkbox", { name: "task completion time", exact: true }).evaluate(el => {
    const tick = getComputedStyle(el, "::before");
    return parseFloat(tick.width) > 0 && parseFloat(tick.height) > 0;
  }), "A selected outcome must draw a visible check mark");
  await dialog.getByRole("textbox", { name: "Other outcomes", exact: true }).fill("rewrite count");
  let release;
  const held = new Promise(resolve => { release = resolve; });
  let requestBody;
  await page.route("**/quick-protocol", async intercepted => {
    requestBody = intercepted.request().postDataJSON();
    await held;
    await intercepted.fulfill({ status: 503, json: { detail: "Synthetic draft outage" } });
  });
  await save.click();
  await expect(dialog.getByRole("button", { name: "Saving…", exact: true })).toBeDisabled();
  release();
  await expect(dialog.getByRole("alert")).toContainText("Synthetic draft outage");
  await expect(dialog.getByLabel(/^Study name/)).toHaveValue("Rewrite behaviour study");
  assert.deepEqual(requestBody.measures, ["task completion time", "rewrite count"]);
  await page.unroute("**/quick-protocol");
  await dialog.getByRole("button", { name: "Save draft", exact: true }).focus();
  for (let i = 0; i < 20; i++) {
    await page.keyboard.press("Tab");
    assert(await dialog.evaluate(el => el.contains(document.activeElement)), "Keyboard focus escaped the dialog");
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(tools).toBeFocused();
  assert.deepEqual(errors, []);
  console.log(`PASS: ${cases} form layout/theme/zoom cases, persistent heading/actions, independent scrolling, keyboard focus trap/return, question editing, outcome validation, custom outcomes and retained fields after an outage. ${artifacts}`);
} finally {
  try { await fixture?.cleanup(); } finally { await browser.close(); }
}
