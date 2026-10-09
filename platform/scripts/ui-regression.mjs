// Researcher workflows against a disposable backend; --audit also checks WCAG,
// themes, responsive layouts and scroll reach. Build the platform first.
import { spawn } from "node:child_process";
import { mkdtempSync, existsSync, mkdirSync, readFileSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const ROOT = resolve(import.meta.dirname, "..", "..");
const extension = JSON.parse(readFileSync(join(ROOT, "extension", "package.json"), "utf8"));
const { values } = parseArgs({ options: { dist: { type: "string" }, screenshots: { type: "string" }, audit: { type: "boolean", default: false } } });
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
const server = spawn("uv", ["run", "python", "-m", "middleware", "serve"], {
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
    MISTRAL_API_KEY: "",
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
  for (const [theme, width, height] of [["light", 1280, 800], ["dark", 1280, 800], ["light", 390, 844], ["dark", 390, 844], ["light", 768, 1024], ["light", 360, 800]]) {
    await page.setViewportSize({ width, height });
    await page.evaluate((theme) => document.documentElement.setAttribute("data-theme", theme), theme);
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

browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
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
      await page.evaluate(() => document.querySelectorAll("details").forEach((d) => (d.open = true)));
      const { focusable, doubles } = await page.evaluate(RING_SCAN);
      check(doubles.length === 0, `${where}: at most one focus ring per element (${focusable} focusable; stacked: ${doubles.join(", ") || "none"})`);
      if (values.screenshots) {
        await page.evaluate(() => {
          document.activeElement?.blur();
          document.querySelectorAll("*").forEach((element) => { element.scrollTop = 0; });
        });
        await page.screenshot({ path: join(values.screenshots, `${hasProtocol ? "protocol" : "empty"}-${tab}-desktop.png`), fullPage: true });
        await page.setViewportSize({ width: 390, height: 844 });
        const mobile = await page.evaluate(RING_SCAN);
        check(mobile.doubles.length === 0, `${where}: no stacked focus rings on mobile`);
        await page.evaluate(() => {
          document.activeElement?.blur();
          document.querySelectorAll("*").forEach((element) => { element.scrollTop = 0; });
        });
        await page.screenshot({ path: join(values.screenshots, `${hasProtocol ? "protocol" : "empty"}-${tab}-mobile.png`), fullPage: true });
      }
      await page.close();
    }
  }
  for (const path of ["/home", "/repertoire", "/settings", "/p/implicit", "/p/implicit/members", "/p/implicit/settings"]) {
    const page = await context.newPage();
    await page.goto(base + path);
    await page.waitForLoadState("networkidle");
    await auditPage(page, path);
    if (path === "/p/implicit") {
      check(!/Members|Team|Manage members|Switch project/.test(await page.locator("body").innerText()), "solo project: no team or switching controls");
    }
    if (path === "/home") {
      check(new URL(page.url()).pathname === "/p/implicit", "solo home: opens the first project directly");
    }
    if (path === "/repertoire") {
      check(await page.getByText("No literature indexed yet.", { exact: false }).isVisible(), "empty evidence index has an honest state");
      check(await page.getByRole("textbox", { name: "Describe your study", exact: true }).isVisible(), "starting a conversation remains available before literature indexing");
    }
    if (path === "/p/implicit/settings") {
      const field = page.getByRole("textbox", { name: "Project name", exact: true });
      check(await field.inputValue() === "My project", "project settings show the current editable name");
      await field.fill("Research workspace");
      await field.press("Enter");
      await page.getByRole("status").filter({ hasText: "Project name saved" }).waitFor();
      check((await api("/projects/implicit")).name === "Research workspace", "project name saves with Enter and retains its URL");
      await field.fill("My project");
      await page.getByRole("button", { name: "Save", exact: true }).click();
      await page.getByRole("status").filter({ hasText: "Project name saved" }).waitFor();
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
  await page.getByRole("button", { name: "Study design", exact: true }).click();
  await page.getByRole("menuitemradio", { name: /^Between-subjects/ }).click();
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
  await page.getByRole("button", { name: "Study design", exact: true }).click();
  await page.getByRole("menuitemradio", { name: /^Within-subjects/ }).click();
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
  await auditPage(page, "protocol review dialog");
  await page.getByRole("button", { name: "Apply protocol", exact: true }).click();
  await page.getByText("Draft applied to the protocol.", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Plan", exact: true }).click();
  await page.getByRole("heading", { name: "Plan participant recruitment" }).waitFor();
  await page.getByRole("button", { name: "Calculate and save plan", exact: true }).click();
  await page.getByText(/Saved plan \d+/).waitFor();
  check(true, "manual entry and Apply unlock Plan without reloading the page");
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
  const release = await page.getByRole("link", { name: "Download the .vsix", exact: true }).getAttribute("href");
  check(release?.startsWith(extension.repository.url.replace(/\.git$/, "")), "extension download points to its release repository");
  await page.getByRole("button", { name: "Data", exact: true }).click();
  await page.getByRole("heading", { name: "Download study records" }).waitFor();
  await auditPage(page, "typed protocol Data");
  for (const name of ["Data (.zip)", "Design card (.md)", "Replication kit"]) {
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name, exact: true }).click();
    const file = await download;
    check(await file.failure() === null, `${name}: generated download completes`);
  }
  check(true, "manual save unlocks Data without reloading");
  await page.close();

  const starter = await context.newPage();
  await starter.goto(`${base}/p/implicit`);
  await starter.getByRole("button", { name: "New study", exact: true }).click();
  await auditPage(starter, "new study dialog");
  await starter.getByRole("button", { name: "Use this template", exact: true }).first().click();
  await starter.getByRole("heading", { name: "Plan participant recruitment" }).waitFor();
  await starter.getByRole("button", { name: "Calculate and save plan", exact: true }).click();
  await starter.getByText(/Saved plan \d+/).waitFor();
  await auditPage(starter, "saved featured plan");
  check(new URL(starter.url()).searchParams.get("tab") === "planning", "featured starter reaches a saved plan without typing a protocol");
  await starter.close();

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
