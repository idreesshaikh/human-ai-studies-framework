/* App-wide polish: header control height, list-row targets, type floor,
 * dialog structure, review row labels. Pure helpers + source-level checks.
 *   node --experimental-strip-types scripts/verify-polish.mjs
 */
import { readFileSync, existsSync } from "node:fs";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};
const root = new URL("../src/", import.meta.url).pathname;
const src = (p) => (existsSync(root + p) ? readFileSync(root + p, "utf8") : "");
const css = src("styles/index.css");
const tokens = src("styles/tokens.css");
const block = (selector) => {
  const i = css.indexOf(selector);
  return i < 0 ? "" : css.slice(i, css.indexOf("}", i));
};

/* ---- 5. review row labels ---- */
const { rowLabel, ROW_LABELS } = await import("../src/lib/slotRowLabels.ts").catch(() => ({}));
ok("rowLabel exists", typeof rowLabel === "function");
if (rowLabel) {
  const want = {
    "participants.design": "Design",
    "participants.planned": "Sample size",
    "participants.sampleSize": "Sample size",
    "participants.counterbalanced": "Counterbalancing",
    "participants.description": "Participants",
    "session.durationMinutes": "Session length",
    "session.taskDescription": "Task",
    "study.title": "Study name",
    "study.ethicsRef": "Ethics reference",
    "researchQuestions[]": "Research questions",
    "protocol.conditions": "Conditions",
    instruments: "Instruments",
    analysisPlan: "Analysis plan",
    "measures[]": "Measures",
    design: "Design",
  };
  for (const [k, v] of Object.entries(want)) ok(`rowLabel(${k}) = ${v}`, rowLabel(k) === v, rowLabel(k));
  ok("no bullet separator in any label", Object.keys(want).every((k) => !rowLabel(k).includes("•")));
  /* Every slot the compiler declares has a plain label. */
  const py = readFileSync(new URL("../../middleware/src/middleware/compiler.py", import.meta.url), "utf8");
  const keys = [...py.matchAll(/Slot\(\s*\(([^)]*)\)/g)].map((m) =>
    [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]).join("."),
  );
  ok("found the compiler's slots", keys.length >= 10, String(keys.length));
  for (const k of keys) {
    const label = rowLabel(k);
    ok(`compiler slot ${k} has a curated label`, label && !/[A-Z][a-z]+ [a-z]*[A-Z]/.test(label) && !label.includes(" • "), label);
  }
  ok("unknown path falls back to sentence case", rowLabel("session.someNewThing") === "Some new thing");
}
ok("FinishReview uses rowLabel", /rowLabel\(m\.target\)/.test(src("components/conversation/FinishReview.tsx")));

/* ---- 3. type floor ---- */
ok("legend role is 12px", /--text-legend:\s*0\.75rem/.test(tokens));
ok("no text role below 12px", !/--text-[a-z-]+:\s*0\.(6|7[0-4])\d*rem/.test(tokens));
ok("legend role is sentence case", !/text-transform:\s*uppercase/.test(block(".type-legend {")));
ok("legend role has no wide tracking", !/letter-spacing:\s*var\(--tracking-legend\)/.test(block(".type-legend {")) && !/--tracking-legend:\s*0\.[1-9]/.test(tokens));
ok("table heads are sentence case", !/uppercase|tracking-wide/.test(src("components/ui/table.tsx")));
ok("no uppercase utility anywhere", !/\buppercase\b/.test(
  ["components/shell/AppFrame.tsx", "components/ui/badge.tsx", "components/conversation/MoveCard.tsx", "components/conversation/DraftRail.tsx"].map(src).join("")));
ok("no screaming literal labels", !/>\s*SETUP PAUSED\s*</.test(src("components/conversation/DraftRail.tsx")));

