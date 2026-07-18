#!/usr/bin/env node
/* Guards the token system: no raw hex / ms / px values in components.
 * Tokens live in src/styles/*.css; every other file consumes them through
 * Tailwind utilities or var().
 *
 * Flags, in .ts/.tsx under src/ (excluding styles/):
 *   - hex colours   (#fff, #4338ca, #4338caff)
 *   - px literals    (12px), including Tailwind arbitrary values [12px]
 *   - ms/s durations (200ms, 0.4s)
 * Tailwind scale utilities (size-2.5, min-h-11, max-w-40) are unitless and
 * pass. Exit 1 on any hit. */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("../src", import.meta.url).pathname;
const SKIP_DIR = /\/styles$/;
const PATTERNS = [
  { name: "hex colour", re: /#[0-9a-fA-F]{3,8}\b/g },
  { name: "px literal", re: /\b\d+(?:\.\d+)?px\b/g },
  { name: "ms/s duration", re: /\b\d+(?:\.\d+)?m?s\b/g },
];

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) {
      if (!SKIP_DIR.test(p)) out.push(...walk(p));
    } else if (/\.(ts|tsx)$/.test(p)) {
      out.push(p);
    }
  }
  return out;
}

/* Strip comments so prose may reference durations/colours by name.
 * Tracks /* … *​/ across lines; drops // to end of line. Returns one
 * code-only string per source line (same length as input). */
function stripComments(src) {
  const out = [];
  let inBlock = false;
  for (let line of src.split("\n")) {
    let code = "";
    for (let i = 0; i < line.length; i++) {
      const two = line.slice(i, i + 2);
      if (inBlock) {
        if (two === "*/") {
          inBlock = false;
          i++;
        }
        continue;
      }
      if (two === "/*") {
        inBlock = true;
        i++;
        continue;
      }
      if (two === "//") break;
      code += line[i];
    }
    out.push(code);
  }
  return out;
}

let hits = 0;
for (const file of walk(ROOT)) {
  const code = stripComments(readFileSync(file, "utf8"));
  code.forEach((line, i) => {
    for (const { name, re } of PATTERNS) {
      re.lastIndex = 0;
      const m = re.exec(line);
      if (m) {
        console.error(
          `${file}:${i + 1}  raw ${name} "${m[0]}" — use a token instead`,
        );
        hits++;
      }
    }
  });
}

if (hits > 0) {
  console.error(`\n✗ ${hits} raw literal(s) found (NFR-12 F1). Tokens only.`);
  process.exit(1);
}
console.log("✓ no raw hex/ms/px literals in components (NFR-12 F1)");
