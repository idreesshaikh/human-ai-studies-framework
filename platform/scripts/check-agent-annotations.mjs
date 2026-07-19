/* Keeps platform/docs/agent-annotations.md honest.
 *
 * Every `data-agent="name"` used in a component must be documented in the
 * conventions doc's inventory table, and every documented name must still be
 * used. A `data-agent` value is a public contract; this catches an
 * undocumented addition or a stale row before it drifts. Run:
 *   node scripts/check-agent-annotations.mjs
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("../src", import.meta.url).pathname;
const DOC = new URL("../docs/agent-annotations.md", import.meta.url).pathname;

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
}

// Primary landmark names used in code (data-agent="..."), excluding the
// secondary data-agent-* refinement attributes.
const used = new Set();
for (const file of walk(ROOT)) {
  const src = readFileSync(file, "utf8");
  for (const m of src.matchAll(/data-agent="([a-z][a-z-]*)"/g)) used.add(m[1]);
}

// Names documented in the inventory table (first `code` cell of each row).
const doc = readFileSync(DOC, "utf8");
const documented = new Set();
for (const m of doc.matchAll(/^\|\s*`([a-z][a-z-]*)`\s*\|/gm)) {
  if (m[1] !== "data-agent") documented.add(m[1]); // skip the column header cell
}

const undocumented = [...used].filter((n,) => !documented.has(n)).sort();
const stale = [...documented].filter((n,) => !used.has(n)).sort();

let ok = true;
if (undocumented.length) {
  ok = false;
  console.error(
    `✗ data-agent names used but not documented: ${undocumented.join(", ")}`);
}
if (stale.length) {
  ok = false;
  console.error(
    `✗ data-agent names documented but not used: ${stale.join(", ")}`);
}
if (ok) {
  console.log(`✓ agent annotations in sync (${used.size} names documented + used)`);
  process.exit(0);
}
console.error("Update platform/docs/agent-annotations.md to match the code.");
process.exit(1);
