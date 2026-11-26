// Capture the PHOENIX screenshots used in the README and the user guide.
//
// Starts a disposable synthetic demo (scripts/run_demo.py), opens each screen
// in Chromium in the light theme, and writes <name>.webp files to
// documentation/docs/assets/screens/. The demo deletes its data on exit.
//
// Needs the built web app and the platform's Playwright browser:
//   npm --prefix platform run build
//   npm --prefix platform exec playwright install chromium
//   node documentation/scripts/screenshots.mjs [name ...]
//
// Pass shot names to capture only those. Every image shows synthetic demo
// data; captions must say so wherever it matters.

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { createServer } from "node:net";
import { join, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..", "..");
const OUT = join(ROOT, "documentation", "docs", "assets", "screens");
const require = createRequire(join(ROOT, "platform", "package.json"));
const { chromium } = require("playwright");

const STUDY = "/studies/example-copilot-and-bug-fixing-synthetic-data";
const VIEWPORT = { width: 1280, height: 800 };
const SCALE = 2;
const QUALITY = 88;

const click =
  (name, role = "button") =>
  async (page) => {
    await page.getByRole(role, { name, exact: true }).first().click();
    await page.waitForTimeout(450);
  };

// name: file stem; path: route in the app; prepare: steps before the shot;
// clip: a locator to crop to instead of the whole window.
const SHOTS = [
  { name: "studies", path: "/home", heading: "Studies" },
  { name: "templates", path: "/repertoire", heading: "Templates" },
  {
    name: "setup",
    path: `${STUDY}?tab=setup`,
    prepare: async (page) => {
      const closed = page.getByRole("button", { name: "Protocol draft", exact: true });
      if (await closed.isVisible()) await closed.click();
      await page.getByRole("button", { name: "Hide protocol draft" }).waitFor();
      // Show the latest reply and the plan card waiting on the researcher.
      await page.getByRole("button", { name: "Accept", exact: true }).first().waitFor();
      await page
        .getByRole("region", { name: "Conversation" })
        .evaluate((thread) => thread.scrollTo({ top: thread.scrollHeight }));
      await page.waitForTimeout(300);
    },
  },
  {
    name: "review-draft",
    path: `${STUDY}?tab=setup`,
    prepare: click("Review draft"),
    dialog: true,
  },
  { name: "evidence", path: `${STUDY}?tab=literature`, heading: "Literature" },
  { name: "plan", path: `${STUDY}?tab=plan`, region: "Planning" },
  { name: "run", path: `${STUDY}?tab=run`, region: "Participants" },
  { name: "data", path: `${STUDY}?tab=data`, region: "Data" },
];

const only = new Set(process.argv.slice(2));
const unknown = [...only].filter(
  (name) => !SHOTS.some((shot) => shot.name === name),
);
if (unknown.length) {
  console.error(
    `Unknown shot: ${unknown.join(", ")}. Known: ${SHOTS.map((s) => s.name).join(", ")}`,
  );
  process.exit(2);
}
if (!existsSync(join(ROOT, "platform", "dist", "index.html"))) {
  console.error("No built web app. Run: npm --prefix platform run build");
  process.exit(2);
}

const freePort = () =>
  new Promise((ok, fail) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      server.close(() => ok(port));
    });
    server.on("error", fail);
  });

async function waitForDemo(base, demo) {
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    if (demo.exitCode !== null)
      throw new Error("The demo server exited before it was ready.");
    try {
      if ((await fetch(`${base}/studies`)).ok) return;
    } catch {
      // Not listening yet.
    }
    await new Promise((ok) => setTimeout(ok, 500));
  }
  throw new Error("The demo server did not answer within 90 seconds.");
}

async function capture(page, file, locator) {
  // Chromium writes WebP directly, which keeps 2x screenshots small.
  const cdp = await page.context().newCDPSession(page);
  const params = { format: "webp", quality: QUALITY };
  if (locator) {
    const box = await locator.boundingBox();
    params.clip = { ...box, scale: 1 };
  }
  const { data } = await cdp.send("Page.captureScreenshot", params);
  writeFileSync(file, Buffer.from(data, "base64"));
  await cdp.detach();
}

const port = await freePort();
const base = `http://127.0.0.1:${port}`;
const demo = spawn(
  "uv",
  ["run", "--no-sync", "python", "scripts/run_demo.py", "--port", String(port)],
  {
    cwd: ROOT,
    stdio: ["ignore", "ignore", "pipe"],
  },
);
let demoErrors = "";
demo.stderr.on(
  "data",
  (chunk) => (demoErrors = (demoErrors + chunk).slice(-4000)),
);

let browser;
try {
  await waitForDemo(base, demo);
  mkdirSync(OUT, { recursive: true });
  browser = await chromium.launch();
  // Light theme only: the README and the guide use one image per screen.
  const context = await browser.newContext({
    viewport: VIEWPORT,
    deviceScaleFactor: SCALE,
    reducedMotion: "reduce",
  });
  await context.addInitScript(
    (value) => localStorage.setItem("platform-theme", value),
    "light",
  );
  const page = await context.newPage();

  // Fold the app's navigation once so every shot gives the screen its width.
  await page.goto(`${base}/home`, { waitUntil: "networkidle" });
  await click("Collapse navigation")(page);

  for (const shot of SHOTS) {
    if (only.size && !only.has(shot.name)) continue;
    await page.goto(base + shot.path, { waitUntil: "networkidle" });
    if (shot.heading) await page.getByRole("heading", { name: shot.heading, exact: true }).first().waitFor();
    if (shot.region) await page.getByRole("region", { name: shot.region, exact: true }).waitFor();
    await page.waitForTimeout(400);
    if (shot.prepare) await shot.prepare(page);
    const target = shot.dialog
      ? page.getByRole("dialog").first()
      : shot.clip?.(page);
    const file = join(OUT, `${shot.name}.webp`);
    await capture(page, file, shot.dialog ? undefined : target);
    console.log(`wrote ${file.slice(ROOT.length + 1)}`);
    // Close any dialog the shot opened before the next route.
    if (shot.dialog) await page.keyboard.press("Escape");
  }
  await context.close();
} catch (error) {
  console.error(error.message);
  if (demoErrors) console.error(demoErrors);
  process.exitCode = 1;
} finally {
  await browser?.close();
  // SIGINT lets run_demo.py delete its temporary data directory.
  demo.kill("SIGINT");
}
