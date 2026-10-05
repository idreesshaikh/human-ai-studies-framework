import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import assert from "node:assert/strict";
import { tmpdir } from "node:os";
import { join } from "node:path";
const BASE = process.env.REHEARSAL_URL;
if (!BASE || !["localhost", "127.0.0.1", "[::1]"].includes(new URL(BASE).hostname)) {
  throw new Error("Set REHEARSAL_URL to an isolated local server. This test creates synthetic studies and participant links.");
}

(async () => {
  const browser = await chromium.launch({ headless: Boolean(process.env.CI) });
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const name = `Usability rehearsal ${Date.now()}`;
    const project = await (await page.request.post(`${BASE}/projects`, {data:{name}})).json();
    const study = await (await page.request.post(`${BASE}/projects/${project.slug}/studies`, {data:{name}})).json();
    const route = `${BASE}/p/${project.slug}/studies/${study.id}`;
    await page.goto(`${route}?tab=planning`);
    await page.getByRole('link', {name:'Set up the study',exact:true}).waitFor();
    await page.getByRole('link', {name:'Set up the study',exact:true}).click();
    await page.getByRole('button', {name:'Enter the protocol details directly'}).click();
    await page.getByLabel('Study name', {exact:true}).fill(name);
    await page.getByLabel('Research question 1', {exact:true}).fill('Does AI assistance affect completion time and cognitive load?');
    await page.getByLabel('Planned participants', {exact:true}).fill('12');
    await page.getByLabel('Condition 1', {exact:true}).fill('ai-assisted');
    await page.getByLabel('Condition 2', {exact:true}).fill('unassisted');
    await page.getByLabel('Participants', {exact:true}).fill('Novice Python developers');
    await page.getByLabel('Session length', {exact:true}).fill('45');
    await page.getByLabel('Task', {exact:true}).fill('Fix the bug in the provided Python application.');
    await page.getByRole('checkbox', {name:'task completion time',exact:true}).check();
    await page.getByRole('checkbox', {name:'cognitive load',exact:true}).check();
    const compiled = page.waitForResponse(r => r.url().endsWith('/quick-protocol'));
    await page.getByRole('button', {name:'Compile details',exact:true}).click();
    assert.equal((await compiled).status(),200);
    await page.getByRole('button',{name:'Plan',exact:true}).click();
    await page.getByText('Preview of accepted decisions.',{exact:false}).waitFor();
    await page.getByRole('link',{name:'Review and apply in Setup'}).click();
    const approved = page.waitForResponse(r => r.url().includes('/conversation/approve'));
    await page.getByRole('button',{name:'Apply protocol',exact:true}).click();
    assert.equal((await approved).status(),200);
    await page.getByRole('button',{name:'Plan',exact:true}).click();
    await page.getByRole('link',{name:'Continue to enrollment'}).waitFor();
    const overview = page.getByRole('region',{name:'Planning'});
    await expect(overview.getByText('45 minutes per block',{exact:true})).toBeVisible();
    await expect(overview.getByText('12 planned participants',{exact:true})).toBeVisible();
    const select = page.getByLabel('Preview assignment for');
    await select.focus();
    await page.keyboard.press('Space');
    await expect(page.getByRole('menuitem',{name:'Participant 1',exact:true})).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await expect(page.getByRole('menuitem',{name:'Participant 2',exact:true})).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(select).toHaveText('Participant 2');
    await page.getByRole('button',{name:'Refresh plan'}).waitFor({state:'visible'});
    await expect(page.getByRole('button',{name:'Refresh plan'})).toBeEnabled();
    // A late response must not replace a newer participant assignment.
    let held;
    let captured;
    const intercepted = new Promise(resolve => { captured = resolve; });
    const oldPlan = await (await page.request.get(`${BASE}/studies/${study.id}/run-plan`)).json();
    oldPlan.blocks[0].title = 'Stale assignment must not appear';
    await page.route('**/run-plan?**', async route => {
      if (new URL(route.request().url()).searchParams.get('participantIndex') === '0') {
        held = route;
        captured();
      } else await route.continue();
    });
    await select.click();
    await page.getByRole('menuitem',{name:'Participant 1',exact:true}).click();
    await intercepted;
    await select.click();
    await page.getByRole('menuitem',{name:'Participant 2',exact:true}).click();
    await expect(page.getByRole('button',{name:'Refresh plan'})).toBeEnabled();
    const oldResponse = page.waitForResponse(r => r.url().includes('/run-plan?participantIndex=0'));
    await held.fulfill({status:200,contentType:'application/json',body:JSON.stringify(oldPlan)});
    await oldResponse;
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
    await expect(page.getByText('Stale assignment must not appear',{exact:false})).toHaveCount(0);
    await page.unroute('**/run-plan?**');
    await page.getByText('Capture and privacy',{exact:true}).click();
    await page.getByText('Raw code: not collected.',{exact:false}).waitFor();
    for (const viewport of [{width:1440,height:1000},{width:390,height:844}]) {
      await page.setViewportSize(viewport);
      await page.screenshot({path:join(tmpdir(), `phoenix-run-plan-${viewport.width}.png`),fullPage:true});
      const axe = await new AxeBuilder({page}).analyze();
      assert.deepEqual(axe.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.html)})),[]);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth));
    }
    // Verify server errors are recoverable, not a spinner or a fake empty state.
    await page.route('**/run-plan?**', r=>r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Rehearsal outage'})}));
    await page.getByRole('button',{name:'Refresh plan'}).click();
    await page.getByRole('alert').filter({hasText:'Rehearsal outage'}).waitFor();
    await page.unroute('**/run-plan?**');
    await page.getByRole('button',{name:'Refresh plan'}).click();
    await page.getByRole('link',{name:'Continue to enrollment'}).waitFor();
    await page.getByRole('link',{name:'Continue to enrollment'}).click();
    await page.getByRole('button',{name:'Create participant links',exact:true}).waitFor();
    await page.getByText('Preview the participant journey',{exact:true}).click();
    await page.getByRole('heading',{name:'How this study will run'}).waitFor();
    await page.getByRole('button',{name:'Create participant links',exact:true}).click();
    await page.getByRole('button',{name:'Create 1 link',exact:true}).click();
    await page.getByText('1 enrollment link',{exact:true}).waitFor();
    await expect(page.getByRole('button',{name:'Copy',exact:true}).first()).toBeVisible();
    assert.deepEqual(errors,[]);
    console.log('PASS: empty Plan -> manual setup -> draft preview -> approval -> keyboard assignment -> privacy -> desktop/mobile axe -> outage/retry -> enrollment');
  } finally { await browser.close(); }
})();
