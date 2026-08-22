import { spawn } from "node:child_process";
import process from "node:process";
import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const HOST = "127.0.0.1";
const PORT = 4173;
const BASE_URL = `http://${HOST}:${PORT}`;
const routes = ["/", "/a-route-that-does-not-exist"];

function waitForServer(url, timeoutMs = 30_000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const response = await fetch(url);
        if (response.ok) {
          resolve();
          return;
        }
      } catch {
        // The preview process may need a few moments to bind its port.
      }
      if (Date.now() - started >= timeoutMs) {
        reject(new Error(`Timed out waiting for ${url}`));
        return;
      }
      setTimeout(poll, 250);
    };
    void poll();
  });
}

const preview = spawn(
  "npm",
  ["run", "preview", "--", "--host", HOST, "--port", String(PORT)],
  { stdio: "ignore", shell: process.platform === "win32" },
);

try {
  await waitForServer(BASE_URL);
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    for (const route of routes) {
      await page.goto(`${BASE_URL}${route}`, { waitUntil: "networkidle" });
      const results = await new AxeBuilder({ page }).analyze();
      if (results.violations.length > 0) {
        console.error(`Accessibility violations on ${route}:`);
        for (const violation of results.violations) {
          console.error(`- [${violation.impact}] ${violation.id}: ${violation.help}`);
          for (const node of violation.nodes) console.error(`  ${node.html}`);
        }
        process.exitCode = 1;
      } else {
        console.log(`✓ Axe clean: ${route}`);
      }
    }
  } finally {
    await context.close();
    await browser.close();
  }
} finally {
  preview.kill();
}
