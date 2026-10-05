/* Exercises the data-bundle download helpers. Run:
 *   node --experimental-strip-types scripts/verify-data-export.mjs
 *
 * Checks that:
 *   - the path targets the study's data-bundle route
 *   - dry-run rows are excluded unless asked for
 *   - study ids are URL-encoded
 *   - the filename matches the server's Content-Disposition name
 */
import { dataBundlePath, dataBundleFilename } from "../src/lib/dataBundle.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};

ok("path targets the data-bundle route", dataBundlePath("pilot-2026") === "/studies/pilot-2026/data-bundle");
ok(
  "synthetic rows are excluded by default",
  !dataBundlePath("pilot-2026").includes("includeSynthetic"),
);
ok(
  "synthetic rows are included only when asked",
  dataBundlePath("pilot-2026", true) === "/studies/pilot-2026/data-bundle?includeSynthetic=true",
);
ok("study id is URL-encoded", dataBundlePath("a/b c") === "/studies/a%2Fb%20c/data-bundle");
ok("filename is <study>-data.zip", dataBundleFilename("pilot-2026") === "pilot-2026-data.zip");

if (failures) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log("\nall data-export checks passed");
