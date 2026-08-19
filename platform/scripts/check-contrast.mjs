#!/usr/bin/env node
/* Measures every text/background and rule/background pairing the palette
 * promises, straight out of tokens.css, and fails on anything under the bar
 * NFR-12 sets: 4.5:1 for text, 3:1 for large text, rules and controls.
 *
 * The palette is a claim; this is the check. A colour picked by eye and
 * described as "muted" is how a 3.3:1 label ships. */
import { readFileSync } from "node:fs";

const CSS = readFileSync(new URL("../src/styles/tokens.css", import.meta.url), "utf8");

/** Every `--name: #hex;` in one `:root`-ish block, in source order. */
function block(selector) {
  const start = CSS.indexOf(selector);
  if (start < 0) throw new Error(`no block for ${selector}`);
  const open = CSS.indexOf("{", start);
  let depth = 0;
  let i = open;
  for (; i < CSS.length; i++) {
    if (CSS[i] === "{") depth++;
    else if (CSS[i] === "}" && --depth === 0) break;
  }
  const body = CSS.slice(open, i);
  const vars = new Map();
  for (const m of body.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    vars.set(m[1], m[2].trim());
  }
  return vars;
}

/** Resolves `var(--x)` chains down to a literal hex. */
function resolve(vars, name, seen = new Set()) {
  let v = vars.get(name);
  if (v === undefined) throw new Error(`undefined token ${name}`);
  const ref = v.match(/^var\((--[\w-]+)\)$/);
  if (ref) {
    if (seen.has(name)) throw new Error(`token cycle at ${name}`);
    seen.add(name);
    return resolve(vars, ref[1], seen);
  }
  return v;
}

function rgb(hex) {
  const h = hex.replace("#", "").trim();
  const full = h.length === 3 ? [...h].map((c) => c + c).join("") : h;
  if (!/^[0-9a-fA-F]{6}$/.test(full)) throw new Error(`not a hex colour: ${hex}`);
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16) / 255);
}

function luminance(hex) {
  const [r, g, b] = rgb(hex).map((c) =>
    c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  );
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a, b) {
  const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m);
  return (x + 0.05) / (y + 0.05);
}

/* fg, bg, floor, what it is. The floor is 4.5 wherever the pairing carries
 * running text and 3 where it carries a rule, a control edge, or large type. */
const PAIRS = [
  ["--text", "--bg", 4.5, "body text on the ground"],
  ["--text", "--surface", 4.5, "body text on a plate"],
  ["--text", "--surface-raised", 4.5, "body text on a raised plate"],
  ["--text-muted", "--bg", 4.5, "secondary text on the ground"],
  ["--text-muted", "--surface", 4.5, "secondary text on a plate"],
  ["--text-muted", "--surface-raised", 4.5, "secondary text on a raised plate"],
  ["--accent", "--bg", 4.5, "accent text on the ground"],
  ["--accent", "--surface", 4.5, "accent text on a plate"],
  ["--accent", "--accent-wash", 4.5, "accent text on its own wash"],
  ["--accent-contrast", "--accent", 4.5, "label on a filled accent control"],
  ["--critical", "--bg", 4.5, "error text on the ground"],
  ["--critical", "--surface", 4.5, "error text on a plate"],
  ["--paper", "--ink", 4.5, "label on a filled ink control"],
  ["--unsourced", "--bg", 4.5, "the unsourced label on the ground"],
  ["--unsourced", "--surface", 4.5, "the unsourced label on a plate"],
  ["--superseded", "--bg", 4.5, "a superseded line on the ground"],
  ["--superseded", "--surface", 4.5, "a superseded line on a plate"],
  ["--control-edge", "--bg", 3, "a control's edge on the ground"],
  ["--control-edge", "--surface", 3, "a control's edge on a plate"],
  ["--control-edge", "--surface-raised", 3, "a control's edge on a raised plate"],
  ["--accent", "--surface", 3, "the accent as a control edge"],
  ["--focus-ring", "--bg", 3, "the focus ring on the ground"],
  ["--focus-ring", "--surface", 3, "the focus ring on a plate"],
  ["--mark", "--surface", 3, "a magnitude mark on a plate"],
  ["--mark", "--bg", 3, "a magnitude mark on the ground"],
];

let failures = 0;
for (const [selector, rendition] of [
  [":root {", "light"],
  [':root[data-theme="dark"]', "dark"],
]) {
  const vars = block(selector);
  console.log(`\n${rendition}`);
  for (const [fg, bg, floor, what] of PAIRS) {
    const r = ratio(resolve(vars, fg), resolve(vars, bg));
    const ok = r >= floor;
    if (!ok) failures++;
    console.log(
      `  ${ok ? "✓" : "✗"} ${r.toFixed(2)}:1 (needs ${floor}) — ${what}`,
    );
  }
}

console.log(
  failures ? `\n✗ ${failures} pairing(s) under the bar` : "\n✓ every pairing clears its floor",
);
process.exit(failures ? 1 : 0);
