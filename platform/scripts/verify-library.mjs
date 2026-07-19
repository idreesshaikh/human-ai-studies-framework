/* Exercises the migrated knowledge-layer pure logic (from the retired Svelte
 * console): the deterministic force layout and the offline seed. Run:
 *   node --experimental-strip-types scripts/verify-library.mjs
 *
 * Checks that:
 *   - the constellation layout is deterministic (replay → identical positions)
 *   - every node lands inside the canvas bounds
 *   - ingested nodes sit nearer the centre than suggestions (the anchor rule)
 *   - ingestIdForRef round-trips arxiv:/doi: refs
 */
import { layoutGraph, ingestIdForRef } from "../src/lib/forceLayout.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failures++;
};

const nodes = [
  { paperRef: "a", title: "A", year: 2024, citationCount: 100, ingested: true },
  { paperRef: "b", title: "B", year: 2023, citationCount: 40, ingested: true },
  { paperRef: "c", title: "C", year: null, citationCount: 10, ingested: false },
  { paperRef: "d", title: "D", year: null, citationCount: 5, ingested: false },
];
const edges = [
  { src: "a", dst: "b", kind: "references" },
  { src: "a", dst: "c", kind: "recommendations" },
];

const W = 640;
const H = 440;
const first = layoutGraph(nodes, edges, { width: W, height: H });
const second = layoutGraph(nodes, edges, { width: W, height: H });

ok(
  "layout is deterministic (byte-identical replay)",
  JSON.stringify(first) === JSON.stringify(second),
);
ok(
  "every node lands inside the canvas",
  first.every((n) => n.x >= 0 && n.x <= W && n.y >= 0 && n.y <= H),
);

const cx = W / 2;
const cy = H / 2;
const dist = (n) => Math.hypot(n.x - cx, n.y - cy);
const ingestedMean =
  first.filter((n) => n.ingested).reduce((s, n) => s + dist(n), 0) / 2;
const suggestedMean =
  first.filter((n) => !n.ingested).reduce((s, n) => s + dist(n), 0) / 2;
ok(
  "ingested nodes anchor nearer the centre than suggestions",
  ingestedMean < suggestedMean,
  `ingested ${ingestedMean.toFixed(0)} < suggested ${suggestedMean.toFixed(0)}`,
);

ok(
  "ingestIdForRef round-trips arxiv: and doi:",
  ingestIdForRef("arxiv:2302.06590").arxivId === "2302.06590" &&
    ingestIdForRef("doi:10.1/x").doi === "10.1/x" &&
    ingestIdForRef("corpus:foo") === null,
);

console.log(
  failures === 0 ? "\n✓ all checks pass" : `\n✗ ${failures} check(s) failed`,
);
process.exit(failures === 0 ? 0 : 1);
