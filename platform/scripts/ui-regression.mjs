// Researcher workflows against a disposable backend; --audit also checks WCAG,
// themes, responsive layouts and scroll reach. Build the platform first.
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { chromium, expect, webkit } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ROOT = resolve(import.meta.dirname, "..", "..");
const extension = JSON.parse(readFileSync(join(ROOT, "extension", "package.json"), "utf8"));
const { values } = parseArgs({ options: { dist: { type: "string" }, screenshots: { type: "string" }, audit: { type: "boolean", default: false }, browser: { type: "string", default: "chromium" } } });
const engine = { chromium, webkit }[values.browser];
if (engine !== chromium && engine !== webkit) throw new Error("Use --browser chromium or --browser webkit");
const DIST = values.dist ?? process.env.UI_DIST ?? join(ROOT, "platform", "dist");
if (values.screenshots) mkdirSync(values.screenshots, { recursive: true });
if (!existsSync(join(DIST, "index.html"))) {
  console.error(`No built app at ${DIST}. Run: npm --prefix platform run build`);
  process.exit(2);
}

const freePort = () =>
  new Promise((ok, fail) => {
    const s = createServer();
    s.listen(0, "127.0.0.1", () => {
      const { port } = s.address();
      s.close(() => ok(port));
    });
    s.on("error", fail);
  });

const port = await freePort();
const base = `http://127.0.0.1:${port}`;
const data = mkdtempSync(join(tmpdir(), "ui-regression-"));
const evidenceFixtures = [
  { paperId: "fixture-a", title: "Fixture: AI assistance and debugging", authors: [{ name: "Ada Example" }], year: 2026, venue: "Fixture journal", externalIds: { ArXiv: "2601.00001" }, citationCount: 12, abstract: "Synthetic browser fixture. A counterbalanced developer study compares assisted and unassisted debugging. Task duration and reported workload are distinct outcomes." },
  { paperId: "fixture-b", title: "Fixture: Workload during code review", authors: [{ name: "Bryn Example" }], year: 2024, externalIds: { DOI: "10.1234/fixture" }, citationCount: 4, abstract: "Synthetic browser fixture. Developers report workload while reviewing code. This text exercises paper filtering and reading." },
  { paperId: "fixture-c", title: "Fixture: Related debugging study", authors: [{ name: "Casey Example" }], year: 2023, externalIds: { DOI: "10.1234/related" }, citationCount: 7, abstract: "Synthetic browser fixture for inspecting and adding a related paper from the literature map." },
];
evidenceFixtures[0].authors.push(...Array.from({ length: 39 }, (_, index) => ({ name: `Fixture Collaborator ${index + 1}` })));
evidenceFixtures[0].abstract = `${evidenceFixtures[0].abstract}\n\n` + "A long synthetic abstract exercises the reader without changing the study workspace geometry. \\textsc{Fixture Research} remains readable while its original source text stays intact. ".repeat(24);
const collectionFixtures = Array.from({ length: 14 }, (_, index) => ({ ...evidenceFixtures[1], paperId: `fixture-collection-${index}`, title: `Fixture: Collection paper ${index + 1}`, year: 2025, externalIds: { ArXiv: `2601.${String(index + 101).padStart(5, "0")}` } }));
evidenceFixtures.push(...collectionFixtures);
writeFileSync(join(data, "metadata.json"), JSON.stringify(evidenceFixtures));
const server = spawn("uv", ["run", "python", "-c", `
import json, os, urllib.parse
from pathlib import Path
import uvicorn
from middleware import semantic_scholar
from middleware.app import create_app
from middleware.settings import Settings
records = json.loads(Path(os.environ["UI_METADATA_FIXTURE"]).read_text())
def metadata(url):
    url = urllib.parse.unquote(url).lower()
    if "/references" in url:
        return {"data": [{"citedPaper": records[2]}]}
    if "/citations" in url:
        return {"data": []}
    if "forpaper" in url:
        return {"recommendedPapers": []}
    for row in records:
        if any(urllib.parse.urlsplit(url).path.endswith("/paper/" + kind.lower() + ":" + str(ident).lower()) for kind, ident in row["externalIds"].items()):
            return row
    raise semantic_scholar.SemanticScholarError("No synthetic fixture for this paper", status=404)
semantic_scholar.get_json = metadata
uvicorn.run(create_app(Settings()), host="127.0.0.1", port=int(os.environ["MIDDLEWARE_PORT"]))
`], {
  cwd: ROOT,
  env: {
    ...process.env,
    DATABASE_URL: "",
    MIDDLEWARE_AUTH: "none",
    MIDDLEWARE_TOKEN: "",
    MIDDLEWARE_PROTOCOL: "",
    MIDDLEWARE_REFRESH_INTERVAL_H: "",
    MIDDLEWARE_PORT: String(port),
    MIDDLEWARE_WEB: DIST,
    MIDDLEWARE_DB: join(data, "ui.sqlite3"),
    MIDDLEWARE_DATA_DIR: data,
    MIDDLEWARE_CORPUS_BOOTSTRAP: "0",
    LLM_API_KEY: "",
    LLM_BASE_URL: "",
    UI_METADATA_FIXTURE: join(data, "metadata.json"),
  },
  detached: process.platform !== "win32",
  stdio: "ignore",
});
const closed = new Promise((ok) => server.once("close", ok));
const stop = (signal = "SIGTERM") => {
  try {
    if (server.pid && process.platform !== "win32") process.kill(-server.pid, signal);
    else server.kill(signal);
  } catch (error) { if (error.code !== "ESRCH") throw error; }
};
const onExit = () => stop();
process.on("exit", onExit);
let browser;
const failures = [];
const auditResults = [];
const check = (ok, message) => {
  console.log(`${ok ? "PASS" : "FAIL"}: ${message}`);
  if (!ok) failures.push(message);
};

const auditPage = async (page, label) => {
  if (!values.audit) return;
  await page.bringToFront();
  for (const [theme, width, height] of [["light", 1280, 800], ["dark", 1280, 800], ["light", 390, 844], ["dark", 390, 844], ["light", 768, 1024], ["light", 360, 800], ["dark", 320, 568]]) {
    await page.setViewportSize({ width, height });
    await page.evaluate((theme) => document.documentElement.setAttribute("data-theme", theme), theme);
    await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
    });
    await page.waitForFunction(() => document.getAnimations().every((animation) => !(animation instanceof CSSTransition) || animation.playState !== "running"), null, { timeout: 5000 });
    const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]).analyze();
    const geometry = await page.evaluate(() => {
      const scrollers = [...document.querySelectorAll("*")].filter((el) => el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 2 && /auto|scroll/.test(getComputedStyle(el).overflowY));
      const scrollChecks = scrollers.map((el) => {
        const before = el.scrollTop;
        el.scrollTop = el.scrollHeight;
        const reachable = el.scrollTop >= el.scrollHeight - el.clientHeight - 2;
        el.scrollTop = before;
        return reachable;
      });
      return { overflow: document.documentElement.scrollWidth > innerWidth + 1, scrollChecks };
    });
    const where = `${label}, ${theme}, ${width}px`;
    check(result.violations.length === 0, `${where}: WCAG 2.2 AA (${result.passes.length} rules passed; ${result.violations.length} violations)`);
    for (const violation of result.violations) {
      console.error(`${where}: ${violation.id}: ${violation.help}`);
      for (const node of violation.nodes) console.error(`  ${node.target.join(" ")}: ${node.failureSummary}`);
    }
    check(!geometry.overflow, `${where}: no page overflow`);
    check(geometry.scrollChecks.every(Boolean), `${where}: scroll regions reach their content (${geometry.scrollChecks.length})`);
    auditResults.push({ label, theme, width, passedRules: result.passes.length, violations: result.violations.map((item) => ({ id: item.id, impact: item.impact, targets: item.nodes.map((node) => node.target) })), ...geometry });
  }
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.evaluate(() => document.documentElement.setAttribute("data-theme", "light"));
};

const settleVisual = async (page) => {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
  });
  await page.waitForFunction(
    () => document.getAnimations().every((animation) => !(animation instanceof CSSTransition) || animation.playState !== "running"),
    null,
    { timeout: 5000 },
  );
};

