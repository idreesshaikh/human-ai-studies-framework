/* Exercises the blink comparator's plate arithmetic (the signature interaction
 * of the study workspace). Run:
 *   node --experimental-strip-types scripts/verify-comparator.mjs
 *
 * Checks that:
 *   - the +/- marker is stripped, so both plates line up character for
 *     character and only genuinely changed text appears to move
 *   - a first compile (all additions) is recognised as having no earlier
 *     version, rather than blinking to an empty plate
 *   - context lines sit at the SAME index in both plates, which is the whole
 *     premise of the instrument
 *   - the reserved row count covers the tallest plate, so a shorter plate's
 *     turn cannot collapse the layout
 *   - a removal survives into the record, struck rather than erased
 */
import { buildPlates, hasEarlierVersion } from "../src/lib/comparator.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};

const L = (line, kind) => ({ line, kind });

// A first compile: every line is an addition.
const firstCompile = [
  L("+protocolVersion: 4", "add"),
  L("+study:", "add"),
  L("+  id: draft", "add"),
];

// A later compile: context, one removal, one addition.
const amended = [
  L(" protocolVersion: 4", "context"),
  L(" study:", "context"),
  L("-  planned: 1", "remove"),
  L("+  planned: 24", "add"),
  L(" phases:", "context"),
];

// ---- marker stripping ----------------------------------------------------
{
  const p = buildPlates(amended);
  ok(
    "the + marker is stripped from an addition",
    p.after.some((d) => d.line === "  planned: 24"),
    p.after.map((d) => d.line).join(" | "),
  );
  ok(
    "the - marker is stripped from a removal",
    p.before.some((d) => d.line === "  planned: 1"),
    p.before.map((d) => d.line).join(" | "),
  );
  ok(
    "no plate line still carries a leading +/-",
    [...p.before, ...p.after, ...p.record].every((d) => !/^[+-]/.test(d.line)),
  );
}

// ---- context lines hold still -------------------------------------------
{
  const p = buildPlates(amended);
  // "protocolVersion" and "study:" precede the change in both plates, so they
  // must occupy identical indices. If they don't, unchanged text moves.
  ok(
    "context lines occupy the same index in both plates",
    p.before[0].line === p.after[0].line && p.before[1].line === p.after[1].line,
  );
  ok(
    "each plate holds exactly one of the changed pair",
    p.before.filter((d) => d.kind === "remove").length === 1 &&
      p.after.filter((d) => d.kind === "add").length === 1 &&
      p.before.every((d) => d.kind !== "add") &&
      p.after.every((d) => d.kind !== "remove"),
  );
}

// ---- the first-compile case --------------------------------------------
{
  const p = buildPlates(firstCompile);
  ok("a first compile has an empty before plate", p.before.length === 0);
  ok("a first compile is flagged firstVersion", p.firstVersion === true);
  ok(
    "a first compile reports no earlier version",
    hasEarlierVersion(firstCompile) === false,
  );
  ok(
    "an amended compile reports an earlier version",
    hasEarlierVersion(amended) === true,
  );
}

// ---- the container reserves the tallest plate ---------------------------
{
  const p = buildPlates(amended);
  ok(
    "reserved rows cover the tallest plate",
    p.rows >= p.record.length &&
      p.rows >= p.before.length &&
      p.rows >= p.after.length,
    `rows=${p.rows} record=${p.record.length} before=${p.before.length} after=${p.after.length}`,
  );
}

// ---- nothing is erased --------------------------------------------------
{
  const p = buildPlates(amended);
  ok(
    "the record keeps the removed line, to be struck rather than erased",
    p.record.some((d) => d.kind === "remove" && d.line === "  planned: 1"),
  );
  ok(
    "the record keeps every line the diff carried",
    p.record.length === amended.length,
  );
}

// ---- degenerate input ---------------------------------------------------
{
  const p = buildPlates([]);
  ok("an empty diff produces empty plates without throwing", p.rows === 0 && p.firstVersion === true);
  const h = buildPlates([L("", "hunk"), L("+a", "add")]);
  ok("a hunk divider is carried through untouched", h.record[0].kind === "hunk");
}

console.log(failures ? `\n✗ ${failures} check(s) failed` : "\n✓ all checks pass");
process.exit(failures ? 1 : 0);
