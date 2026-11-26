/* One-off visual tour of the built platform against a disposable middleware.
 * Run: node platform/scripts/visual-tour.mjs
 */
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createServer } from "node:net";
import { chromium } from "@playwright/test";

const ROOT = resolve(import.meta.dirname, "../..");
const DIST = join(ROOT, "platform", "dist");
const OUT = join(tmpdir(), "phoenix-tour");
const mkdirp = (p) => import("node:fs").then((fs) => fs.mkdirSync(p, { recursive: true }));
await mkdirp(OUT);

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
const data = mkdtempSync(join(tmpdir(), "phoenix-tour-"));
const server = spawn("uv", ["run", "python", "-c", `
from pathlib import Path
import uvicorn
from middleware.app import create_app
from middleware.settings import Settings
uvicorn.run(create_app(Settings()), host="127.0.0.1", port=int(__import__("os").environ["MIDDLEWARE_PORT"]))
`], {
  cwd: ROOT,
  env: {
    ...process.env,
    DATABASE_URL: "",
    MIDDLEWARE_AUTH: "none",
    MIDDLEWARE_TOKEN: "",
    MIDDLEWARE_PROTOCOL: "",
    MIDDLEWARE_REFRESH_INTERVAL_H: "off",
    MIDDLEWARE_PORT: String(port),
    MIDDLEWARE_WEB: DIST,
    MIDDLEWARE_DB: join(data, "tour.sqlite3"),
    MIDDLEWARE_DATA_DIR: data,
    MIDDLEWARE_CORPUS_BOOTSTRAP: "0",
    LLM_API_KEY: "",
    LLM_BASE_URL: "",
  },
  detached: process.platform !== "win32",
  stdio: "ignore",
});
const stop = () => {
  try { if (process.platform !== "win32") process.kill(-server.pid); else server.kill(); } catch {}
};
process.on("exit", stop);

// wait for readiness
for (let i = 0; ; i++) {
  try { await (await fetch(base + "/auth/config")).json(); break; } catch {
    if (i > 120) { console.error("middleware never came up"); process.exit(1); }
    await new Promise((r) => setTimeout(r, 500));
  }
}
const seeded = spawnSync("uv", ["run", "python", "-m", "middleware", "seed-example"], {
  cwd: ROOT, encoding: "utf8", env: {
    ...process.env, DATABASE_URL: "", MIDDLEWARE_AUTH: "none", MIDDLEWARE_PROTOCOL: "",
    MIDDLEWARE_WEB: DIST, MIDDLEWARE_DB: join(data, "tour.sqlite3"), MIDDLEWARE_DATA_DIR: data,
    MIDDLEWARE_CORPUS_BOOTSTRAP: "0", MIDDLEWARE_REFRESH_INTERVAL_H: "off", LLM_API_KEY: "", LLM_BASE_URL: "",
  },
});
if (seeded.status !== 0) throw new Error(`seed failed: ${seeded.stderr}`);

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();
const consoleErrors = [];
page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

const shot = async (name) => {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
  });
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  console.log(`shot: ${name}`);
};
const setTheme = (t) => page.evaluate((theme) => document.documentElement.setAttribute("data-theme", theme), t);

const examplePath = base + "/studies/example-copilot-and-bug-fixing-synthetic-data";

// 1. Home
await page.goto(base + "/home", { waitUntil: "networkidle" });
await shot("01-home-light");
await setTheme("dark");
await shot("02-home-dark");
await setTheme("light");

// 2. Data tab with outcome checks open
await page.goto(examplePath + "?tab=data", { waitUntil: "networkidle" });
const outcomeSummary = page.getByText("Outcome capture checks", { exact: true });
await outcomeSummary.click();
const checkBtn = page.getByRole("button", { name: "Check captured inputs", exact: false });
await checkBtn.click();
await page
  .waitForResponse((res) => res.url().includes("outcome") || res.url().includes("checks"), { timeout: 20000 })
  .then((r) => console.log("check response:", r.status(), r.url()))
  .catch(() => console.log("no outcome response observed"));
await page.waitForTimeout(1500);
console.log("panel text:", JSON.stringify((await page.getByRole("region", { name: "Data" }).innerText().catch(() => "")) || (await page.locator("main").innerText()).slice(0, 800)));
await shot("03-data-default");
// expand first outcome details
const detail = page.locator("summary").filter({ hasText: "Time to first passing test" }).first();
await detail.locator("summary").click();
await page.waitForTimeout(300);
await detail.scrollIntoViewIfNeeded();
await shot("04-data-outcome-details");
const olive = await detail.evaluate((el) => el.outerHTML.slice(0, 2400));
writeFileSync(join(OUT, "outcome-details.html"), olive);

// 3. Sessions expanded (timeline)
const firstSession = page.locator('[aria-label="Captured sessions"] button').filter({ hasText: "P0" }).first();
await firstSession.click();
await page.waitForTimeout(800);
await firstSession.scrollIntoViewIfNeeded();
await shot("05-data-session-timeline");

// 4. Measurements strip area
const measurements = page.getByText("Measurements by condition").first();
await measurements.scrollIntoViewIfNeeded();
await shot("06-data-measurements");

// 5. Export menu open
await page.evaluate(() => window.scrollTo(0, 0));
const exportButton = page.getByRole("button", { name: /Export/ }).first();
await exportButton.click();
await page.waitForTimeout(300);
await shot("07-export-menu");
await page.keyboard.press("Escape");

// 6. Plan tab
await page.goto(examplePath + "?tab=planning", { waitUntil: "networkidle" });
await page.waitForTimeout(400);
await shot("08-plan");

// 7. Setup tab (seeded conversation, LLM disabled)
await page.goto(examplePath + "?tab=conversation", { waitUntil: "networkidle" });
await page.waitForTimeout(400);
await shot("09-setup-seeded");

// 8. Repertoire
await page.goto(base + "/repertoire", { waitUntil: "networkidle" });
await shot("10-repertoire");

// 9. Mobile data
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(examplePath + "?tab=data", { waitUntil: "networkidle" });
await shot("11-data-mobile");
await setTheme("dark");
await shot("12-data-mobile-dark");

console.log("console errors:", JSON.stringify(consoleErrors, null, 2));
await browser.close();
stop();
process.exit(0);
