/* Form controls: one control spec, one field layout, one dialog structure.
 * Pure helpers plus source-level checks (no browser). Run:
 *   node --experimental-strip-types scripts/verify-form-controls.mjs
 */
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};
const root = new URL("../src/", import.meta.url).pathname;
const src = (p) => (existsSync(root + p) ? readFileSync(root + p, "utf8") : "");
const css = src("styles/index.css");
const block = (selector) => {
  const i = css.indexOf(selector);
  return i < 0 ? "" : css.slice(i, css.indexOf("}", i));
};

/* ---- pure helpers ---- */
const { stepNumber } = await import("../src/lib/fieldStep.ts").catch(() => ({}));
ok("stepNumber exists", typeof stepNumber === "function");
if (stepNumber) {
  ok("step up", stepNumber("10", 1, { min: 4, max: 20 }) === "11");
  ok("step down", stepNumber("10", -1, { min: 4, max: 20 }) === "9");
  ok("clamps at max", stepNumber("20", 1, { min: 4, max: 20 }) === "20");
  ok("clamps at min", stepNumber("4", -1, { min: 4, max: 20 }) === "4");
  ok("blank starts at min", stepNumber("", 1, { min: 15, max: 180 }) === "15");
  ok("custom step", stepNumber("30", 1, { min: 15, max: 180, step: 5 }) === "35");
  ok("below min snaps up", stepNumber("2", 1, { min: 4, max: 20 }) === "4");
  ok("decimals do not drift", stepNumber("0.1", 1, { step: 0.1 }) === "0.2");
  ok("scientific notation retains precision", stepNumber("0.0000001", 1, { step: 1e-7 }) === "2e-7");
  ok("fractional bounds are not rounded out of range", stepNumber("5", -1, { min: 4.5 }) === "4.5");
  ok("non-numeric treated as blank", stepNumber("abc", 1, { min: 4 }) === "4");
}
const { scrollEdges } = await import("../src/lib/scrollEdges.ts").catch(() => ({}));
ok("scrollEdges exists", typeof scrollEdges === "function");
if (scrollEdges) {
  const a = scrollEdges(0, 300, 300);
  ok("not scrollable: no shade", !a.above && !a.below);
  const b = scrollEdges(0, 300, 600);
  ok("top of a long body: shade below only", !b.above && b.below);
  const c = scrollEdges(150, 300, 600);
  ok("middle: shade both", c.above && c.below);
  const d = scrollEdges(300, 300, 600);
  ok("bottom: shade above only", d.above && !d.below);
  ok("sub-pixel rounding tolerated", !scrollEdges(299.6, 300, 600).below);
}

const { validateManualProtocol } = await import("../src/lib/manualProtocol.ts").catch(() => ({}));
ok("validateManualProtocol exists", typeof validateManualProtocol === "function");
if (validateManualProtocol) {
  const good = { title: "Study one", researchQuestions: ["Does AI change time?"], conditions: ["AI", "None"], participantDescription: "Developers", plannedParticipants: "12", taskDescription: "Fix a bug", sessionMinutes: "45", measures: ["time"] };
  ok("valid protocol has no errors", validateManualProtocol(good).length === 0);
  ok("fractional counts are rejected before the server", validateManualProtocol({ ...good, plannedParticipants: "12.5" }).some(e => e.id === "manual-planned"));
  ok("fractional minutes are rejected before the server", validateManualProtocol({ ...good, sessionMinutes: "45.5" }).some(e => e.id === "manual-minutes"));
  const bad = validateManualProtocol({ ...good, title: "ab", plannedParticipants: "2", sessionMinutes: "5", measures: [], researchQuestions: ["short"] });
  const ids = bad.map((e) => e.id);
  ok("errors name field ids in form order", ["manual-title", "manual-rq-0", "manual-planned", "manual-minutes", "manual-outcomes"].every((i) => ids.includes(i)) && ids.indexOf("manual-title") < ids.indexOf("manual-minutes"));
  ok("each error has a plain message and label", bad.every((e) => e.message.length > 5 && e.label.length > 2));
  ok("more than six outcomes is an error", validateManualProtocol({ ...good, measures: ["a","b","c","d","e","f","g"] }).some((e) => e.id === "manual-outcomes"));
}