/* ---- 1. header controls ---- */
const hc = block(".header-control {");
ok(".header-control exists", hc.length > 0);
ok("header control is 40px", /height:\s*var\(--control-height\)/.test(hc));
ok("header control has the control radius + edge", /radius-control/.test(hc) && /border:\s*var\(--rule-hair\) solid var\(--border\)/.test(hc));
ok("header control uses the 13px label size", /font-size:\s*var\(--text-label\)/.test(hc));
ok("coarse query lifts header controls to 44px", /@media \(pointer: coarse\), \(max-width: 640px\)\s*\{[^@]*\.header-control\s*\{[^}]*--touch-target/.test(css));
const frame = src("components/shell/AppFrame.tsx");
const sw = src("components/shell/ProjectSwitcher.tsx");
ok("theme toggle is a header control", /className="header-control[^"]*"[\s\S]{0,200}themeToggleLabel/.test(frame) || /themeToggleLabel[\s\S]{0,200}header-control/.test(frame));
ok("account button is a header control", /header-control[^"]*"\s*aria-label="Account"|aria-label="Account"[\s\S]{0,40}header-control/.test(frame));
ok("project switcher is a header control", /header-control/.test(sw));
ok("switcher is not 12px caption type", !/type-caption/.test(sw.split("<CommandDialog")[0].split("<button")[1] ?? ""));
ok("sidebar collapse shares the nav item class", /NAV_ITEM/.test(frame) && (frame.match(/NAV_ITEM/g) ?? []).length >= 3);

/* ---- 2. list rows ---- */
const lib = src("components/library/LibraryTab.tsx");
ok("paper title is a row button", /className="row-button/.test(lib));
const rb = block(".row-button {");
ok("row button >= 28px with padding", /min-height:\s*var\(--target-min\)/.test(rb) && /padding/.test(rb));
ok("row button has hover + truncation", /\.row-button:hover/.test(css) && /text-overflow:\s*ellipsis/.test(rb));
ok("remove uses the quiet icon button", /size="icon-sm"/.test(lib) && /aria-label=\{`Remove \$\{/.test(lib));
const btn = src("components/ui/button.tsx");
ok("icon-sm is 28px", /"icon-sm":\s*"size-7/.test(btn));
ok("detail close is an icon-sm button", /icon-sm[\s\S]{0,200}Close detail|Close detail[\s\S]{0,40}/.test(lib) && !/className="absolute right-3 top-3 text-text-muted/.test(lib));
for (const [f, label] of [["components/enrollment/TogglePopover.tsx", "Close"], ["components/charts/DataProvenance.tsx", "Dismiss the rehearsal"]]) {
  ok(`${f.split("/").pop()} close is >= 28px`, /icon-sm/.test(src(f)));
}

/* ---- 4. dialogs ---- */
const fr = src("components/conversation/FinishReview.tsx");
ok("FinishReview uses DialogHeader/Body/Footer", /<DialogHeader>/.test(fr) && /<DialogBody/.test(fr) && /<DialogFooter/.test(fr));
ok("FinishReview secondary is outline", /variant="outline"[^>]*onClick=\{\(\) => onOpenChange\(false\)\}|onClick=\{\(\) => onOpenChange\(false\)\}[^>]*variant="outline"/.test(fr.replace(/\n\s*/g, " ")));
ok("FinishReview has no hand-rolled sticky footer", !/sticky bottom-0/.test(fr));
ok("FinishReview footer buttons are sm like the others", /<Button size="sm" onClick=\{onApply\}/.test(fr));
const tour = src("components/shell/StudyTour.tsx");
ok("StudyTour uses the shared dialog", /<DialogContent/.test(tour) && /<DialogHeader>/.test(tour) && /<DialogBody/.test(tour) && /<DialogFooter/.test(tour));
ok("StudyTour keeps its accessible name", /Getting started/.test(tour));
const cmd = src("components/ui/command.tsx");
ok("palette list cannot scroll sideways", /overflow-x-hidden/.test(cmd) && /min-w-0/.test(cmd));
ok("palette rows truncate", /min-w-0/.test(cmd) && /truncate/.test(src("components/shell/ProjectSwitcher.tsx")));
const tpl = src("pages/Templates.tsx");
ok("Templates detail footer is outline sm", /variant="outline" size="sm" onClick=\{onClose\}/.test(tpl));

/* ---- 3b. body-length copy is >= 13px ---- */
ok("a body-copy role exists for hints and notes", /\.type-note\s*\{/.test(css));
ok("field hints are 13px", /type-note/.test(src("components/ui/field.tsx")));

if (failures) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
