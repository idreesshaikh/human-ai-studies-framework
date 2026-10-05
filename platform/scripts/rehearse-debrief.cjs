const { tmpdir } = require('node:os');
const { join } = require('node:path');
const Module = require('node:module');
const assert = require('node:assert/strict');
const { chromium, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
let html;
const originalLoad = Module._load;
Module._load = function (id, ...args) {
  if (id === 'vscode') return { ViewColumn: { Active: 1 }, window: { createWebviewPanel: () => ({
    webview: { set html(value) { html = value; }, onDidReceiveMessage() {} }, onDidDispose() {}, dispose() {},
  }) } };
  return originalLoad.call(this, id, ...args);
};
const { showEndSurvey } = require('../../extension/out/vscode/endSurvey.js');
Module._load = originalLoad;
(async () => {
  const browser = await chromium.launch({ headless: Boolean(process.env.CI) });
  let cases = 0;
  try {
    for (const condition of ['ai-assisted', 'unassisted']) {
      showEndSurvey(condition);
      for (const theme of ['light', 'dark', 'forced']) for (const width of [320, 1000]) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, forcedColors: theme === 'forced' ? 'active' : 'none' });
        const page = await context.newPage();
        await page.addInitScript(() => { window.acquireVsCodeApi = () => ({ postMessage: value => { window.submitted = value; } }); });
        await page.route('http://debrief.test/', route => route.fulfill({ contentType: 'text/html', body: html }));
        await page.goto('http://debrief.test/');
        await page.evaluate(theme => {
          const dark = theme === 'dark';
          const values = { 'font-family': 'Arial, sans-serif', foreground: dark ? '#cccccc' : '#333333', 'editor-background': dark ? '#1e1e1e' : '#ffffff', 'descriptionForeground': dark ? '#b0b0b0' : '#666666', 'button-background': dark ? '#0078d4' : '#005fb8', 'button-foreground': '#ffffff', focusBorder: '#0078d4' };
          for (const [key,value] of Object.entries(values)) document.documentElement.style.setProperty('--vscode-' + key, value);
        }, theme);
        const submit = page.getByRole('button', { name: 'Submit & finish' });
        await expect(submit).toBeDisabled();
        const questions = page.locator('fieldset[data-id]');
        const expected = condition === 'ai-assisted' ? 7 : 6;
        assert.equal(await questions.count(), expected);
        const first = questions.first().getByRole('radio').first();
        await first.focus();
        assert.equal(await first.evaluate(el => getComputedStyle(el.nextElementSibling).outlineStyle), 'solid');
        await first.press('ArrowRight');
        await expect(questions.first().getByRole('radio').nth(1)).toBeChecked();
        for (const question of await questions.all()) {
          const answer = question.getByRole('radio').nth(3);
          await answer.focus();
          await answer.press('Space');
          await expect(answer).toBeChecked();
          assert((await answer.boundingBox()).height >= 44);
        }
        await page.getByRole('textbox', { name: 'Anything else about the session? (optional)' }).fill('Synthetic accessibility rehearsal.');
        await expect(submit).toBeEnabled();
        await expect(page.getByRole('status')).toHaveText(`${expected} / ${expected} answered`);
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        assert.deepEqual((await new AxeBuilder({ page }).analyze()).violations.map(v => ({id:v.id,nodes:v.nodes.map(n=>n.html)})), []);
        if (condition === 'ai-assisted' && theme !== 'forced') await page.screenshot({ path: join(tmpdir(), `phoenix-debrief-${theme}-${width}.png`), fullPage: true });
        await submit.click();
        const result = await page.evaluate(() => window.submitted);
        assert.equal(result.kind, 'submit');
        assert.equal(Object.keys(result.responses).length, expected);
        assert.equal(result.comments, 'Synthetic accessibility rehearsal.');
        await context.close();
        cases++;
      }
    }
    console.log(`PASS: ${cases} debrief cases, native keyboard radio navigation, visible focus, 44px controls, complete-only submission, named comments, progress announcements, light/dark/high-contrast Axe and narrow layouts.`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