/* ---- one control spec ---- */
const input = src("components/ui/input.tsx");
const textarea = src("components/ui/textarea.tsx");
const select = src("components/ui/select.tsx");
ok("input uses the control spec", /\bcontrol\b/.test(input));
ok("textarea uses the control spec", /\bcontrol\b/.test(textarea));
ok("select uses the control spec", /\bcontrol\b/.test(select));
ok("select has no drop shadow", !/shadow-/.test(select));
ok("select no longer sets its own height or border", !/\bh-10\b|border-border|bg-surface-raised/.test(select));
ok("input sets no shadow, own height or own border", !/shadow-|\bh-9\b|border-control-edge/.test(input));
const control = block(".control {");
ok(".control defined from tokens", /var\(--control-height\)/.test(control) && /var\(--control-edge\)/.test(control));
ok(".control has no shadow", !/box-shadow:\s*[^n;\s]/.test(control));
ok("control tokens exist", /--control-height:/.test(src("styles/tokens.css")));
ok("one focus ring: control focus is a single 2px outline", /\.control:focus-visible[\s\S]*?outline:\s*var\(--rule-ring\)?\s*|\.control:focus-visible[^}]*outline:\s*2px solid var\(--focus-ring\)/.test(css));
ok("focus ring covers the border (negative offset)", /\.control:focus-visible[^}]*outline-offset:\s*calc\(-1 \* var\(--rule-hair\)\)/.test(css));
ok("group focus uses the same ring", /\.control-group:focus-within[^}]*outline:\s*2px solid var\(--focus-ring\)/.test(css));
ok("forced-colors focus handled", /forced-colors: active\)[\s\S]*Highlight/.test(css));
ok("invalid state", /\.control\[aria-invalid="true"\]/.test(css));
ok("read-only state", /\.control:read-only/.test(css));
ok("native number spinners hidden", /-webkit-inner-spin-button/.test(css) && /appearance:\s*textfield/.test(css));
ok("input passes unit to a group, not a detached box", /control-group/.test(input) && !/bg-zone-9/.test(input));
ok("unit suffix is plain muted text", /control-suffix/.test(input));
ok("input offers an integrated stepper", /stepNumber/.test(input) && /stepper/.test(input));
ok("textarea can auto-grow without a grip", /autoGrow/.test(textarea) && /resize:\s*none|resize-none/.test(textarea + css));

/* ---- checkbox primitive ---- */
const cbFile = src("components/ui/checkbox.tsx");
ok("Checkbox primitive exists", /export (const|function) Checkbox/.test(cbFile));
ok("checkbox is restyled natively", /\.checkbox \{[^}]*appearance:\s*none/.test(css));
ok("checked state is an accent fill", /\.checkbox:checked[^}]*background[^}]*var\(--accent\)/.test(css));
ok("unchecked is an empty bordered box", /\.checkbox \{[^}]*border:[^;]*var\(--control-edge\)/.test(css));
ok("checkbox has a check mark", /\.checkbox::before/.test(css));
ok("checkbox supports indeterminate", /\.checkbox:indeterminate/.test(css) && /indeterminate/.test(cbFile));
ok("checkbox row meets the 24px target", /\.checkbox-row \{[^}]*min-height:\s*var\(--target-min\)/.test(css));
ok("checkbox forced-colors", /forced-colors: active\)[\s\S]*\.checkbox/.test(css));
const rawBoxes = [];
(function walk(dir) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.tsx$/.test(p) && !p.endsWith("ui/checkbox.tsx") && /type=["'{]+(checkbox|radio)/.test(readFileSync(p, "utf8")))
      rawBoxes.push(p.replace(root, ""));
  }
})(root);
ok("no raw type=checkbox / type=radio outside the primitive", rawBoxes.length === 0, rawBoxes.join(", "));

/* ---- field layout ---- */
const field = src("components/ui/field.tsx");
ok("Field exists", /export (const|function) Field\b/.test(field));
ok("Field wires aria-describedby and aria-invalid", /aria-describedby/.test(field) && /aria-invalid/.test(field));
ok("Field renders hint and error slots", /hint/.test(field) && /error/.test(field) && /aria-live/.test(field));
ok("error text is not colour alone (icon)", /AlertCircle|CircleAlert|TriangleAlert/.test(field));
ok("label is the label type role", /type-label/.test(src("components/ui/label.tsx")) && !/type-body/.test(src("components/ui/label.tsx")));

