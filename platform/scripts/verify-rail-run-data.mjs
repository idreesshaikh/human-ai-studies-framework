/* Focused checks for the Run tab, the Data tab dry run and the draft rail
 * values. Run:
 *   node --experimental-strip-types scripts/verify-rail-run-data.mjs
 *
 * No browser: pure formatting functions, plus a source-level assertion that the
 * enrollment table cannot clip its Revoke control.
 */
import { readFileSync } from "node:fs";
import { compile } from "../src/lib/compiler.ts";
import { emptyDraft } from "../src/lib/types.ts";
import { formatSlotValue } from "../src/lib/protocolFormat.ts";
import { summarizeProducerStates } from "../src/components/enrollment/captureSummary.ts";
import { dryRunFallbackSessionIds } from "../src/components/charts/dryRunSessions.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};

const move = (patch, kind = "set-field") => ({
  moveId: "m1",
  kind,
  target: "x",
  proposal: "x",
  patch,
  grounding: [],
  status: "accepted",
});

/* Rail values */
const planned = compile(emptyDraft(), [
  move({ op: "set-field", path: ["participants", "planned"], value: 12 }),
]);
ok(
  "planned participants show the planned number",
  planned.participants.join("|") === "12 participants",
  JSON.stringify(planned.participants),
);
ok(
  "design slot shows a humanised template name, not the raw id",
  formatSlotValue("design", "within-subjects-ab") === "Within-subjects ab",
  formatSlotValue("design", "within-subjects-ab"),
);
ok(
  "conditions separated by a comma get a space",
  formatSlotValue("conditions", "ai-assisted,unassisted") ===
    "AI-assisted, unassisted",
  formatSlotValue("conditions", "ai-assisted,unassisted"),
);
ok(
  "instrument tern is upper-cased",
  formatSlotValue("instruments", "tern") === "TERN",
  formatSlotValue("instruments", "tern"),
);
ok(
  "an ethics posture id is humanised",
  formatSlotValue("ethics", "informed-consent-voluntary-anonymized") ===
    "Informed consent voluntary anonymized",
  formatSlotValue("ethics", "informed-consent-voluntary-anonymized"),
);
ok(
  "ethics prose is left alone",
  formatSlotValue("ethics", "Approved by the IRB, ref 42.") ===
    "Approved by the IRB, ref 42.",
);
ok(
  "other slots pass through untouched",
  formatSlotValue("researchQuestions", "Does it help?") === "Does it help?",
);

/* Capture summary */
const off = {
  tern: "enabled",
  metrics: "external-required",
  "agent-capture": "unavailable",
  a: "unavailable",
  b: "unsupported",
};
ok(
  "all non-tern producers off collapses to one phrase",
  summarizeProducerStates(off) === "External producers off",
  summarizeProducerStates(off),
);
ok(
  "enabled producers are listed, the rest summarised",
  summarizeProducerStates({ tern: "enabled", metrics: "enabled", x: "unavailable" }) ===
    "Code metrics on; other external producers off",
  summarizeProducerStates({ tern: "enabled", metrics: "enabled", x: "unavailable" }),
);
ok("no external producers says nothing", summarizeProducerStates({ tern: "enabled" }) === "");

/* Enrollment layout: Revoke must stay reachable at 1440px wide. */
const panel = readFileSync(
  new URL("../src/components/enrollment/EnrollmentPanel.tsx", import.meta.url),
  "utf8",
);
const tokens = readFileSync(
  new URL("../src/styles/tokens.css", import.meta.url),
  "utf8",
);
const minRem = Number(
  /--enrollment-table-min-width:\s*([\d.]+)rem/.exec(tokens)?.[1] ?? Infinity,
);
ok("enrollment table min width fits a 1440px window beside the chrome", minRem <= 62, `${minRem}rem`);
ok("Revoke column is sticky to the right edge", /sticky right-0[^"]*"[^>]*>\s*\{canMint/.test(panel));
ok("Will capture column is flexible, not a fixed w-96", !panel.includes('<col className="w-96"'));

/* Dry run fallback */
const report = { sessions: 3, sessionIds: ["a", "b", "c"] };
ok(
  "dry-run ids fill the list when the refresh returned none",
  dryRunFallbackSessionIds(report, 0).join() === "a,b,c",
);
ok("no fallback once real sessions loaded", dryRunFallbackSessionIds(report, 3).length === 0);
ok("no fallback without a report", dryRunFallbackSessionIds(null, 0).length === 0);

if (failures) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
