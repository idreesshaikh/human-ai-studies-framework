/* Exercises the layout contract's pure logic without a browser: run
 *   node --experimental-strip-types scripts/verify-layout.mjs
 *
 * Checks that, for every measure:
 *   - the root never scrolls itself (a Surface has exactly one scroller)
 *   - the body carries exactly one scroller
 *   - no bare numeric max-w-<n> escapes the four measure tokens
 */
import { MEASURES, surfaceClasses } from "../src/lib/layout.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failures++;
};

for (const measure of MEASURES) {
  const { root, body, column } = surfaceClasses(measure);
  const combined = `${root} ${body} ${column}`;

  ok(`root never scrolls itself (measure=${measure})`, !root.includes("overflow-auto"));
  ok(
    `body is the Surface's one scroller (measure=${measure})`,
    (body.match(/overflow-auto/g) ?? []).length === 1,
  );
  ok(
    `column carries the ${measure} measure token`,
    column.includes(`max-w-${measure}`),
  );
  ok(
    `no bare numeric max-w escapes the token set (measure=${measure})`,
    !/max-w-\d/.test(combined),
  );
}

// One measure should never bleed into another's class string.
const narrow = surfaceClasses("narrow").column;
const wide = surfaceClasses("wide").column;
ok("distinct measures produce distinct columns", narrow !== wide);

console.log(failures === 0 ? "\n✓ all checks pass" : `\n✗ ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
