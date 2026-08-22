/* Exercises the migrated knowledge-layer pure logic (from the retired Svelte
 * console): the deterministic force layout and the offline seed. Run:
 *   node --experimental-strip-types scripts/verify-library.mjs
 *
 * Checks that:
 *   - the constellation layout is deterministic (replay → identical positions)
 *   - every node lands inside the canvas bounds
 *   - ingested nodes sit nearer the centre than suggestions (the anchor rule)
 *   - ingestIdForRef round-trips arxiv:/doi: refs
 *   - the exact node positions match a golden snapshot (below)
 *
 * The golden snapshot exists because the other three checks would all still
 * pass after a refactor that moved every node to a different (x, y)  -  none
 * of them pin the actual layout. It is the safety net for the Obsidian-style
 * constellation rewrite: `layoutGraph`'s body must not change underneath it
 * (`forceLayout.ts`'s new helpers are additive-only), so this snapshot should
 * never need updating by that work. If a *deliberate* layout change ever
 * needs one, regenerate it by running this fixture through `layoutGraph` and
 * copying its rounded output back in  -  never hand-edit the numbers.
 */
import {
  layoutGraph,
  ingestIdForRef,
  degreeMap,
  relaxStep,
} from "../src/lib/forceLayout.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
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

// ---------------------------------------------------------- golden snapshot
const round2 = (v) => Math.round(v * 100) / 100;
const GOLDEN = {
  a: { x: 397.74, y: 225.05 },
  b: { x: 324.75, y: 313.98 },
  c: { x: 122.7, y: 220.15 },
  d: { x: 320.0, y: 15.29 },
};
for (const n of first) {
  const g = GOLDEN[n.paperRef];
  ok(
    `${n.paperRef} lands at its golden position`,
    g && round2(n.x) === g.x && round2(n.y) === g.y,
    `got (${round2(n.x)}, ${round2(n.y)}), want (${g?.x}, ${g?.y})`,
  );
}

// ----------------------------------------------------------- degreeMap
const degrees = degreeMap(nodes, edges);
ok("degreeMap counts in + out edges", degrees.get("a") === 2);
ok("degreeMap counts a node with one edge", degrees.get("b") === 1);
ok("degreeMap gives an unconnected node degree 0", degrees.get("d") === 0);

// ----------------------------------------------------------- relaxStep
const settleFrom = layoutGraph(nodes, edges, { width: W, height: H });
const relaxed = relaxStep(settleFrom, edges, 0.35, { width: W, height: H });
ok(
  "relaxStep doesn't touch layoutGraph's own output",
  JSON.stringify(settleFrom) === JSON.stringify(first),
);
ok(
  "relaxStep returns one position per node, still inside the canvas",
  relaxed.length === settleFrom.length &&
    relaxed.every((n) => n.x >= 0 && n.x <= W && n.y >= 0 && n.y <= H),
);
ok(
  "a zero alpha leaves positions unchanged",
  JSON.stringify(relaxStep(settleFrom, edges, 0, { width: W, height: H })) ===
    JSON.stringify(settleFrom),
);

console.log(
  failures === 0 ? "\n✓ all checks pass" : `\n✗ ${failures} check(s) failed`,
);
process.exit(failures === 0 ? 0 : 1);