/* ---- dialog structure ---- */
const dialog = src("components/ui/dialog.tsx");
ok("dialog exports header/body/footer", /export const DialogHeader/.test(dialog) && /export const DialogBody/.test(dialog) && /export const DialogFooter/.test(dialog));
ok("dialog height capped in dvh", /dvh/.test(dialog + block(".dialog {")));
ok("footer is sticky/fixed in the flex column", /dialog-footer/.test(css) && /shrink-0|flex-shrink: 0/.test(dialog + css));
ok("scroll shade only when scrollable", /scrollEdges/.test(dialog) && /data-shade|data-more/.test(css));
ok("mobile sheet", /max-width: 40rem\)[\s\S]*\.dialog/.test(css));
ok("reduced motion respected for dialog", /prefers-reduced-motion/.test(css));

/* ---- ManualProtocolDialog ---- */
const manual = src("components/conversation/ManualProtocolDialog.tsx");
ok("manual dialog has a footer", /<DialogFooter/.test(manual));
ok("manual dialog uses Field + Checkbox", /<Field\b/.test(manual) && /<Checkbox\b/.test(manual));
ok("manual dialog has an error summary alert with links", /role="alert"/.test(manual) && /href=\{`#/.test(manual));
ok("manual dialog shows 'N of 6 selected'", /of (6|\{MAX_OUTCOMES\}) selected/.test(manual));
ok("manual dialog grouped into sections", ["Study", "Design", "Participants", "Task", "Outcomes"].every((h) => manual.includes(`>${h}<`)));
ok("research questions auto-grow", /autoGrow/.test(manual));
ok("session length is an input group with stepper", /unit="min"/.test(manual) && /stepper/.test(manual));

/* ---- placeholders fit ---- */
const long = [];
(function walk(dir) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.tsx$/.test(p)) {
      for (const m of readFileSync(p, "utf8").matchAll(/placeholder=(?:"([^"]*)"|\{?"([^"]*)"\}?)/g)) {
        const t = m[1] ?? m[2] ?? "";
        if (t.length > 36) long.push(`${p.replace(root, "")}: ${t}`);
      }
    }
  }
})(root);
ok("no placeholder longer than 36 characters", long.length === 0, long.join(" | "));

/* ---- no one-off controls ---- */
const OWNED = new Set(["components/conversation/ConversationView.tsx"]); /* composer: its wrapper owns the ring */
const oneOffs = [];
(function walk(dir) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.tsx$/.test(p)) {
      const rel = p.replace(root, "");
      if (rel.startsWith("components/ui/") || OWNED.has(rel)) continue;
      const text = readFileSync(p, "utf8");
      for (const m of text.matchAll(/<(input|select|textarea)\b([^>]*)>/g))
        if (!(m[1] === "input" && /type="(file|range)"/.test(m[2]))) oneOffs.push(`${rel}: raw <${m[1]}>`);
      for (const m of text.matchAll(/<(Input|Textarea|Select)\b[^>]*?className=(?:"([^"]*)"|\{`([^`]*)`\})/g)) {
        const cls = m[2] ?? m[3] ?? "";
        if (/(^|\s)(h-\d|min-h-\d|rounded-|shadow-|border(\s|$)|border-|bg-|py-|px-)/.test(cls)) oneOffs.push(`${rel}: <${m[1]}> className "${cls}"`);
      }
    }
  }
})(root);
ok("no raw input/select/textarea and no per-field height, radius, shadow, border or fill", oneOffs.length === 0, oneOffs.join(" | "));

/* The tick is a ::before sized 100% inside an inline-grid. In an auto-sized grid
 * track that resolves to 0px and the mark never shows (seen live: 0x0). The box
 * must give the pseudo-element a definite track. */
const checkboxRule = (css.match(/\n\s*\.checkbox\s*\{[^}]*\}/) ?? [""])[0];
ok("the checkbox gives its tick a definite grid track (not 0px)",
  /grid-template(-columns|-rows)?\s*:/.test(checkboxRule),
  "the .checkbox rule needs an explicit grid template");

if (failures) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