const api = async (path, init) => {
  const res = await fetch(base + path, {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} -> ${res.status}`);
  return res.json();
};

try {
for (let i = 0; ; i++) {
  try {
    await api("/health");
    break;
  } catch {
    if (i > 60) throw new Error("backend did not start");
    await new Promise((r) => setTimeout(r, 500));
  }
}

const { protocol } = await api("/templates/two-group-rct-v1/instantiate", {
  method: "POST",
  body: JSON.stringify({ parameters: {} }),
});
const bare = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "No protocol" }) })).id;
const full = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "With protocol", protocol }) })).id;
const literature = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "Evidence browser fixtures" }) })).id;
const between = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "Between-subjects planner fixture" }) })).id;
const betweenDraft = await api(`/studies/${between}/quick-protocol`, {
  method: "POST",
  body: JSON.stringify({
    title: "Between-subjects planner fixture",
    researchQuestions: ["Does access to an AI assistant change debugging time?"],
    design: "between-subjects",
    conditions: ["AI assistant permitted", "No AI assistant"],
    participantDescription: "Early-career Python developers",
    plannedParticipants: 24,
    taskDescription: "Fix a seeded bug in a synthetic Python repository.",
    sessionMinutes: 60,
    measures: ["Time to first passing test"],
    measureIds: ["E1"],
    typedMeasures: true,
    counterbalanced: false,
  }),
});
check(betweenDraft.valid, "between-subjects planner fixture compiles through the protocol compiler");
await api(`/studies/${between}/conversation/approve`, {
  method: "POST",
  body: JSON.stringify({
    compilationId: betweenDraft.compilationId,
    rationale: "Synthetic planner regression fixture",
    approvedBy: "Researcher",
  }),
});

browser = await engine.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
context.on("weberror", (event) => check(false, `uncaught browser error: ${event.error().message}`));
const tokenContext = await browser.newContext({ viewport: { width: 320, height: 568 } });
const tokenPage = await tokenContext.newPage();
tokenPage.on("pageerror", (error) => check(false, `uncaught token sign-in error: ${error.message}`));
const fixtureToken = "disposable-browser-token";
await tokenPage.route(`${base}/auth/config`, (route) => route.fulfill({ json: { mode: "token" } }));
await tokenPage.route(`${base}/me`, async (route) =>
  (await route.request().allHeaders()).authorization === `Bearer ${fixtureToken}`
    ? route.continue()
    : route.fulfill({ status: 401, json: { detail: "Invalid session token" } }),
);
await tokenPage.goto(base + "/signin?next=%2Fsettings");
const tokenInput = tokenPage.getByLabel("Session token", { exact: true });
await tokenInput.fill("incorrect-browser-token");
await tokenInput.press("Enter");
await expect(tokenPage.getByText("That session token wasn’t accepted.", { exact: false })).toBeVisible();
await expect(tokenInput).toHaveAttribute("aria-invalid", "true");
check(await tokenPage.evaluate(() => localStorage.getItem("middleware.token")) === null, "an incorrect token keeps the sign-in form and is never stored");
await auditPage(tokenPage, "invalid session token");
await tokenInput.fill(fixtureToken);
await tokenInput.press("Enter");
await expect(tokenPage.getByRole("heading", { name: "Account settings", exact: true })).toBeVisible();
check(new URL(tokenPage.url()).pathname === "/settings", "correcting the token opens the requested page");
await tokenPage.evaluate(() => localStorage.setItem("middleware.token", "expired-browser-token"));
await tokenPage.reload();
await expect(tokenPage.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
await tokenInput.fill(fixtureToken);
await tokenInput.press("Enter");
await expect(tokenPage.getByRole("heading", { name: "Account settings", exact: true })).toBeVisible();
check(true, "a rejected stored token allows sign-in without clearing browser storage manually");
await tokenPage.getByRole("button", { name: "Account", exact: true }).press("ArrowDown");
await tokenPage.getByRole("menuitem", { name: "Sign out", exact: true }).press("Enter");
await expect(tokenPage.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
check(true, "sign-out returns to the sign-in form");
await tokenContext.close();
const navigation = await context.newPage();
await navigation.emulateMedia({ reducedMotion: "reduce" });
await navigation.setViewportSize({ width: 320, height: 568 });
await navigation.goto(base + "/home");
const skip = navigation.getByRole("link", { name: "Skip to main content" });
await skip.press("Enter");
await expect(navigation.getByRole("main")).toBeFocused();
const navToggle = navigation.getByRole("button", { name: "Toggle navigation", includeHidden: true });
await navToggle.press("Enter");
const drawer = navigation.getByRole("dialog", { name: "Navigation" });
await expect(drawer).toBeVisible();
await expect(navToggle).toHaveAttribute("aria-expanded", "true");
for (let index = 0; index < 6; index++) {
  await navigation.keyboard.press("Tab");
  check(await drawer.evaluate((el) => el.contains(document.activeElement)), "mobile navigation keeps keyboard focus within the drawer");
}
await navigation.keyboard.press("Escape");
await expect(drawer).toBeHidden();
await expect(navToggle).toBeFocused();
check(true, "skip link and Escape return keyboard focus to the expected destination");
await navigation.setViewportSize({ width: 1280, height: 800 });
await navigation.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
await expect(navigation.getByRole("heading", { name: "Studies", exact: true })).toBeInViewport();
check(await navigation.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "the study list reflows at 200% text size");
await navigation.goto(base + "/studies/%E0%A4%A");
await expect(navigation.getByRole("alert")).toContainText("The study couldn’t be loaded.");
await navigation.getByRole("link", { name: "Return to studies", exact: true }).click();
await expect(navigation.getByRole("heading", { name: "Studies", exact: true })).toBeVisible();
check(true, "a malformed study URL offers a working return to Studies");
await navigation.close();
const evidence = await context.newPage();
await evidence.goto(`${base}/p/implicit/studies/${literature}?tab=library`);
const paperInput = evidence.getByRole("textbox", { name: /arXiv id or DOI|Paper link or identifier/i });
await paperInput.fill("https://arxiv.org/abs/2601.00001");
const addingPaper = evidence.waitForResponse((response) => response.url().endsWith(`/studies/${literature}/papers`) && response.request().method() === "POST");
await paperInput.press("Enter");
const addedPaper = await addingPaper;
check(addedPaper.status() === 200, "Evidence accepts a pasted arXiv link");
check(addedPaper.request().postDataJSON().arxivId === "2601.00001", "Evidence resolves the paper link to its scholarly identifier");
if (!addedPaper.ok()) throw new Error("pasted paper link did not reach a successful lookup");
await evidence.getByRole("heading", { name: evidenceFixtures[0].title, exact: true }).waitFor();
await paperInput.fill("https://doi.org/10.1234/fixture");
const addingDoi = evidence.waitForResponse((response) => response.url().endsWith(`/studies/${literature}/papers`) && response.request().method() === "POST");
await paperInput.press("Enter");
const addedDoi = await addingDoi;
check(addedDoi.ok() && addedDoi.request().postDataJSON().doi === "10.1234/fixture", "Evidence accepts a pasted DOI link");
await evidence.getByRole("heading", { name: evidenceFixtures[1].title, exact: true }).waitFor();
const list = evidence.getByRole("region", { name: "Study paper list", exact: true });
check(await evidence.getByRole("searchbox", { name: "Filter papers", exact: true }).count() === 0, "a short paper list shows no filter or sort controls");
await list.getByRole("button", { name: new RegExp(evidenceFixtures[0].title) }).click();
await evidence.getByRole("textbox", { name: "Protocol links", exact: true }).fill("RQ-1, RQ-1, RQ-2");
await evidence.getByRole("button", { name: "Save links", exact: true }).click();
await evidence.getByRole("status").filter({ hasText: "Protocol links saved." }).waitFor();
check(JSON.stringify((await api(`/studies/${literature}/papers`)).find((paper) => paper.paperRef === "arxiv:2601.00001").links.sort()) === JSON.stringify(["RQ-1", "RQ-2"]), "protocol links save without duplicate targets");
check(await evidence.getByRole("link", { name: "Open source", exact: true }).getAttribute("href") === "https://arxiv.org/abs/2601.00001", "selected papers have a readable source link");
await evidence.getByRole("textbox", { name: "Protocol links", exact: true }).fill("RQ-9");
await list.getByRole("button", { name: new RegExp(evidenceFixtures[1].title) }).click();
await list.getByRole("button", { name: new RegExp(evidenceFixtures[0].title) }).click();
check(await evidence.getByRole("textbox", { name: "Protocol links", exact: true }).inputValue() === "RQ-9", "switching papers preserves unsaved protocol-link drafts");
await evidence.getByRole("textbox", { name: "Protocol links", exact: true }).fill("RQ-1, RQ-2");
await evidence.waitForFunction(() => ![...document.querySelectorAll('[role="status"]')].some((element) => element.textContent.includes("Finding related literature")));
const related = evidence.getByRole("button", { name: `${evidenceFixtures[2].title} (related paper)`, exact: true });
await related.focus();
await related.press("Space");
await evidence.getByRole("heading", { name: evidenceFixtures[2].title, exact: true }).waitFor();
check(await evidence.getByRole("button", { name: "Add to study", exact: true }).isVisible(), "map papers open with Space and can be added from their detail");
await auditPage(evidence, "populated Evidence and related paper");
if (values.screenshots) {
  await evidence.evaluate(() => { document.activeElement?.blur(); document.querySelector('[role="region"][aria-label="Literature"]').scrollTop = 0; });
  await evidence.screenshot({ path: join(values.screenshots, "evidence-populated-desktop.png"), fullPage: true });
  await evidence.setViewportSize({ width: 390, height: 844 });
  await evidence.screenshot({ path: join(values.screenshots, "evidence-populated-mobile.png"), fullPage: true });
  await evidence.setViewportSize({ width: 1280, height: 800 });
}
await evidence.getByRole("button", { name: "Add to study", exact: true }).click();
await evidence.getByRole("status").filter({ hasText: "Related paper added" }).waitFor();
await evidence.getByRole("button", { name: "Remove paper", exact: true }).click();
await evidence.getByRole("button", { name: "Cancel", exact: true }).click();
check((await api(`/studies/${literature}/papers`)).length === 3, "canceling removal preserves the paper and its links");
await evidence.getByRole("button", { name: "Remove paper", exact: true }).click();
await evidence.getByRole("button", { name: "Remove from study", exact: true }).click();
await evidence.getByRole("status").filter({ hasText: "Paper and its protocol links removed" }).waitFor();
check((await api(`/studies/${literature}/papers`)).length === 2, "confirmed paper removal persists");
await paperInput.fill("https://example.org/unrecognized-paper");
await paperInput.press("Enter");
check(await paperInput.getAttribute("aria-invalid") === "true", "unsupported paper links have an inline validation error");
await paperInput.fill("2601.99999");
await paperInput.press("Enter");
await evidence.getByRole("alert").filter({ hasText: /couldn't find that paper/ }).waitFor();
check(await paperInput.inputValue() === "2601.99999", "failed paper lookup preserves the entered identifier");
await evidence.reload();
await evidence.getByRole("region", { name: "Study paper list", exact: true }).getByRole("button", { name: new RegExp(evidenceFixtures[0].title) }).click();
await evidence.route(`${base}/studies/${literature}/papers`, async (route) => {
  if (route.request().method() === "GET") await route.fulfill({ status: 503, json: { detail: "Synthetic read failure" } });
  else await route.continue();
});
await evidence.getByRole("textbox", { name: "Protocol links", exact: true }).fill("RQ-3");
await evidence.getByRole("button", { name: "Save links", exact: true }).click();
await evidence.getByRole("status").filter({ hasText: "Protocol links saved." }).waitFor();
await evidence.getByRole("alert").filter({ hasText: "Could not refresh study papers." }).waitFor();
check(await evidence.getByRole("heading", { name: evidenceFixtures[0].title, exact: true }).isVisible(), "a failed refresh retains the reading pane and successful save feedback");
await evidence.unroute(`${base}/studies/${literature}/papers`);
await evidence.getByRole("button", { name: "Try again", exact: true }).click();
await evidence.getByRole("alert").filter({ hasText: "Could not refresh study papers." }).waitFor({ state: "hidden" });
const map = evidence.getByRole("group", { name: /^Literature map/ });
await map.scrollIntoViewIfNeeded();
const bodyScroll = evidence.getByRole("region", { name: "Literature", exact: true });
await bodyScroll.evaluate((element) => { element.scrollTop = 0; });
const beforeScroll = await bodyScroll.evaluate((element) => element.scrollTop);
await map.hover();
await evidence.mouse.wheel(0, 250);
await evidence.waitForFunction((before) => document.querySelector('[role="region"][aria-label="Literature"]').scrollTop > before, beforeScroll);
check(true, "normal scrolling over the map continues through the Evidence page");
const beforeZoom = await map.locator(":scope > g").getAttribute("transform");
await evidence.getByRole("button", { name: "Zoom out", exact: true }).click();
check(await map.locator(":scope > g").getAttribute("transform") !== beforeZoom, "map zoom is available through keyboard-accessible buttons");
await evidence.getByRole("button", { name: "Fit literature map", exact: true }).click();
for (const record of collectionFixtures) await api(`/studies/${literature}/papers`, { method: "POST", body: JSON.stringify({ arxivId: record.externalIds.ArXiv }) });
await evidence.reload();
const collection = evidence.getByRole("region", { name: "Study paper list", exact: true });
await evidence.getByRole("searchbox", { name: "Filter papers", exact: true }).fill("2024");
check(await collection.getByRole("button").count() === 1 && await collection.getByRole("button", { name: new RegExp(evidenceFixtures[1].title) }).isVisible(), "study papers filter by bibliographic information");
await evidence.getByRole("searchbox", { name: "Filter papers", exact: true }).fill("no such paper");
await evidence.getByRole("button", { name: "Clear filter", exact: true }).click();
await evidence.getByRole("combobox", { name: "Sort papers", exact: true }).click();
await evidence.getByRole("option", { name: "Newest publication", exact: true }).click();
check((await collection.getByRole("button").first().innerText()).includes(evidenceFixtures[0].title), "study papers can be sorted by publication year");
await collection.getByRole("button", { name: new RegExp(evidenceFixtures[0].title) }).click();
const frameHeight = async () => evidence.getByRole("complementary", { name: "Paper details", exact: true }).evaluate((element) => element.getBoundingClientRect().height);
const longHeight = await frameHeight();
const listHeight = await collection.evaluate((element) => element.parentElement.getBoundingClientRect().height);
check(Math.abs(longHeight - listHeight) <= 1, "desktop paper list and reader share one stable height");
await collection.getByRole("button", { name: new RegExp(evidenceFixtures[1].title) }).click();
check(Math.abs(await frameHeight() - longHeight) <= 1, "switching between short and long papers preserves the reading frame");
await collection.getByRole("button", { name: new RegExp(evidenceFixtures[0].title) }).click();
await evidence.getByText("View all 40 authors", { exact: true }).click();
check(Math.abs(await frameHeight() - longHeight) <= 1, "expanding the full author list does not grow the reading card");
const content = evidence.getByRole("region", { name: "Paper reader content", exact: true });
check((await content.innerText()).includes("Fixture Collaborator 39") && !(await content.innerText()).includes("\\textsc{"), "full author details and abstract formatting stay readable");
check(await collection.evaluate((element) => element.scrollHeight > element.clientHeight), "a growing paper collection scrolls within its frame");
await evidence.getByText("View all 40 authors", { exact: true }).click();
await content.evaluate((element) => { element.scrollTop = 0; });
await auditPage(evidence, "bounded Evidence with long bibliography");
if (values.screenshots) {
  await evidence.evaluate(() => { document.activeElement?.blur(); document.querySelector('[role="region"][aria-label="Literature"]').scrollTop = 0; });
  await evidence.screenshot({ path: join(values.screenshots, "evidence-long-desktop.png"), fullPage: true });
  await evidence.setViewportSize({ width: 390, height: 844 });
  await evidence.screenshot({ path: join(values.screenshots, "evidence-long-mobile.png"), fullPage: true });
  await evidence.setViewportSize({ width: 1280, height: 800 });
}
await evidence.getByLabel("Upload a PDF", { exact: true }).setInputFiles({ name: "not-a-pdf.pdf", mimeType: "application/pdf", buffer: Buffer.from("This is not PDF content.") });
await evidence.getByRole("alert").waitFor();
check(!/upload failed:|HTTP \d{3}/.test(await evidence.getByRole("alert").innerText()), "PDF errors explain the failed upload in readable language");
await evidence.close();

const viewer = await context.newPage();
await viewer.route(`${base}/studies/${literature}/summary`, async (route) => {
  const response = await route.fetch();
  const body = await response.json();
  body.role = "viewer";
  await route.fulfill({ response, json: body });
});
await viewer.goto(`${base}/p/implicit/studies/${literature}?tab=library`);
await viewer.getByText("Your access is read-only.", { exact: false }).waitFor();
check(await viewer.getByRole("button", { name: "Add paper", exact: true }).count() === 0, "read-only Evidence hides paper mutations");
await viewer.getByRole("region", { name: "Study paper list", exact: true }).getByRole("button", { name: new RegExp(evidenceFixtures[0].title) }).click();
check(await viewer.getByRole("button", { name: "Save links", exact: true }).count() === 0 && await viewer.getByRole("link", { name: "Open source", exact: true }).isVisible(), "viewers can inspect sources and saved links without editing controls");
await auditPage(viewer, "read-only Evidence");
const viewerWrites = [];
viewer.on("request", (request) => {
  if (request.method() === "POST") viewerWrites.push(request.url());
});
await viewer.getByRole("button", { name: "Setup", exact: true }).click();
await viewer.getByText("No messages have been recorded for this study.", { exact: true }).waitFor();
check(await viewer.getByRole("textbox", { name: "Message the design assistant" }).count() === 0 &&
  await viewer.getByRole("button", { name: "Research tools" }).count() === 0 &&
  viewerWrites.length === 0, "read-only Setup does not offer or send write actions");
await viewer.close();

const PROTOCOL_ONLY = /\/studies\/[^/]+\/(plan|status|dataset|live|enrollment)(\/|\?|$)/;
const RING_SCAN = () => {
  const sel = 'a[href],button:not([disabled]),input:not([type=hidden]):not([disabled]),textarea,select,[tabindex]:not([tabindex="-1"]),[role=slider],summary';
  const ring = (el) => {
    const s = getComputedStyle(el);
    return s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0 && s.outlineColor !== "rgba(0, 0, 0, 0)";
  };
  const doubles = [];
  const els = [...document.querySelectorAll(sel)].filter((e) => e.offsetParent !== null);
  for (const el of els) {
    el.focus({ focusVisible: true });
    let n = 0;
    for (let node = el; node && node !== document.body; node = node.parentElement) if (ring(node)) n++;
    if (n > 1) doubles.push((el.getAttribute("aria-label") || el.textContent || el.tagName).trim().slice(0, 40));
  }
  return { focusable: els.length, doubles };
};

await context.route("**/*", (route) => {
  if (new URL(route.request().url()).origin !== base) {
    check(false, "regression build must use the disposable backend");
    return route.abort();
  }
  return route.continue();
});
  for (const [label, id, hasProtocol] of [["no-protocol study", bare, false], ["protocol study", full, true]]) {
    for (const tab of ["conversation", "library", "planning", "enrollment", "data"]) {
      const page = await context.newPage();
      const requests = [];
      const consoleErrors = [];
      page.on("request", (r) => requests.push(new URL(r.url()).pathname));
      page.on("console", (m) => m.type() === "error" && consoleErrors.push(m.text()));
      await page.goto(`${base}/p/implicit/studies/${id}?tab=${tab}`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(200);
      const where = `${label}, ${tab} tab`;
      await auditPage(page, where);
      if (!hasProtocol) {
        const early = requests.filter((p) => PROTOCOL_ONLY.test(p));
        check(early.length === 0, `${where}: no request that needs a protocol (${[...new Set(early)].join(", ") || "none"})`);
        const red = await page.locator(".text-critical:visible").allTextContents();
        check(red.length === 0, `${where}: no red error text (${red.map((t) => t.trim().slice(0, 50)).join(" | ") || "none"})`);
        check(consoleErrors.length === 0, `${where}: no console errors (${consoleErrors.length})`);
        if (tab === "conversation") {
          const text = await page.locator("body").innerText();
          check(!/Leads|Steer mode|initiative|Examples and study tools/.test(text), `${where}: plain start-screen wording`);
        }
        if (tab === "library") {
          check(await page.getByRole("status").filter({ hasText: "Never refreshed" }).isVisible(), `${where}: library freshness is visible`);
        }
      }
      await page.evaluate(() => document.querySelectorAll("details:not([data-example-questions])").forEach((d) => (d.open = true)));
      const { focusable, doubles } = await page.evaluate(RING_SCAN);
      check(doubles.length === 0, `${where}: at most one focus ring per element (${focusable} focusable; stacked: ${doubles.join(", ") || "none"})`);
      if (values.screenshots) {
        await page.evaluate(() => {
          document.activeElement?.blur();
          document.querySelectorAll("*").forEach((element) => { element.scrollTop = 0; });
        });
        await settleVisual(page);
        await page.screenshot({ path: join(values.screenshots, `${hasProtocol ? "protocol" : "empty"}-${tab}-desktop.png`), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        const mobile = await page.evaluate(RING_SCAN);
        check(mobile.doubles.length === 0, `${where}: no stacked focus rings on mobile`);
        await page.evaluate(() => {
          document.activeElement?.blur();
          document.querySelectorAll("*").forEach((element) => { element.scrollTop = 0; });
        });
        await settleVisual(page);
        await page.screenshot({ path: join(values.screenshots, `${hasProtocol ? "protocol" : "empty"}-${tab}-mobile.png`), fullPage: true });
      }
      await page.close();
    }
  }
  for (const path of ["/home", "/repertoire", "/settings"]) {
    const page = await context.newPage();
    await page.goto(base + path);
    await page.waitForLoadState("networkidle");
    await auditPage(page, path);
    if (path === "/home") {
      check(await page.getByRole("heading", { name: "Studies", exact: true }).isVisible(), "home opens the study list");
    }
    if (path === "/repertoire") {
      check(await page.getByText("No literature indexed yet.", { exact: false }).isVisible(), "empty evidence index has an honest state");
      check(await page.getByRole("textbox", { name: "Describe your study", exact: true }).isVisible(), "starting a conversation remains available before literature indexing");
    }
    const { focusable, doubles } = await page.evaluate(RING_SCAN);
    check(doubles.length === 0, `${path}: at most one focus ring per element (${focusable} focusable; stacked: ${doubles.join(", ") || "none"})`);
    if (values.screenshots) {
      await page.evaluate(() => {
        document.activeElement?.blur();
        document.querySelectorAll("*").forEach((element) => { element.scrollTop = 0; });
      });
      await page.screenshot({ path: join(values.screenshots, `${path.replaceAll("/", "-")}-desktop.png`), fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({ path: join(values.screenshots, `${path.replaceAll("/", "-")}-mobile.png`), fullPage: true });
    }
    await page.close();
  }
  {
    // A theme applied with no saved preference behind it (the sign-in
    // toggle, or a save that failed) is still what is on screen.
    const page = await context.newPage();
    await page.goto(base + "/settings");
    await page.evaluate(() => localStorage.setItem("platform-theme", "dark"));
    await page.reload();
    await page.waitForLoadState("networkidle");
    const applied = await page.evaluate(() => document.documentElement.dataset.theme);
    const theme = page.getByRole("combobox", { name: "Theme", exact: true });
    const shown = (await theme.innerText()).trim();
    check(applied === "dark" && shown === "Dark", `settings theme control shows the applied theme (applied ${applied}, shown ${shown})`);
    await theme.press("Enter");
    const selectedTheme = page.getByRole("option", { name: "Dark", exact: true, selected: true });
    const indicatorClearsLabel = await selectedTheme.evaluate((option) => {
      const indicator = option.querySelector('[data-slot="select-item-indicator"]');
      const label = option.querySelector(".type-body");
      return indicator.getBoundingClientRect().right < label.getBoundingClientRect().left;
    });
    check(indicatorClearsLabel, "selected listbox options keep the checkmark clear of their label");
    await page.keyboard.press("l");
    await page.keyboard.press("Enter");
    await expect(theme).toHaveText("Light");
    await expect(theme).toBeFocused();
    check(true, "select typeahead changes the theme and returns keyboard focus");
    await page.close();
  }

  const page = await context.newPage();
  const requests = [];
  page.on("request", (request) => requests.push(new URL(request.url()).pathname));
  await page.goto(`${base}/p/implicit/studies/${bare}?tab=planning`);
  await page.waitForLoadState("networkidle");
  for (const name of ["Run", "Data", "Plan", "Run", "Data"]) {
    await page.getByRole("button", { name, exact: true }).click();
    await page.waitForTimeout(100);
  }
  await page.waitForTimeout(16_000);
  check(!requests.some((path) => PROTOCOL_ONLY.test(path)), "empty study: revisits and polling never request a protocol-dependent route");
  await page.getByRole("button", { name: "Setup", exact: true }).click();
  await page.getByRole("button", { name: "Research tools", exact: true }).click();
  await page.getByRole("menuitem", { name: "Enter protocol manually" }).click();
  for (const [id, text] of Object.entries({
    "manual-title": "Manual browser study", "manual-rq-0": "Does AI change task completion time?",
    "manual-condition-0": "ai-assisted", "manual-condition-1": "unassisted",
    "manual-participants": "Python developers", "manual-planned": "12",
    "manual-minutes": "45", "manual-task": "Fix a small Python maintenance task",
  })) await page.locator(`#${id}`).fill(text);
  await page.getByRole("button", { name: "Add research question", exact: true }).click();
  await page.locator("#manual-rq-1").fill("does ai change task completion time?");
  await page.locator("#manual-condition-1").fill("AI-assisted");
  await page.getByRole("combobox", { name: "Study design", exact: true }).click();
  await page.getByRole("option", { name: /^Between-subjects/ }).click();
  await page.locator("#manual-planned").fill("4");
  await page.getByRole("checkbox", { name: /^(task completion time|Time to first passing test)$/ }).check();
  const submitted = () => requests.filter((path) => path.endsWith("/quick-protocol")).length;
  const beforeInvalid = submitted();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await page.getByRole("alert").waitFor();
  for (const id of ["manual-rq-1", "manual-condition-1", "manual-planned"]) {
    check(await page.locator(`#${id}`).getAttribute("aria-invalid") === "true", `${id}: invalid input has an inline error`);
  }
  check(submitted() === beforeInvalid, "duplicate questions, conditions and insufficient group size are caught before saving");
  await page.getByRole("link", { name: "Planned participants", exact: true }).click();
  check(await page.locator("#manual-planned").evaluate((element) => element === document.activeElement), "validation summary returns focus to the field to fix");
  await page.getByRole("button", { name: "Remove research question 2", exact: true }).click();
  await page.locator("#manual-condition-1").fill("unassisted");
  await page.getByRole("combobox", { name: "Study design", exact: true }).click();
  await page.getByRole("option", { name: /^Within-subjects/ }).click();
  await page.locator("#manual-planned").fill("12");
  await page.getByRole("checkbox", { name: /^(task completion time|Time to first passing test)$/ }).check();
  await page.locator("#manual-other-outcomes").fill("mental demand");
  await page.waitForTimeout(500);
  const suggestedMeasure = page.getByRole("button", { name: "Add mental demand", exact: true });
  check(await suggestedMeasure.count() === 1, "manual outcomes: supported catalog suggestion is offered");
  if (await suggestedMeasure.count()) {
    await suggestedMeasure.click();
    check(await page.locator("#manual-other-outcomes").evaluate((element) => element === document.activeElement), "adding a measure returns keyboard focus to the outcomes field");
  }
  else await page.locator("#manual-other-outcomes").fill("");
  const dialogRings = await page.evaluate(RING_SCAN);
  check(dialogRings.doubles.length === 0, `manual protocol dialog: no stacked focus rings (${dialogRings.doubles.join(", ") || "none"})`);
  await auditPage(page, "manual protocol dialog");
  const savedManual = page.waitForResponse((response) => response.url().endsWith(`/studies/${bare}/quick-protocol`) && response.request().method() === "POST");
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  const savedResponse = await savedManual;
  const savedPayload = await savedResponse.json();
  check(savedPayload.protocol?.protocolVersion === 6, "manual outcomes: confirmed catalog choices save a v6 protocol");
  await page.getByRole("dialog").waitFor({ state: "hidden" });
  await page.getByRole("button", { name: "Review draft", exact: true }).last().click();
  await expect(page.getByText(/Participants will repeat a task/)).toBeVisible();
  check(true, "review explains repeated-task risk before applying a within-subjects protocol");
  await auditPage(page, "protocol review dialog");
  const approvalPath = `${base}/studies/${bare}/conversation/approve`;
  const staleDraft = "The draft changed. Review the refreshed protocol before applying it.";
  await page.route(approvalPath, (route) => route.fulfill({
    status: 409,
    json: { detail: staleDraft },
  }), { times: 1 });
  const draftReview = page.getByRole("dialog", { name: "Review draft" });
  await page.setViewportSize({ width: 320, height: 568 });
  await draftReview.getByRole("button", { name: "Apply protocol", exact: true }).click();
  await expect(draftReview.getByRole("alert")).toHaveText(staleDraft);
  await expect(draftReview.getByRole("button", { name: "Apply protocol", exact: true })).toBeEnabled();
  check(true, "a stale approval shows its error inside the mobile review and requires explicit reapproval");
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.getByRole("button", { name: "Apply protocol", exact: true }).click();
  await page.getByRole("link", { name: /Applied\. Plan recruitment/ }).waitFor();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Plan", exact: true }).click();
  await page.getByRole("heading", { name: "Plan participant recruitment" }).waitFor();
  const outcomeDistribution = page.getByRole("combobox", { name: "Outcome distribution", exact: true });
  await outcomeDistribution.click();
  check(
    await page.getByRole("option", { name: "Log-normal (completion times)", exact: true }).count() === 0,
    "paired Wilcoxon plans do not offer unsupported log-normal assumptions",
  );
  check(await outcomeDistribution.isEnabled(), "paired Wilcoxon keeps supported distributions selectable");
  check(
    await page.getByText(/Log-normal assumptions are not supported for paired Wilcoxon plans/).isVisible(),
    "paired planner explains why log-normal assumptions are unavailable for Wilcoxon",
  );
  check(
    await page.getByText("Difference in outcome units.", { exact: true }).count() === 1 &&
      await page.getByText("Use the same units as the effect.", { exact: true }).count() === 1,
    "paired raw completion-time assumptions state their outcome units",
  );
  const manualPlanResponse = page.waitForResponse((response) =>
    response.url().endsWith(`/studies/${bare}/plan`) && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Calculate and save plan", exact: true }).click();
  const pairedPlanResponse = await manualPlanResponse;
  check(pairedPlanResponse.status() === 200, "paired manual protocol saves a supported recruitment plan");
  const pairedPlanFixture = await pairedPlanResponse.json();
  await page.getByText(/Saved plan \d+/).waitFor();
  check(true, "manual entry and Apply unlock Plan without reloading the page");

  const plannerPath = `${base}/studies/${bare}/plan`;
  let plannerFixtureMode = "saved-wilcoxon-log-normal";
  await page.route(plannerPath, async (route) => {
    if (plannerFixtureMode === "live") return route.continue();
    if (route.request().method() === "GET") {
      const response = await route.fetch();
      const doc = await response.json();
      if (plannerFixtureMode === "saved-wilcoxon-log-normal") {
        doc.plan.inputs.distribution = "log-normal";
        await route.fulfill({ response, json: doc });
        return;
      }
      const measure = doc.protocol.measures.find((item) => typeof item === "object");
      measure.analysisRecipe = "mean-comparison";
      measure.analysisScale = "log";
      doc.plan = {
        ...doc.plan,
        measureId: measure.id,
        inputs: {
          ...doc.plan.inputs,
          test: "paired-t",
          distribution: "log-normal",
        },
      };
      await route.fulfill({ response, json: doc });
      return;
    }
    if (route.request().method() === "POST") {
      if (plannerFixtureMode !== "paired-t-log-scale") return route.continue();
      const body = route.request().postDataJSON();
      check(
        body.test === "paired-t" && body.distribution === "log-normal",
        "paired t planner submits log-normal assumptions for a declared log-scale outcome",
      );
      await route.fulfill({
        status: 200,
        json: {
          ...pairedPlanFixture,
          inputs: body,
          measureId: body.measure_id,
          planId: 9001,
        },
      });
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await page.getByRole("button", { name: "Plan", exact: true }).click();
  await expect(outcomeDistribution).toHaveText("Normal");
  check(true, "an older unsupported paired Wilcoxon log-normal plan reopens on supported assumptions");

  plannerFixtureMode = "paired-t-log-scale";
  await page.getByRole("button", { name: "Run", exact: true }).click();
  await page.getByRole("button", { name: "Plan", exact: true }).click();
  await page.getByText("Log-normal (completion times)", { exact: true }).waitFor();
  await expect(outcomeDistribution).toHaveText("Log-normal (completion times)");
  await outcomeDistribution.click();
  check(
    await page.getByRole("option", { name: "Log-normal (completion times)", exact: true }).count() === 1 &&
      await page.getByRole("option", { name: "Ordinal (Likert ratings)", exact: true }).count() === 0,
    "paired t on a log-scale outcome offers only its supported log-normal assumptions",
  );
  await page.keyboard.press("Escape");
  check(
    await page.getByRole("button", { name: "Calculate and save plan", exact: true }).isEnabled(),
    "a paired t test with a declared log-scale measure remains plannable",
  );
  await page.getByText("Range, covariates and period assumptions", { exact: true }).click();
  const periodEffect = page.getByRole("spinbutton", { name: /Period effect/ });
  await periodEffect.fill("0.2");
  check(
    await page.getByRole("button", { name: "Calculate and save plan", exact: true }).isDisabled() &&
      await page.getByRole("status").filter({ hasText: /Analytic t planning requires zero period and order effects/ }).isVisible(),
    "paired t planning blocks unsupported nonzero period effects before submission",
  );
  await periodEffect.fill("0");
  const pairedLogResponse = page.waitForResponse((response) =>
    response.url().endsWith(`/studies/${bare}/plan`) && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Calculate and save plan", exact: true }).click();
  check((await pairedLogResponse).status() === 200, "paired log-scale t planning succeeds through the supported UI path");
  await page.getByText(/Saved plan 9001/).waitFor();
  plannerFixtureMode = "live";
  await page.unroute(plannerPath);

  await page.getByRole("button", { name: "Run", exact: true }).click();
  await page.waitForLoadState("networkidle");
  await auditPage(page, "typed protocol Run");
  check(!await page.getByText("Set up and apply a protocol before creating participant links.", { exact: false }).isVisible(), "manual save unlocks Run without reloading");
  await page.getByRole("button", { name: "Create participant links", exact: true }).click();
  await page.getByLabel("How many", { exact: true }).fill("0");
  await page.getByRole("button", { name: "Create links", exact: true }).click();
  check(await page.getByText("Enter a whole number from 1 to 100.", { exact: true }).isVisible(), "participant link count rejects zero before creating links");
  await page.getByLabel("How many", { exact: true }).fill("2");
  await page.getByText("Capture settings", { exact: true }).click();
  await auditPage(page, "participant capture settings dialog");
  await page.getByRole("button", { name: "Create 2 links", exact: true }).click();
  await page.getByRole("textbox", { name: "Connection link for P01", exact: true }).waitFor();
  check(await page.getByRole("textbox", { name: /Connection link for P\d+/ }).count() === 2, "participant links mint from the saved protocol");
  await auditPage(page, "created participant links dialog");
  await page.getByRole("button", { name: "Done", exact: true }).click();
  const editorLinks = await page.getByRole("link", { name: /Open in VS Code/ }).evaluateAll((elements) => elements.map((element) => element.href));
  check(editorLinks.length === 2 && editorLinks.every((href) => {
    const link = new URL(href);
    return link.protocol === "vscode:" && link.hostname === `${extension.publisher}.${extension.name}` && link.searchParams.get("c")?.startsWith(base + "#");
  }), "participant links open the installed extension with the correct enrollment token");
  await page.getByText("Install TERN in VS Code", { exact: true }).click();
  const release = await page.getByRole("link", { name: "Download the .vsix", exact: true }).getAttribute("href");
  check(release?.startsWith(extension.repository.url.replace(/\.git$/, "")), "extension download points to its release repository");
  await page.getByRole("button", { name: "Data", exact: true }).click();
  await page.locator("summary").filter({ hasText: /^Outcome capture checks$/ }).click();
  await auditPage(page, "typed protocol Data");
  const captureChecks = page.getByRole("region", { name: "Outcome capture checks", exact: true });
  const checksPath = `/studies/${bare}/outcome-checks`;
  await page.route(`**${checksPath}`, (route) => route.abort("failed"));
  await captureChecks.getByRole("button", { name: "Check captured inputs", exact: true }).click();
  await captureChecks.getByRole("alert").waitFor();
  check(await captureChecks.getByRole("button", { name: "Download checks (.json)", exact: true }).count() === 0, "failed outcome checks expose recovery without a stale report");
  await page.unroute(`**${checksPath}`);
  await captureChecks.getByRole("button", { name: "Check captured inputs", exact: true }).click();
  await captureChecks.getByRole("status").filter({ hasText: "0 sessions checked" }).waitFor();
  check(true, "outcome checks distinguish no rehearsal data from missing measurements");
  const pairingToken = new URL(editorLinks[0]).searchParams.get("c").split("#").at(-1);
  const paired = await api("/pair/redeem", { method: "POST", body: JSON.stringify({ token: pairingToken }) });
  const participantHeaders = { "Content-Type": "application/json", Authorization: `Bearer ${paired.sessionCredential}` };
  const captureEvent = async (sessionId, seq, payload) => {
    const configResponse = await fetch(`${base}/studies/${bare}/capture-config?sessionId=${sessionId}`, { headers: participantHeaders });
    if (!configResponse.ok) throw new Error("Rehearsal capture configuration failed");
    const config = await configResponse.json();
    const response = await fetch(`${base}/ingest/events`, { method: "POST", headers: participantHeaders, body: JSON.stringify([
      { sessionId, seq, v: 6, ts: new Date(Date.now() + seq).toISOString(), source: "task-harness", taskId: config.block.taskId, type: "task_outcome", payload },
    ]) });
    if (!response.ok) throw new Error("Rehearsal event ingest failed");
  };
  const captureFlaggedEvent = async (sessionId) => {
    const configResponse = await fetch(`${base}/studies/${bare}/capture-config?sessionId=${sessionId}`, { headers: participantHeaders });
    if (!configResponse.ok) throw new Error("Flagged rehearsal configuration failed");
    const config = await configResponse.json();
    const response = await fetch(`${base}/ingest/events`, { method: "POST", headers: participantHeaders, body: JSON.stringify([
      {
        sessionId, seq: 0, v: 6, ts: new Date().toISOString(), source: "task-harness",
        participantId: "P99", condition: config.block.condition, taskId: config.block.taskId,
        type: "edit_burst", payload: { charsAdded: 80, charsDeleted: 0, linesTouched: 1, durationMs: 1000, origin: "human" },
      },
    ]) });
    if (!response.ok) throw new Error("Flagged rehearsal event ingest failed");
  };
  await captureEvent("browser-outcome-rehearsal-a", 0, { passed: true, failed: 0, total: 0 });
  await captureChecks.getByRole("button", { name: "Check again", exact: true }).click();
  await captureChecks.getByRole("status").filter({ hasText: "1 session checked" }).waitFor();
  for (const summary of await captureChecks.locator("details > summary").all()) await summary.click();
  check(await captureChecks.getByText("No coherent, nonempty test run was recorded.", { exact: true }).isVisible(), "outcome checks detect a fake passing result with no executed tests");
  await auditPage(page, "outcome capture discrepancies");
  if (values.screenshots) {
    const details = captureChecks.locator("details");
    await details.evaluateAll((elements) => elements.forEach((element, index) => { element.open = index === 0; }));
    await captureChecks.evaluate((element) => element.scrollIntoView({ block: "start" }));
    await page.screenshot({ path: join(values.screenshots, "outcome-checks-desktop.png"), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await captureChecks.evaluate((element) => element.scrollIntoView({ block: "start" }));
    await page.screenshot({ path: join(values.screenshots, "outcome-checks-mobile.png"), fullPage: true });
    await page.setViewportSize({ width: 1280, height: 800 });
  }
  await captureEvent("browser-outcome-rehearsal-a", 1, { passed: true, failed: 0, total: 3, firstGreenMs: 1000 });
  await captureEvent("browser-outcome-rehearsal-b", 0, { passed: true, failed: 0, total: 3, firstGreenMs: 1200 });
  await captureChecks.getByRole("button", { name: "Check again", exact: true }).click();
  await captureChecks.getByRole("status").filter({ hasText: "2 sessions checked" }).waitFor();
  await page.getByRole("button").filter({ hasText: "browser-outcome-rehearsal-b" }).waitFor();
  check(true, "checking capture refreshes the session list without discarding the report");
  const correctedCapture = await api(checksPath);
  check(correctedCapture.outcomes.some((outcome) => outcome.fields.includes("task_outcome.firstGreenMs") && outcome.observedUnits === 2 && outcome.pairedParticipants === 1), "outcome checks count session units and paired participant coverage after repair");
  const reportDownload = page.waitForEvent("download");
  await captureChecks.getByRole("button", { name: "Download checks (.json)", exact: true }).click();
  const exportedChecks = JSON.parse(readFileSync(await (await reportDownload).path(), "utf8"));
  check(exportedChecks.protocolHash === correctedCapture.protocolHash && exportedChecks.dataHash === correctedCapture.dataHash, "downloaded outcome checks retain the exact protocol and data fingerprints");
  const flaggedSessionId = "browser-flagged-integrity";
  await captureFlaggedEvent(flaggedSessionId);
  const integrityStatus = await api(`/studies/${bare}/status`);
  const integritySession = integrityStatus.sessions.find((session) => session.sessionId === flaggedSessionId);
  check(integritySession?.complete === true && integritySession.flaggedEvents > 0, "integrity fixture has complete event sequencing and flagged events");
  await page.reload();
  await page.locator("summary").filter({ hasText: /^Outcome capture checks$/ }).click();
  const capturedSessions = page.getByRole("region", { name: "Captured sessions", exact: true });
  const flaggedCard = capturedSessions.getByRole("button").filter({ hasText: flaggedSessionId });
  await flaggedCard.waitFor();
  await expect(flaggedCard).toContainText("Review capture · 1 flagged event");
  await expect(flaggedCard).not.toContainText("no flags");
  await flaggedCard.click();
  await capturedSessions.getByText("credential-mismatch", { exact: true }).waitFor();
  check(true, "a complete sequence with flagged rows is visibly marked for capture review");
  const sessionReview = page.getByRole("region", { name: "Session review", exact: true });
  await sessionReview.getByRole("combobox", { name: "Show sessions", exact: true }).click();
  await page.getByRole("option", { name: "All sessions", exact: true }).click();
  await sessionReview.getByRole("searchbox", { name: "Search review sessions", exact: true }).fill(flaggedSessionId);
  await sessionReview.getByRole("button", { name: /^P\d+/ }).first().click();
  await sessionReview.getByText(`Session: ${flaggedSessionId}`, { exact: true }).waitFor();
  await sessionReview.getByRole("combobox", { name: /Include in analysis/ }).click();
  await page.getByRole("option", { name: "Exclude", exact: true }).click();
  await sessionReview.getByRole("textbox", { name: "Reason for the decision or pilot tag", exact: true }).fill("Synthetic browser fixture: exclude flagged capture from analysis.");
  await sessionReview.getByRole("button", { name: "Save decision", exact: true }).click();
  await sessionReview.getByText(/Last recorded by/).waitFor();
  check(await sessionReview.getByRole("textbox", { name: "Reason for the decision or pilot tag", exact: true }).isVisible(), "saving a session decision preserves the selected review and expanded row");
  const flaggedDecision = await api(`/studies/${bare}/plan`);
  check(flaggedDecision.decisions[flaggedSessionId]?.decision === "exclude", "the flagged session exclusion is persisted in the study plan");
  const annotatedRows = (await api(`/studies/${bare}/dataset`)).rows.filter((row) => row.sessionId === flaggedSessionId);
  check(annotatedRows.length > 0 && annotatedRows.every((row) => row.inclusionDecision === "exclude"), "excluded raw rows retain their decision for downstream filtering");
  await captureChecks.getByRole("button", { name: "Check captured inputs", exact: true }).waitFor();
  check(true, "changing an inclusion decision clears an outdated outcome report");
  await page.getByText("Download study records", { exact: true }).click();
  for (const name of ["Data (.zip)", "Design card (.md)", "Replication kit"]) {
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name, exact: true }).click();
    const file = await download;
    check(await file.failure() === null, `${name}: generated download completes`);
  }
  check(true, "manual save unlocks Data without reloading");
  await page.close();

  const starter = await context.newPage();
  await starter.goto(`${base}/repertoire`);
  await starter.getByRole("button", { name: "Use this template", exact: true }).first().click();
  // A template opens in Setup as an unapplied draft; Plan unlocks after Apply.
  await starter.getByRole("heading", { name: "Your draft starts from the template" }).waitFor();
  await auditPage(starter, "template study before apply");
  await starter.getByRole("button", { name: "Review draft", exact: true }).last().click();
  await expect(starter.getByRole("heading", { name: "Current protocol", exact: true })).toBeVisible();
  await expect(starter.getByText("No decisions from the chat yet")).toBeHidden();
  await starter.getByText("Decision history", { exact: true }).click();
  await expect(starter.getByText("No decisions from the chat yet")).toBeVisible();
  await starter.getByRole("dialog", { name: "Review draft" }).getByRole("button", { name: "Apply protocol", exact: true }).click();
  await starter.getByRole("link", { name: /Applied\. Plan recruitment/ }).click();
  await starter.getByRole("heading", { name: "Plan participant recruitment" }).waitFor();
  await starter.getByRole("button", { name: "Calculate and save plan", exact: true }).click();
  await starter.getByText(/Saved plan \d+/).waitFor();
  await auditPage(starter, "saved featured plan");
  check(new URL(starter.url()).searchParams.get("tab") === "planning", "featured starter reaches a saved plan without typing a protocol");
  await starter.close();

  const taskStudy = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "Two-task fixture" }) })).id;
  const taskPage = await context.newPage();
  await taskPage.setViewportSize({ width: 390, height: 844 });
  await taskPage.goto(`${base}/p/implicit/studies/${taskStudy}?tab=conversation`);
  await taskPage.getByRole("button", { name: "Research tools" }).click();
  await taskPage.getByRole("menuitem", { name: "Enter protocol manually" }).click();
  for (const [id, text] of Object.entries({
    "manual-title": "Two-task study", "manual-rq-0": "Does AI change debugging time?",
    "manual-condition-0": "AI-assisted", "manual-condition-1": "Unassisted",
    "manual-participants": "Python developers", "manual-planned": "12",
    "manual-minutes": "45", "manual-task": "Fix the first failing test.",
  })) await taskPage.locator(`#${id}`).fill(text);
  await taskPage.getByRole("checkbox", { name: "Time to first passing test" }).check();
  await taskPage.getByRole("button", { name: "Add task", exact: true }).click();
  await taskPage.locator("#manual-task-desc-1").fill("Fix the second failing test.");
  await taskPage.locator("#manual-task-minutes-0").fill("15");
  await taskPage.locator("#manual-task-minutes-1").fill("15");
  await taskPage.getByRole("button", { name: "Add task", exact: true }).click();
  await taskPage.locator("#manual-task-desc-2").fill("Fix the third failing test.");
  await taskPage.locator("#manual-task-minutes-2").fill("10");
  await taskPage.locator("#manual-task-materials-2").fill("fixtures/third-task");
  await taskPage.locator("#manual-task-version-2").fill("commit-a1b2c3");
  const taskSave = taskPage.waitForResponse((response) => response.url().endsWith(`/studies/${taskStudy}/quick-protocol`) && response.request().method() === "POST");
  await taskPage.getByRole("button", { name: "Save draft" }).click();
  const taskPayload = await (await taskSave).json();
  const initialTasks = taskPayload.protocol?.tasks ?? [];
  check(initialTasks.length === 3 && initialTasks[0].minutes === 15 && initialTasks[2].minutes === 10, "manual entry saves an ordered task list with timing");
  check(initialTasks[2].materials === "fixtures/third-task" && initialTasks[2].version === "commit-a1b2c3", "manual entry records task materials and revision");
  await taskPage.getByRole("dialog").waitFor({ state: "hidden" });

  // Reopen the saved draft and exercise editing, reordering and removing an
  // existing task. The ids of the two retained tasks must survive.
  await taskPage.getByRole("button", { name: "Research tools" }).click();
  await taskPage.getByRole("menuitem", { name: "Enter protocol manually" }).click();
  await taskPage.getByRole("button", { name: "Move task 3 up" }).waitFor();
  if (values.screenshots) {
    await taskPage.locator("#manual-task").scrollIntoViewIfNeeded();
    await settleVisual(taskPage);
    await taskPage.screenshot({ path: join(values.screenshots, "tasks-editor-mobile.png"), fullPage: true });
    await taskPage.setViewportSize({ width: 1280, height: 800 });
    await settleVisual(taskPage);
    await taskPage.screenshot({ path: join(values.screenshots, "tasks-editor-desktop.png"), fullPage: true });
    await taskPage.setViewportSize({ width: 390, height: 844 });
  }
  await taskPage.getByRole("button", { name: "Move task 3 up" }).click();
  await taskPage.getByRole("button", { name: "Remove task 3" }).click();
  await taskPage.locator("#manual-task").fill("Fix the updated first failing test.");
  const revisedTaskSave = taskPage.waitForResponse((response) => response.url().endsWith(`/studies/${taskStudy}/quick-protocol`) && response.request().method() === "POST");
  await taskPage.getByRole("button", { name: "Save draft" }).click();
  const revisedTasks = (await (await revisedTaskSave).json()).protocol?.tasks ?? [];
  check(revisedTasks.length === 2 && revisedTasks[0].id === initialTasks[0].id && revisedTasks[1].id === initialTasks[2].id, "editing a saved protocol preserves retained task ids and applies the chosen order");
  check(revisedTasks[0].description === "Fix the updated first failing test.", "editing a saved task updates its description");
  check(revisedTasks[1].materials === "fixtures/third-task" && revisedTasks[1].version === "commit-a1b2c3", "reordering tasks preserves each task's materials and revision");
  await expect(taskPage.getByText("Updated the manual protocol: Does AI change debugging time?", { exact: true })).toBeVisible();
  await taskPage.getByRole("dialog").waitFor({ state: "hidden" });
  await taskPage.getByRole("button", { name: "Review draft", exact: true }).last().click();
  const taskReview = taskPage.getByRole("dialog", { name: "Review draft" });
  await expect(taskReview.getByText(/Task 2: Fix the third failing test.*10 min/)).toBeVisible();
  await expect(taskReview.getByText(/Materials: fixtures\/third-task.*Version: commit-a1b2c3/)).toBeVisible();
  await expect(taskReview.getByRole("listitem").filter({ hasText: "Task 1: Fix the updated first failing test" })).toBeVisible();
  check(true, "the review shows the saved tasks once, with timing and materials");
  if (values.screenshots) {
    await settleVisual(taskPage);
    await taskPage.screenshot({ path: join(values.screenshots, "task-review-mobile.png"), fullPage: true });
    await taskPage.setViewportSize({ width: 1280, height: 800 });
    await settleVisual(taskPage);
    await taskPage.screenshot({ path: join(values.screenshots, "task-review-desktop.png"), fullPage: true });
  }
  await taskPage.close();

  // Failed transport must leave the message editable, and the next Send must
  // actually retry the same request instead of silently becoming a local turn.
  const chatStudy = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "Chat recovery fixtures" }) })).id;
  const chat = await context.newPage();
  const chatRequests = [];
  const recoveredReply = "Synthetic transport fixture: your research question was received.";
  let chatMode = "offline";
  const chatErrors = {
    validation: { status: 422, detail: [{ loc: ["body", "text"], msg: "Text must contain valid Unicode characters." }], message: "Text must contain valid Unicode characters." },
    forbidden: { status: 403, detail: "Only project contributors can send messages.", message: "Only project contributors can send messages." },
    conflict: { status: 409, detail: "Refresh the conversation and try again.", message: "Refresh the conversation and try again." },
    limited: { status: 429, detail: "Too many requests. Wait a few seconds and try again.", message: "Too many requests. Wait a few seconds and try again." },
  };
  let releasePending;
  const pendingGate = new Promise((resolve) => { releasePending = resolve; });
  let releaseOffline;
  const offlineGate = new Promise((resolve) => { releaseOffline = resolve; });
  await chat.route(new RegExp(`/studies/${chatStudy}/conversation/turns(?:/stream)?$`), async (route) => {
    const request = route.request();
    const body = request.postDataJSON();
    chatRequests.push({ path: new URL(request.url()).pathname, ...body });
    if (chatErrors[chatMode]) {
      const error = chatErrors[chatMode];
      return route.fulfill({ status: error.status, contentType: "application/json", body: JSON.stringify({ detail: error.detail }) });
    }
    if (chatMode === "offline") {
      await offlineGate;
      return route.abort("connectionfailed");
    }
    if (chatMode === "truncated") return route.fulfill({ status: 200, contentType: "text/event-stream", body: 'event: token\ndata: {"text":"Synthetic partial reply"}\n\n' });
    if (chatMode === "pending") {
      await pendingGate;
      return route.abort("aborted").catch(() => {}); // Stop already aborted this request.
    }
    const reply = { researcherTurnId: "fixture-researcher", platformTurnId: "fixture-platform", text: recoveredReply, moves: [], recommendations: [], source: "llm" };
    return route.fulfill({ status: 200, contentType: "text/event-stream", body: `event: token\ndata: ${JSON.stringify({ text: recoveredReply })}\n\nevent: done\ndata: ${JSON.stringify(reply)}\n\n` });
  });
  await chat.route(`${base}/studies/${chatStudy}/conversation`, (route) => route.abort("connectionfailed"), { times: 1 });
  await chat.goto(`${base}/p/implicit/studies/${chatStudy}?tab=conversation`);
  const composer = chat.getByRole("textbox", { name: "Message the design assistant", exact: true });
  const send = chat.getByRole("button", { name: "Send", exact: true });
  const retryLoad = chat.getByRole("button", { name: "Retry conversation", exact: true });
  await retryLoad.waitFor();
  check(await composer.count() === 0, "chat: an unread conversation shows a retry and prevents writes");
  const compiled = chat.waitForResponse((response) => response.url().endsWith(`/studies/${chatStudy}/conversation/compile`));
  await retryLoad.click();
  await compiled;
  check(await send.isDisabled(), "chat: blank messages cannot be submitted");
  await composer.fill("My existing question");
  await chat.getByRole("button", { name: "Enter protocol manually", exact: true }).click();
  await chat.getByRole("dialog").getByRole("button", { name: "Cancel" }).click();
  check(await composer.inputValue() === "My existing question", "chat: opening and cancelling manual entry preserves the draft");
  await composer.fill("");
  const compileRequests = [];
  chat.on("request", (request) => {
    if (request.url().endsWith(`/studies/${chatStudy}/conversation/compile`)) compileRequests.push(request);
  });
  const chatText = "Does AI change debugging time?\nDevelopers: naïve, 日本語, العربية 🔬 <script>window.fixtureRan=true</script>";
  await composer.fill(chatText);
  await chat.getByRole("button", { name: "Plan", exact: true }).click();
  await chat.getByRole("button", { name: "Setup", exact: true }).click();
  await expect(composer).toHaveValue(chatText);
  check(true, "chat: moving between Setup and Plan preserves unsent multiline text");
  await composer.press("Enter");
  await chat.getByRole("button", { name: "Stop reply", exact: true }).waitFor();
  await expect(composer).toBeFocused();
  releaseOffline();
  await chat.getByRole("status").filter({ hasText: "Connection interrupted." }).waitFor();
  await expect(composer).toBeFocused();
  check(await composer.inputValue() === chatText, "chat: a failed stream and fallback restore the complete Unicode message");
  check(chatRequests.length === 2 && chatRequests[0].requestId === chatRequests[1].requestId, "chat: fallback reuses the original request id");
  chatMode = "recovered";
  await send.click();
  await chat.getByText(recoveredReply, { exact: true }).waitFor({ timeout: 2500 }).catch(() => {});
  check(chatRequests.length === 3 && chatRequests[2].requestId === chatRequests[0].requestId, "chat: Send after recovery reaches the server with the same request id");
  check(await chat.getByText(recoveredReply, { exact: true }).count() > 0 && await composer.inputValue() === "", "chat: retry renders the recovered reply and clears the composer");
  check(await chat.evaluate(() => window.fixtureRan !== true && !document.querySelector("#root script")), "chat: user HTML remains text and never executes");
  chatMode = "truncated";
  const interruptedText = "Keep this message when the connection drops during a reply.";
  await composer.fill(interruptedText);
  await send.click();
  await chat.getByRole("status").filter({ hasText: "Connection interrupted." }).waitFor();
  check(chatRequests.length === 4 && await composer.inputValue() === interruptedText, "chat: a partial stream restores input without an automatic duplicate POST");
  chatMode = "recovered";
  await send.click();
  await chat.getByRole("button", { name: "Stop reply", exact: true }).waitFor({ state: "hidden" });
  check(chatRequests.length === 5 && chatRequests[4].requestId === chatRequests[3].requestId, "chat: retry after a partial stream preserves request identity");
  chatMode = "pending";
  const stoppedText = "Let me stop this slow reply and edit the research question.";
  await composer.fill(stoppedText);
  const pendingRequest = chat.waitForRequest((request) => request.url().endsWith(`/studies/${chatStudy}/conversation/turns/stream`));
  await send.click();
  await pendingRequest;
  await chat.getByRole("button", { name: "Stop reply", exact: true }).click();
  await chat.getByRole("status").filter({ hasText: "Stopped. Your message is back in the box." }).waitFor();
  await expect(composer).toBeFocused();
  check(chatRequests.length === 6 && await composer.inputValue() === stoppedText, "chat: Stop restores editable text without a fallback POST");
  releasePending();
  for (const [mode, error] of Object.entries(chatErrors)) {
    chatMode = mode;
    const before = chatRequests.length;
    const text = `Preserve my message after ${mode}: العربية 日本語 🔬`;
    await composer.fill(text);
    const refused = chat.waitForResponse((response) => response.url().endsWith(`/studies/${chatStudy}/conversation/turns/stream`) && response.request().method() === "POST");
    await send.click();
    await refused;
    await expect(composer).toHaveValue(text);
    await chat.getByRole("button", { name: "Stop reply", exact: true }).waitFor({ state: "hidden" });
    check(chatRequests.length === before + 1, `chat: ${error.status} does not cause an automatic duplicate POST`);
    check(await composer.inputValue() === text, `chat: ${error.status} preserves the editable message`);
    check(await chat.getByRole("status").filter({ hasText: error.message }).isVisible(), `chat: ${error.status} explains the server refusal without calling it offline`);
  }
  chatMode = "recovered";
  const decisionLikeMessage = "I accepted: the limitations of this design still matter.";
  const compiledBeforeReply = compileRequests.length;
  await composer.fill(decisionLikeMessage);
  await send.click();
  await chat.getByRole("button", { name: "Stop reply", exact: true }).waitFor({ state: "hidden" });
  check(await chat.getByText(decisionLikeMessage, { exact: true }).isVisible(), "chat: a typed message is not hidden because it resembles a card decision");
  check(compileRequests.length === compiledBeforeReply, "chat: receiving a text-only reply does not write another compilation");
  await auditPage(chat, "chat transport recovery");
  await chat.close();

  // Deliver fragments separately so scrolling and the final handoff are
  // exercised while the reply is actually growing.
  const streamStudy = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "Long reply fixture" }) })).id;
  const streamPage = await context.newPage();
  await streamPage.setViewportSize({ width: 390, height: 720 });
  await streamPage.emulateMedia({ reducedMotion: "reduce" });
  await streamPage.addInitScript(() => {
    const fetchRequest = window.fetch;
    window.fetch = (input, init) => {
      if (!String(input).endsWith("/conversation/turns/stream")) return fetchRequest(input, init);
      return Promise.resolve(new Response(new ReadableStream({
        start(controller) {
          const encoder = new TextEncoder();
          window.pushReplyFrame = (event, data) => controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
        },
      }), { headers: { "content-type": "text/event-stream" } }));
    };
  });
  await streamPage.goto(`${base}/p/implicit/studies/${streamStudy}?tab=conversation`);
  const welcomeThread = streamPage.getByRole("region", { name: "Conversation", exact: true });
  const welcome = streamPage.getByRole("region", { name: "Start the study design", exact: true });
  const welcomeCenter = async () => welcome.evaluate((el) => {
    const region = el.getBoundingClientRect();
    const viewport = el.closest('[aria-label="Conversation"]').getBoundingClientRect();
    return (region.top + region.height / 2 - viewport.top) / viewport.height;
  });
  await expect.poll(welcomeCenter).toBeGreaterThan(0.42);
  await expect.poll(welcomeCenter).toBeLessThan(0.68);
  if (values.screenshots) await streamPage.screenshot({ path: join(values.screenshots, "study-start-mobile.png") });
  await streamPage.setViewportSize({ width: 1280, height: 900 });
  await expect.poll(welcomeCenter).toBeGreaterThan(0.42);
  await expect.poll(welcomeCenter).toBeLessThan(0.68);
  if (values.screenshots) await streamPage.screenshot({ path: join(values.screenshots, "study-start-desktop.png") });
  await streamPage.setViewportSize({ width: 390, height: 720 });
  await streamPage.getByText("Example questions", { exact: true }).click();
  await streamPage.getByRole("button", { name: "Debugging time", exact: true }).click();
  const streamComposer = streamPage.getByRole("textbox", { name: "Message the design assistant" });
  await expect(streamComposer).toHaveValue(/Compare how long debugging takes/);
  await expect(streamComposer).toBeFocused();
  await expect(streamPage.getByRole("button", { name: "Debugging time", exact: true })).toBeHidden();
  await streamComposer.press("Enter");
  const thread = streamPage.getByRole("region", { name: "Conversation", exact: true });
  await expect(thread.getByText("Preparing reply…", { exact: true })).toBeVisible();
  const distance = () => thread.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight);
  const push = (text) => streamPage.evaluate((fragment) => window.pushReplyFrame("token", { text: fragment }), text);
  const first = "## Study setup\n- Use matched tasks.\nKeep the same instructions.\n2. Record task time.\n\n" + Array.from({ length: 18 }, (_, index) => `Observation ${index + 1}. Repeat the instructions consistently across the two study conditions.`).join("\n\n");
  await push(first);
  await expect(thread.getByText(/^Observation 18\./)).toBeVisible();
  const replyStart = thread.getByText("Study setup", { exact: true });
  const startOffset = async (locator) => (await locator.boundingBox()).y - (await thread.boundingBox()).y;
  await expect.poll(() => startOffset(replyStart)).toBeGreaterThanOrEqual(0);
  await expect.poll(() => startOffset(replyStart)).toBeLessThan(150);
  await thread.press("Home");
  const latest = streamPage.getByRole("button", { name: "Jump to latest" });
  await expect(latest).toBeVisible();
  await expect.poll(() => thread.evaluate((el) => el.scrollTop)).toBeLessThanOrEqual(24);
  const tail = "\n\nLast fragment with **emphasis**.\n\n" + "x".repeat(500);
  await push(tail);
  await expect(thread.getByText("Last fragment with", { exact: false })).toBeVisible();
  await expect.poll(() => thread.evaluate((el) => el.scrollTop)).toBeLessThanOrEqual(24);
  if (values.screenshots) await streamPage.screenshot({ path: join(values.screenshots, "chat-reading-mobile.png") });
  await latest.click();
  await expect.poll(distance).toBeLessThanOrEqual(2);
  await expect(thread).toBeFocused();
  await streamPage.evaluate((text) => {
    window.pushReplyFrame("done", { researcherTurnId: "stream-user", platformTurnId: "stream-assistant", text, moves: [], recommendations: [], source: "llm" });
  }, first + tail);
  await expect(streamPage.getByRole("button", { name: "Stop reply" })).toBeHidden();
  await expect(thread.getByRole("heading", { name: "Study setup" })).toBeAttached();
  await expect(thread.getByRole("listitem").filter({ hasText: "Record task time." })).toBeAttached();
  await expect(thread.getByText("Keep the same instructions.", { exact: true })).toBeAttached();
  await expect.poll(distance).toBeLessThanOrEqual(8);
  await expect(thread).toBeFocused();
  check(await thread.evaluate((el) => el.scrollWidth <= el.clientWidth), "chat: streaming preserves reading position and wraps long tokens");

  // A short reply followed by several tall proposals should land at the
  // researcher's message and the reply, even when the stream sends no tokens.
  const followUp = "Yes, use a small Python bug fix.";
  await streamPage.route(`${base}/studies/${streamStudy}/conversation/moves/*/decision`, (route) => route.fulfill({
    json: { moveId: route.request().url().split("/").at(-2), status: route.request().postDataJSON().status },
  }));
  await streamComposer.fill(followUp);
  await streamComposer.press("Enter");
  await expect(thread.getByText("Preparing reply…", { exact: true })).toBeVisible();
  await streamPage.evaluate(() => {
    window.pushReplyFrame("done", {
      researcherTurnId: "follow-up-user", platformTurnId: "follow-up-assistant",
      text: "Use a matched bug fix in both conditions. Review the draft changes below.",
      moves: Array.from({ length: 5 }, (_, index) => ({
        moveId: `fixture-proposal-${index}`, kind: "set-plan", target: "study",
        proposal: `Draft proposal ${index + 1}. ${"Record assigned task materials and starting code. ".repeat(3)}`,
        status: "proposed",
        grounding: index === 0 ? [{
          ref: "doi:10.1234/long-abstract", confidence: 0.84,
          title: "Long abstract citation fixture", year: 2026, venue: "Synthetic study methods journal",
          why: "A deliberately long synthetic abstract tests the citation popover: " + "This paper discusses the research context, study methods, participant population, task materials, measures, analysis plan, and limitations in detail. ".repeat(18),
        }] : [],
      })),
      recommendations: [], source: "llm",
    });
  });
  const freshReply = thread.getByRole("paragraph").filter({ hasText: "Use a matched bug fix" });
  await expect(freshReply).toBeAttached();
  if (values.screenshots) await streamPage.screenshot({ path: join(values.screenshots, "new-reply-position-390.png") });
  await expect(freshReply).toBeInViewport();
  await expect(thread.getByText(followUp, { exact: true })).toBeInViewport();
  await expect(thread.locator('[data-move-id="fixture-proposal-0"]')).toBeInViewport();
  const proposals = thread.locator('[data-move-id^="fixture-proposal-"]:visible');
  await expect(proposals).toHaveCount(2);
  await expect(thread.getByText("3 more decisions waiting", { exact: true })).toBeVisible();
  await expect.poll(distance).toBeGreaterThan(100);
  await expect(streamComposer).toBeFocused();
  await streamPage.getByRole("button", { name: "Cited paper: Long abstract citation fixture" }).hover();
  const citationPopup = streamPage.locator(".citation-tooltip:visible");
  await expect(citationPopup).toBeVisible();
  const citationBounds = await citationPopup.boundingBox();
  const citationFits = await citationPopup.evaluate((el) => {
    const rect = el.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= innerHeight && rect.height <= 320;
  });
  check(Boolean(citationBounds) && citationFits, "chat: long abstracts stay in a compact citation popover within the viewport");
  check(await citationPopup.locator(".line-clamp-4").evaluate((el) => getComputedStyle(el).webkitLineClamp) === "4", "chat: citation popovers preview long paper text without dumping the abstract");
  if (values.screenshots) await streamPage.screenshot({ path: join(values.screenshots, "citation-popover-390.png") });
  await streamPage.mouse.move(0, 0);
  await expect(citationPopup).toBeHidden();
  if (values.screenshots) {
    for (const width of [390, 1280]) {
      await streamPage.setViewportSize({ width, height: 800 });
      await settleVisual(streamPage);
      if (values.screenshots) await streamPage.screenshot({ path: join(values.screenshots, `new-reply-resize-${width}.png`) });
      await expect(thread.getByText(followUp, { exact: true })).toBeInViewport();
      await streamPage.screenshot({ path: join(values.screenshots, `new-reply-start-${width}.png`) });
    }
  }
  await thread.getByRole("button", { name: "Accept both", exact: true }).click();
  await expect(thread.locator('[data-move-id="fixture-proposal-2"]')).toBeFocused();
  await expect(proposals).toHaveCount(2);
  await expect(thread.getByText("1 more decision waiting", { exact: true })).toBeVisible();
  await thread.locator('[data-move-id="fixture-proposal-2"]').press("r");
  await expect(thread.locator('[data-move-id="fixture-proposal-4"]')).toBeVisible();
  await expect(thread.getByText(/more decisions? waiting/)).toHaveCount(0);
  await thread.getByText("Decisions (3)", { exact: true }).click();
  await thread.locator('[data-move-id="fixture-proposal-2"]').getByRole("button", { name: "Undo" }).press("Enter");
  await expect(thread.locator('[data-move-id="fixture-proposal-2"]')).toBeFocused();
  await expect(thread.locator('[data-move-id="fixture-proposal-4"]')).toHaveCount(0);
  check(true, "chat: two pending decisions advance in order, and Undo brings its card back into view");

  // A question is the only choice on screen, even if the response or an older
  // turn has pending proposals. Those proposals return after the answer lands.
  await streamComposer.fill("Let's settle the outcome first.");
  await streamComposer.press("Enter");
  await expect(thread.getByText("Preparing reply…", { exact: true })).toBeVisible();
  await streamPage.evaluate(() => {
    window.pushReplyFrame("done", {
      researcherTurnId: "clarification-user", platformTurnId: "clarification-assistant",
      text: "We can decide the outcome first.",
      questions: [{ ask: "Which outcome matters most?", options: ["Time to first passing test", "Workload"] }],
      moves: [{
        moveId: "proposal-during-question", kind: "set-plan", target: "plan.design",
        proposal: "A counterbalanced within-subjects design.",
        patch: { part: "design", plan: { design: "within-subjects", conditions: ["baseline", "Copilot"] }, before: {}, suggested: [] },
        status: "proposed", grounding: [],
      }],
      recommendations: [], source: "llm",
    });
  });
  const outcomeAnswers = thread.getByRole("group", { name: "Answers to: Which outcome matters most?" });
  await expect(outcomeAnswers).toBeVisible();
  await expect(outcomeAnswers).toBeInViewport();
  await expect(thread.locator('[data-move-id="proposal-during-question"]')).toHaveCount(0);
  await expect(thread.getByText(/more decisions? waiting/)).toHaveCount(0);
  if (values.screenshots) await streamPage.screenshot({ path: join(values.screenshots, "question-only-1280.png") });
  await outcomeAnswers.getByRole("button", { name: "Time to first passing test", exact: true }).click();
  await expect(thread.getByText("Preparing reply…", { exact: true })).toBeVisible();
  await streamPage.evaluate(() => {
    window.pushReplyFrame("done", {
      researcherTurnId: "outcome-answer", platformTurnId: "outcome-follow-up",
      text: "Time to first passing test will be the primary outcome.",
      questions: [], moves: [], recommendations: [], source: "llm",
    });
  });
  await expect(thread.locator('[data-move-id^="fixture-proposal-"]:visible')).toHaveCount(2);
  await expect(thread.getByText(/more decisions? waiting/)).toBeVisible();
  check(true, "chat: pending questions hide every proposal until the researcher answers");
  await streamPage.close();

  const answerStudy = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "Assistant answers fixture" }) })).id;
  const answers = await context.newPage();
  await answers.setViewportSize({ width: 320, height: 620 });
  await answers.emulateMedia({ reducedMotion: "reduce" });
  const answerPath = `${base}/studies/${answerStudy}`;
  const question = "Which design fits the study?";
  const answer = "Assign different participants to assisted and unassisted debugging conditions, using the same starting code and acceptance tests for both groups.";
  const draftAnswer = "Unsent notes about the participant recruitment window.";
  const planMove = (moveId, title, status = "proposed") => ({
    moveId, kind: "set-plan", target: "study", proposal: title, status, grounding: [],
    patch: { part: "title", plan: { title }, before: {} },
  });
  const originalMove = planMove("original:title", "Original study name");
  const replacement = planMove("updated:title", "Updated study name");
  // A card the next reply leaves open: it gathers under that reply.
  const openDesign = {
    moveId: "original:design", kind: "set-plan", target: "plan.design", proposal: "Use a within-subjects design.", status: "proposed", grounding: [],
    patch: { part: "design", plan: { design: "within-subjects" }, before: {} },
  };
  const firstReply = {
    turnId: "original", role: "platform", text: "Here is a setup option.",
    moves: [originalMove, openDesign], recommendations: [],
    questions: [{ ask: question, options: [answer, "Use the same participants in both conditions"] }],
  };
  const nextReply = {
    turnId: "updated", role: "platform", text: "I updated the study name.",
    moves: [replacement], recommendations: [],
  };
  let answerSaved = false;
  const answerRequests = [];
  await answers.route(`${answerPath}/conversation`, (route) => route.fulfill({
    json: { turns: answerSaved
      ? [{ ...firstReply, moves: [{ ...originalMove, status: "superseded" }, openDesign] }, nextReply]
      : [firstReply] },
  }));
  await answers.route(`${answerPath}/conversation/turns/stream`, (route) => {
    answerRequests.push(route.request().postDataJSON());
    if (answerRequests.length === 1) return route.fulfill({ status: 503, json: { detail: "The assistant is unavailable. Retry this answer." } });
    answerSaved = true;
    const reply = {
      researcherTurnId: "answer", platformTurnId: nextReply.turnId, text: nextReply.text,
      moves: nextReply.moves, recommendations: [], supersededMoveIds: [originalMove.moveId], source: "llm",
    };
    return route.fulfill({ contentType: "text/event-stream", body: `event: done\ndata: ${JSON.stringify(reply)}\n\n` });
  });
  await answers.goto(`${answerPath}?tab=setup`);
  const options = answers.getByRole("group", { name: `Answers to: ${question}` });
  const answerChip = options.getByRole("button", { name: answer, exact: true });
  await expect(answerChip).toBeVisible();
  await answers.reload();
  await expect(answerChip).toBeVisible();
  for (const width of [1280, 320]) {
    await answers.setViewportSize({ width, height: 620 });
    const fits = await answerChip.evaluate((button) => {
      const box = button.getBoundingClientRect();
      const text = document.createRange();
      text.selectNodeContents(button.firstElementChild);
      const lines = [...text.getClientRects()];
      return box.left >= 0 && box.right <= innerWidth
        && lines.every((line) => line.left >= box.left && line.right <= box.right && line.bottom <= box.bottom)
        && (innerWidth > 320 || lines.length > 1);
    });
    check(fits, `the full saved answer fits its button at ${width}px after reload`);
    if (values.screenshots) {
      await options.scrollIntoViewIfNeeded();
      await settleVisual(answers);
      await answers.screenshot({ path: join(values.screenshots, `answer-options-${width}.png`) });
    }
  }
  const draftComposer = answers.getByRole("textbox", { name: "Message the design assistant", exact: true });
  const emptyHeight = await draftComposer.evaluate((element) => element.getBoundingClientRect().height);
  check(emptyHeight <= 40, "an empty mobile composer stays compact");
  await draftComposer.fill(draftAnswer);
  await answerChip.press("Enter");
  await answers.getByRole("status").filter({ hasText: "The assistant is unavailable." }).waitFor();
  await expect(draftComposer).toHaveValue(draftAnswer);
  await expect(draftComposer).toBeFocused();
  await answerChip.press("Space");
  const newProposal = answers.locator('[data-move-id="updated:title"]');
  await expect(newProposal.getByRole("button", { name: "Accept", exact: true })).toBeVisible();
  await expect(draftComposer).toHaveValue(draftAnswer);
  check(answerRequests.length === 2 && answerRequests.every((request) => request.text === answer && request.requestId === answerRequests[0].requestId), "keyboard answer and retry preserve the unsent draft and send only the selected answer");
  await expect(options).toBeHidden();
  const oldProposal = answers.locator('[data-move-id="original:title"]');
  const gathered = answers.locator('[data-move-id="original:design"]');
  const verifyReplacement = async () => {
    await answers.getByText("Decisions (1)", { exact: true }).click();
    await expect(oldProposal.getByText("Replaced", { exact: true })).toBeVisible();
    await expect(oldProposal.getByRole("button")).toHaveCount(0);
    await expect(gathered.getByRole("button", { name: "Accept", exact: true })).toBeVisible();
    const latestReply = await answers.getByRole("paragraph").filter({ hasText: "I updated the study name." }).boundingBox();
    check((await gathered.boundingBox()).y > latestReply.y, "an open plan card from an earlier reply gathers under the latest reply while the earlier reply keeps its decided cards");
  };
  await verifyReplacement();
  await answers.reload();
  await verifyReplacement();
  check(true, "superseded proposals become read-only on reply arrival and stay replaced after reload");
  await answers.close();

  const create = await context.newPage();
  let createRequests = 0;
  let releaseCreate;
  const createGate = new Promise((resolve) => { releaseCreate = resolve; });
  await create.route(`${base}/projects/implicit/studies`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    createRequests++;
    await createGate;
    return route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "Synthetic outage: try creating the study again." }) });
  });
  await create.setViewportSize({ width: 360, height: 800 });
  await create.goto(`${base}/home`);
  await create.getByRole("button", { name: "New study", exact: true }).click();
  const studyName = create.getByRole("textbox", { name: "Study name", exact: true });
  const longName = "調査 العربية naïve 🔬 ".repeat(6);
  await studyName.fill(longName);
  const storedName = await studyName.inputValue();
  check(storedName.length <= 80, "new study: long Unicode names respect the stated length limit");
  const creatingRequest = create.waitForRequest((request) => request.url() === `${base}/projects/implicit/studies` && request.method() === "POST");
  await studyName.press("Enter");
  await creatingRequest;
  await studyName.press("Enter");
  await studyName.press("Enter");
  check(createRequests === 1, "new study: repeated Enter during creation sends one request");
  releaseCreate();
  await create.getByRole("alert").filter({ hasText: "Synthetic outage" }).waitFor();
  check(await studyName.inputValue() === storedName, "new study: a failed save preserves the name for retry");
  await auditPage(create, "new study creation error");
  await create.close();

  const deletable = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "Deletion refresh fixture" }) })).id;
  const deletingPage = await context.newPage();
  await deletingPage.goto(`${base}/home`);
  const deleteButton = deletingPage.getByRole("button", { name: "Delete Deletion refresh fixture", exact: true });
  await deleteButton.click();
  await deletingPage.route(`${base}/studies/${deletable}`, (route) => route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "Delete refused" }) }));
  await deletingPage.getByRole("button", { name: "Delete study", exact: true }).click();
  await deletingPage.getByText("Delete refused", { exact: true }).waitFor();
  check(await deletingPage.locator(`a[href="/studies/${deletable}"]`).count() === 1, "a refused deletion keeps the study in the list");
  await deletingPage.unroute(`${base}/studies/${deletable}`);
  await deletingPage.route(`${base}/studies`, (route) => route.abort("connectionfailed"));
  await deletingPage.getByRole("button", { name: "Delete study", exact: true }).click();
  await deletingPage.getByRole("dialog").waitFor({ state: "hidden" });
  await expect(deleteButton).toHaveCount(0);
  check(!(await api("/studies")).some((study) => study.id === deletable), "confirmed deletion removes the study even if refreshing the list fails");
  await deletingPage.close();

  const sourceStudy = (await api("/projects/implicit/studies", { method: "POST", body: JSON.stringify({ name: "Source history fixture" }) })).id;
  const sourcePage = await context.newPage();
  await sourcePage.route(`${base}/studies/${sourceStudy}/conversation`, (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ turns: [{
      turnId: "fixture-turn", role: "platform", text: "Fixture decisions.",
      recommendations: [], moves: [
        { moveId: "earlier", kind: "add-rq", target: "researchQuestions", proposal: "An earlier question", status: "accepted", grounding: [{ ref: "fixture:paper", title: "Earlier fixture paper" }] },
        { moveId: "replacement", kind: "choose-template", target: "design", proposal: "A replacement plan", status: "accepted", grounding: [], patch: { templateId: "two-group-rct-v1", manual: true } },
        { moveId: "pending-choice", kind: "add-rq", target: "researchQuestions", proposal: "Does assistance change debugging time?", status: "proposed", grounding: [] },
      ],
    }] }),
  }));
  await sourcePage.route(`${base}/studies/${sourceStudy}/conversation/moves/pending-choice/decision`, (route) => route.fulfill({
    json: { moveId: "pending-choice", status: route.request().postDataJSON().status },
  }));
  await sourcePage.route(`${base}/studies/${sourceStudy}/conversation/turns/stream`, (route) => route.fulfill({
    status: 409, json: { detail: "Fixture decision saved." },
  }));
  await sourcePage.goto(`${base}/p/implicit/studies/${sourceStudy}?tab=conversation`);
  await sourcePage.getByText("Fixture decisions.", { exact: true }).first().waitFor();
  await sourcePage.getByRole("button", { name: "Review draft", exact: true }).last().click();
  const reviewDialog = sourcePage.getByRole("dialog");
  await reviewDialog.getByText("Decision history", { exact: true }).click();
  await expect(reviewDialog).toContainText("0 with linked sources");
  await reviewDialog.getByText("Earlier sourced decisions (1)", { exact: true }).click();
  await expect(reviewDialog).toContainText("Earlier fixture paper");
  check(true, "review distinguishes current sources from earlier sourced decisions");
  await reviewDialog.getByRole("button", { name: "Close", exact: true }).click();
  const pendingChoice = sourcePage.locator('[data-move-id="pending-choice"]');
  await pendingChoice.press("r");
  const undoChoice = pendingChoice.getByRole("button", { name: "Undo", exact: true });
  await expect(undoChoice).toBeFocused();
  await undoChoice.press("Enter");
  await expect(pendingChoice).toBeFocused();
  check(true, "keyboard focus follows the last decision into Undo and returns to the reopened card");
  await sourcePage.close();

  const seeded = spawnSync("uv", ["run", "python", "-m", "middleware", "seed-example"], {
    cwd: ROOT, encoding: "utf8", env: {
      ...process.env, DATABASE_URL: "", MIDDLEWARE_AUTH: "none", MIDDLEWARE_PROTOCOL: "",
      MIDDLEWARE_WEB: DIST, MIDDLEWARE_DB: join(data, "ui.sqlite3"), MIDDLEWARE_DATA_DIR: data,
      MIDDLEWARE_CORPUS_BOOTSTRAP: "0", MIDDLEWARE_REFRESH_INTERVAL_H: "",
      LLM_API_KEY: "", LLM_BASE_URL: "",
    },
  });
  if (seeded.status !== 0) throw new Error(`Synthetic example seed failed: ${seeded.stderr}`);
  const example = await context.newPage();
  const examplePath = `${base}/p/implicit/studies/example-copilot-and-bug-fixing-synthetic-data`;
  await example.goto(`${examplePath}?tab=data`);
  const exampleChecks = example.getByText("Outcome capture checks", { exact: true });
  await exampleChecks.click();
  await example.getByRole("button", { name: "Check captured inputs", exact: true }).click();
  await example.locator("summary").filter({ hasText: /^Time to first passing test/ }).click();
  await expect(example.getByText("23 of 25 session units have observed inputs.", { exact: true }).filter({ visible: true })).toBeVisible();
  await exampleChecks.click();
  await example.setViewportSize({ width: 320, height: 620 });
  const exportPath = `${base}/studies/example-copilot-and-bug-fixing-synthetic-data/data-bundle`;
  const exportFailure = "The data export could not be prepared. Please verify the study configuration and try again.";
  await example.route(exportPath, (route) => route.fulfill({ status: 503, json: { detail: exportFailure } }), { times: 1 });
  const exportMenu = example.getByRole("button", { name: "Export study", exact: true });
  const exportData = example.getByRole("menuitem", { name: /^Data \(\.zip\)/ });
  await exportMenu.press("ArrowDown");
  await exportData.press("Enter");
  const exportAlert = example.getByRole("alert").filter({ hasText: exportFailure });
  await expect(exportAlert).toBeVisible();
  const errorFits = await exportAlert.evaluate((element) =>
    element.scrollWidth <= element.clientWidth && element.getBoundingClientRect().right <= innerWidth,
  );
  const help = await example.getByRole("button", { name: "How this workspace works", exact: true }).boundingBox();
  check(errorFits && help.x + help.width <= 320, "a failed export shows the whole error without pushing mobile controls offscreen");
  await exportMenu.press("ArrowDown");
  const retriedExport = example.waitForEvent("download");
  await exportData.press("Enter");
  check(await (await retriedExport).failure() === null, "export succeeds on retry after a temporary refusal");
  await expect(exportAlert).toBeHidden();
  await example.setViewportSize({ width: 1280, height: 800 });
  const sessionList = example.getByRole("region", { name: "Captured sessions", exact: true });
  await expect(sessionList.getByRole("button", { name: /^P\d+/ })).toHaveCount(6);
  await sessionList.getByRole("button", { name: "Next sessions page", exact: true }).click();
  check(await sessionList.getByRole("status").innerText() === "7–12 of 25", "captured sessions use bounded pages");
  await sessionList.getByRole("searchbox", { name: "Search sessions", exact: true }).fill("P13");
  await expect(sessionList.getByRole("button", { name: /^P\d+/ })).toHaveCount(1);
  check(await sessionList.getByRole("navigation").count() === 0, "searching sessions resets pagination and keeps the match visible");
  await sessionList.getByRole("searchbox", { name: "Search sessions", exact: true }).fill("");
  const review = example.getByRole("region", { name: "Session review", exact: true });
  await review.getByRole("combobox", { name: "Show sessions", exact: true }).waitFor();
  check(await review.getByRole("button", { name: /^P\d+/ }).count() <= 6, "session review starts with a compact set needing attention");
  await review.getByRole("combobox", { name: "Show sessions", exact: true }).click();
  await example.getByRole("option", { name: "Control conditions", exact: true }).click();
  await review.getByRole("button", { name: "Next audit page", exact: true }).click();
  check(await review.getByRole("status").innerText() === "7–12 of 13", "control-session review paginates without treatment-row clutter");
  await review.getByRole("searchbox", { name: "Search review sessions", exact: true }).fill("<script>invalid</script>");
  await review.getByText("No matching sessions. Try another search.", { exact: true }).waitFor();
  await review.getByRole("searchbox", { name: "Search review sessions", exact: true }).fill("P13");
  await expect(review.getByRole("button", { name: /^P\d+/ })).toHaveCount(1);
  await review.getByRole("searchbox", { name: "Search review sessions", exact: true }).fill("");
  await review.getByRole("combobox", { name: "Show sessions", exact: true }).click();
  await example.getByRole("option", { name: "Needs review", exact: true }).click();
  await review.getByRole("button", { name: /^P\d+/ }).first().click();
  await auditPage(example, "populated Data and session review");
  const captureScreens = async (label, target) => {
    if (!values.screenshots) return;
    await example.evaluate(() => { if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); });
    for (const [width, suffix] of [[1280, "desktop"], [390, "mobile"]]) {
      await example.setViewportSize({ width, height: 844 });
      await target.evaluate((element) => element.scrollIntoView({ block: "start" }));
      await example.screenshot({ path: join(values.screenshots, `${label}-${suffix}.png`), fullPage: true });
    }
    await example.setViewportSize({ width: 1280, height: 800 });
  };
  await captureScreens("session-review", review);
  const measurements = example.getByRole("region", { name: "Measurements", exact: true });
  await measurements.getByRole("combobox", { name: "Metric", exact: true }).click();
  await example.getByRole("option", { name: "Acceptance-test outcome", exact: true }).click();
  const spacing = await measurements.evaluate((element) => {
    const chart = [...element.querySelectorAll("div")].find((node) => node.classList.contains("relative") && node.textContent.includes("Each record counts once"));
    const next = [...document.querySelectorAll("h2")].find((heading) => heading.textContent === "Recorded analysis plan");
    return next.getBoundingClientRect().top - chart.getBoundingClientRect().bottom;
  });
  check(spacing >= 0 && spacing <= 64, "categorical charts leave no fixed-height blank area before the analysis plan");
  await auditPage(example, "categorical measurements and recorded analysis");
  await captureScreens("measurements", measurements);
  await example.getByRole("button", { name: "Run", exact: true }).click();
  const roster = example.getByRole("region", { name: "Participant links", exact: true });
  await expect(roster.locator("tbody tr")).toHaveCount(6);
  const conditionCell = roster.locator("tbody tr").first().locator("td").nth(1);
  const originalCondition = await conditionCell.textContent();
  await conditionCell.evaluate((cell) => { cell.textContent = "Without AI Assistant (Baseline)"; });
  const conditionFits = await conditionCell.evaluate((cell) => {
    const range = document.createRange();
    range.selectNodeContents(cell);
    const boundary = cell.getBoundingClientRect();
    return [...range.getClientRects()].every((line) => line.right <= boundary.right + 1);
  });
  check(conditionFits, "long condition names wrap within their participant table column");
  await conditionCell.evaluate((cell, value) => { cell.textContent = value; }, originalCondition);
  await example.getByRole("button", { name: "Next participants page", exact: true }).click();
  await example.getByRole("searchbox", { name: "Search participants", exact: true }).fill("P24");
  await expect(roster.locator("tbody tr")).toHaveCount(1);
  check(await roster.getByText("P24", { exact: true }).isVisible(), "participant search finds records beyond the first roster page");
  await example.getByRole("searchbox", { name: "Search participants", exact: true }).fill("without AI");
  check((await roster.locator("tbody tr").allTextContents()).every((text) => text.includes("Without AI")), "participant search accepts the displayed condition wording");
  await example.getByRole("searchbox", { name: "Search participants", exact: true }).fill("");
  await example.setViewportSize({ width: 360, height: 800 });
  await expect.poll(() => roster.evaluate((element) => {
    const status = element.querySelector("tbody tr")?.cells[2];
    return status && status.getBoundingClientRect().right <= element.getBoundingClientRect().right;
  })).toBe(true);
  check(true, "the mobile roster shows participant, condition, and status before horizontal scrolling");
  await roster.focus();
  await example.keyboard.press("ArrowRight");
  await expect.poll(() => roster.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
  check(true, "the participant table scrolls horizontally with the keyboard");
  await roster.evaluate((element) => { element.scrollLeft = 0; });
  await auditPage(example, "populated Run roster");
  await captureScreens("participant-roster", example.getByRole("searchbox", { name: "Search participants", exact: true }));
  await example.getByRole("button", { name: "Plan", exact: true }).click();
  await example.getByRole("heading", { name: "Plan participant recruitment", exact: true }).waitFor();
  await example.waitForLoadState("networkidle");
  await auditPage(example, "populated recruitment plan");
  await captureScreens("recruitment-plan", example.getByRole("heading", { name: "Plan participant recruitment", exact: true }));
  await example.close();

  const mutation = await context.newPage();
  await mutation.goto(`${base}/p/implicit/studies/${bare}?tab=conversation`);
  await mutation.waitForLoadState("networkidle");
  const original = await mutation.evaluate(() => {
    const button = [...document.querySelectorAll("button")].find((element) => element.offsetParent !== null);
    const parent = button.parentElement;
    const styles = [button.getAttribute("style"), parent.getAttribute("style")];
    button.dataset.ringMutation = "target";
    parent.dataset.ringMutation = "parent";
    button.style.outline = parent.style.outline = "2px solid red";
    return styles;
  });
  check((await mutation.evaluate(RING_SCAN)).doubles.length > 0, "ring scanner catches an intentional stacked-outline mutation");
  await mutation.evaluate((styles) => {
    for (const [index, name] of ["target", "parent"].entries()) {
      const element = document.querySelector(`[data-ring-mutation="${name}"]`);
      if (styles[index] === null) element.removeAttribute("style");
      else element.setAttribute("style", styles[index]);
      delete element.dataset.ringMutation;
    }
  }, original);
  check((await mutation.evaluate(RING_SCAN)).doubles.length === 0, "ring scanner passes after restoring the mutation");
  await mutation.close();

  const betweenPage = await context.newPage();
  await betweenPage.goto(`${base}/p/implicit/studies/${between}?tab=planning`);
  await betweenPage.getByRole("heading", { name: "Plan participant recruitment" }).waitFor();
  const betweenDistribution = betweenPage.getByRole("combobox", { name: "Outcome distribution", exact: true });
  await betweenDistribution.click();
  const betweenLogNormal = betweenPage.getByRole("option", { name: "Log-normal (completion times)", exact: true });
  const betweenOrdinal = betweenPage.getByRole("option", { name: "Ordinal (Likert ratings)", exact: true });
  check(
    await betweenLogNormal.count() === 1 && await betweenOrdinal.count() === 1,
    "between-subjects rank plans retain log-normal and ordinal assumptions",
  );
  await betweenOrdinal.click();
  const betweenOrdinalPlan = betweenPage.waitForResponse((response) =>
    response.url().endsWith(`/studies/${between}/plan`) && response.request().method() === "POST",
  );
  await betweenPage.getByRole("button", { name: "Calculate and save plan", exact: true }).click();
  check((await betweenOrdinalPlan).status() === 200, "between-subjects rank test saves supported ordinal assumptions");
  await betweenPage.getByText(/Saved plan \d+/).waitFor();
  await betweenDistribution.click();
  await betweenPage.getByRole("option", { name: "Log-normal (completion times)", exact: true }).click();
  const betweenPlan = betweenPage.waitForResponse((response) =>
    response.url().endsWith(`/studies/${between}/plan`) && response.request().method() === "POST",
  );
  await betweenPage.getByRole("button", { name: "Calculate and save plan", exact: true }).click();
  check((await betweenPlan).status() === 200, "between-subjects log-normal plan saves through the UI");
  await betweenPage.getByText(/Saved plan \d+/).waitFor();
  await betweenPage.close();
} finally {
  await browser?.close();
  stop();
  await Promise.race([closed, new Promise((ok) => setTimeout(ok, 1500))]);
  if (server.exitCode === null) stop("SIGKILL");
  await closed;
  rmSync(data, { recursive: true, force: true });
  process.removeListener("exit", onExit);
}
if (values.audit) console.log(`AUDIT_RESULTS ${JSON.stringify(auditResults)}`);
console.log(failures.length ? `\n${failures.length} check(s) failed` : "\nall checks passed");
process.exitCode = failures.length ? 1 : 0;
