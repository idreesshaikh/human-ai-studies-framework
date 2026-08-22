/* Exercises the Obsidian-style constellation view's pure decision logic
 * (`src/lib/constellationView.ts`) without a DOM. Run:
 *   node --experimental-strip-types scripts/verify-constellation.mjs
 *
 * Checks that:
 *   - node radius grows by degree, not raw citation count, and clamps
 *   - adjacency is built both directions from a directed edge list
 *   - the active neighbourhood is the focus node plus only its neighbours
 *   - node/edge opacity match the at-rest vs. focused states
 *   - "incident" means touching the focus node itself, not just its
 *     neighbourhood (two neighbours citing each other are "dimmed")
 *   - labels reveal by selection, focus, or zoomed-in radius  -  never always
 *     (the dense mode above the always-on node-count limit)
 *   - the label mode flips from always-on to zoom-gated at the node-count
 *     threshold, so a small study reads by name and a large one stays legible
 *   - drift is deterministic per ref and never depends on render order
 *   - the settle alpha schedule decays and the node-count gate is honoured
 */
import {
  nodeRadius,
  buildAdjacency,
  activeNeighbourhood,
  nodeOpacity,
  edgeState,
  edgeOpacity,
  labelVisible,
  labelMode,
  driftPhase,
  driftOffset,
  nextSettleAlpha,
  shouldSettle,
  NODE_RADIUS_MIN,
  NODE_RADIUS_MAX,
  NEUTRAL_NODE_OPACITY,
  DIMMED_NODE_OPACITY,
  NEUTRAL_EDGE_OPACITY,
  INCIDENT_EDGE_OPACITY,
  DIMMED_EDGE_OPACITY,
  SETTLE_ALPHA0,
  SETTLE_NODE_LIMIT,
  LABEL_ALWAYS_NODE_LIMIT,
  LENSES,
  lensEdges,
  lensNodes,
  lensCounts,
  curateGraph,
  MAX_SUGGESTED_NODES,
  MAX_SUGGESTIONS_PER_ANCHOR,
} from "../src/lib/constellationView.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};

// ------------------------------------------------------------- nodeRadius
ok("a disconnected node gets the minimum radius", nodeRadius(0) === NODE_RADIUS_MIN);
ok("radius grows with degree", nodeRadius(10) > nodeRadius(1));
ok(
  "radius clamps at the top for an extreme hub",
  nodeRadius(10_000) === NODE_RADIUS_MAX,
);
ok("radius never goes negative or below the floor", nodeRadius(-5) === NODE_RADIUS_MIN);

// ------------------------------------------------------------- adjacency
const edges = [
  { src: "a", dst: "b", kind: "references" },
  { src: "a", dst: "c", kind: "recommendations" },
];
const adjacency = buildAdjacency(edges);
ok(
  "adjacency is built both directions",
  adjacency.get("a")?.has("b") && adjacency.get("b")?.has("a"),
);
ok("an unconnected node has no adjacency entry", !adjacency.has("d"));

// ------------------------------------------------------- active neighbourhood
ok("nothing focused → empty active set", activeNeighbourhood(null, adjacency).size === 0);
const active = activeNeighbourhood("a", adjacency);
ok(
  "focusing a hub activates itself and its neighbours",
  active.has("a") && active.has("b") && active.has("c") && active.size === 3,
);
ok(
  "focusing a leaf activates only itself and its one neighbour",
  [...activeNeighbourhood("b", adjacency)].sort().join(",") === "a,b",
);

// ------------------------------------------------------------- opacity
ok("at rest, every node is at full opacity", nodeOpacity("d", new Set()) === NEUTRAL_NODE_OPACITY);
ok("the focused node itself is at full opacity", nodeOpacity("a", active) === NEUTRAL_NODE_OPACITY);
ok(
  "a node outside the active neighbourhood dims",
  nodeOpacity("z", active) === DIMMED_NODE_OPACITY,
);

// --------------------------------------------------------------- edgeState
ok("at rest every edge is neutral", edgeState("a", "b", null) === "neutral");
ok("an edge touching the focus node is incident", edgeState("a", "b", "a") === "incident");
ok(
  "an edge touching the focus node from the other end is still incident",
  edgeState("b", "a", "a") === "incident",
);
ok(
  "an edge between two neighbours of the focus (not the focus itself) dims, not incident",
  edgeState("b", "c", "a") === "dimmed",
);
ok(
  "edge opacity matches each state",
  edgeOpacity("neutral") === NEUTRAL_EDGE_OPACITY &&
    edgeOpacity("incident") === INCIDENT_EDGE_OPACITY &&
    edgeOpacity("dimmed") === DIMMED_EDGE_OPACITY,
);

// ------------------------------------------------------------ labelVisible
ok(
  "a selected node's label always shows, even zoomed out and unfocused",
  labelVisible({ selected: true, inFocusNeighbourhood: false, radius: 3.5, zoomK: 0.4 }),
);
ok(
  "a node in the focus neighbourhood always shows its label",
  labelVisible({ selected: false, inFocusNeighbourhood: true, radius: 3.5, zoomK: 0.4 }),
);
ok(
  "an unremarkable node zoomed out shows no label",
  !labelVisible({ selected: false, inFocusNeighbourhood: false, radius: 3.5, zoomK: 1 }),
);
ok(
  "zooming in reveals the same node's label",
  labelVisible({ selected: false, inFocusNeighbourhood: false, radius: 3.5, zoomK: 4 }),
);

// --------------------------------------------------------------- labelMode
ok(
  "a study-sized graph gets always-on labels",
  labelMode(LABEL_ALWAYS_NODE_LIMIT) === "always",
);
ok(
  "a small graph gets always-on labels",
  labelMode(3) === "always",
);
ok(
  "a harvested neighbourhood past the limit degrades to zoom-gated labels",
  labelMode(LABEL_ALWAYS_NODE_LIMIT + 1) === "dense",
);
ok(
  "an empty graph still gets always-on labels (no labels to clash)",
  labelMode(0) === "always",
);

// --------------------------------------------------------------- drift
ok(
  "drift phase is deterministic for the same ref",
  driftPhase("corpus:same-ref") === driftPhase("corpus:same-ref"),
);
ok(
  "different refs get different phases (no coincidental collision for these two)",
  driftPhase("corpus:paper-one") !== driftPhase("corpus:paper-two"),
);
ok(
  "drift at t=0 for two different refs is not identical (not one global wave)",
  JSON.stringify(driftOffset("corpus:paper-one", 0)) !==
    JSON.stringify(driftOffset("corpus:paper-two", 0)),
);
ok(
  "drift never exceeds its amplitude",
  Math.abs(driftOffset("corpus:paper-one", 1.23).dx) <= 1.2 + 1e-9,
);

// ------------------------------------------------------------- settle
ok("settle alpha decays each frame", nextSettleAlpha(SETTLE_ALPHA0) < SETTLE_ALPHA0);
ok(
  "repeated decay approaches zero, not a fixed floor",
  Array.from({ length: 200 }).reduce((a) => nextSettleAlpha(a), SETTLE_ALPHA0) < 0.001,
);
ok("a typical neighbourhood settles", shouldSettle(40));
ok("an empty graph never settles", !shouldSettle(0));
ok(
  "a harvested neighbourhood past the node limit skips the settle animation",
  !shouldSettle(SETTLE_NODE_LIMIT + 1),
);

// ------------------------------------------------------------------ lenses
// A study with two of its own papers, plus one suggestion arriving down each
// of the three relations  -  so every lens has exactly one thing to show and
// the anchors are shared.
const LENS_NODES = [
  { paperRef: "own-a", ingested: true },
  { paperRef: "own-b", ingested: true },
  { paperRef: "earlier", ingested: false },
  { paperRef: "later", ingested: false },
  { paperRef: "similar", ingested: false },
];
const LENS_EDGES = [
  { src: "own-a", dst: "earlier", kind: "references" },
  { src: "later", dst: "own-a", kind: "citations" },
  { src: "own-b", dst: "similar", kind: "recommendations" },
];

ok("the four lenses are all/earlier/later/similar",
  LENSES.map((l) => l.id).join(",") ===
    "all,references,citations,recommendations");
ok("every lens carries a researcher-facing label and a hint",
  LENSES.every((l) => l.label.length > 0 && l.hint.length > 0));

ok("`all` keeps every edge, by identity (no allocation in the common case)",
  lensEdges(LENS_EDGES, "all") === LENS_EDGES);
ok("a lens keeps only its own relation",
  lensEdges(LENS_EDGES, "citations").every((e) => e.kind === "citations") &&
    lensEdges(LENS_EDGES, "citations").length === 1);

// The anchor rule: a researcher's own papers never vanish, even when the
// active lens leaves them with no edges at all.
const earlierOnly = lensNodes(LENS_NODES, LENS_EDGES, "references");
ok("every ingested paper survives every lens",
  LENSES.every(({ id }) =>
    lensNodes(LENS_NODES, LENS_EDGES, id).filter((n) => n.ingested).length === 2));
ok("`own-b` survives a lens that leaves it with no edges",
  earlierOnly.some((n) => n.paperRef === "own-b"));
ok("a suggestion survives only on the lens that introduced it",
  earlierOnly.some((n) => n.paperRef === "earlier") &&
    !earlierOnly.some((n) => n.paperRef === "later") &&
    !earlierOnly.some((n) => n.paperRef === "similar"));
ok("`all` keeps every node, by identity",
  lensNodes(LENS_NODES, LENS_EDGES, "all") === LENS_NODES);

// The badge counts suggestions, not nodes  -  the anchors are not what a
// researcher is choosing between.
const counts = lensCounts(LENS_NODES, LENS_EDGES);
ok("each lens counts exactly its own suggestions, never the anchors",
  counts.references === 1 && counts.citations === 1 &&
    counts.recommendations === 1);
ok("`all` counts every suggestion", counts.all === 3);
ok("a lens with nothing harvested counts zero rather than going missing",
  lensCounts(LENS_NODES, [], "citations") &&
    lensCounts(LENS_NODES, []).citations === 0);

// --------------------------------------------------------- graph curation
const CURATED_NODES = [
  { paperRef: "anchor-a", ingested: true, citationCount: 80 },
  { paperRef: "anchor-b", ingested: true, citationCount: 60 },
  ...Array.from({ length: 80 }, (_, i) => ({
    paperRef: `suggestion-${i}`,
    ingested: false,
    citationCount: 100 - i,
  })),
];
const CURATED_EDGES = CURATED_NODES.slice(2).map((node, i) => ({
  src: i % 2 === 0 ? "anchor-a" : "anchor-b",
  dst: node.paperRef,
  kind: i % 3 === 0 ? "references" : i % 3 === 1 ? "citations" : "recommendations",
}));
const curated = curateGraph({ nodes: CURATED_NODES, edges: CURATED_EDGES });
ok("graph curation keeps every ingested anchor", curated.nodes.filter((n) => n.ingested).length === 2);
ok("graph curation caps the suggestion neighbourhood", curated.nodes.filter((n) => !n.ingested).length <= MAX_SUGGESTED_NODES);
ok("graph curation caps each anchor's suggestions", CURATED_NODES.slice(0, 2).every((anchor) =>
  curated.edges.filter((e) => e.src === anchor.paperRef || e.dst === anchor.paperRef).length <=
    MAX_SUGGESTIONS_PER_ANCHOR));
ok("graph curation drops unsupported internal edge kinds",
  curateGraph({
    nodes: [{ paperRef: "own", ingested: true }, { paperRef: "via", ingested: false }],
    edges: [{ src: "own", dst: "via", kind: "harvested-via" }],
  }).edges.length === 0);

console.log(
  failures === 0 ? "\n✓ all checks pass" : `\n✗ ${failures} check(s) failed`,
);
process.exit(failures === 0 ? 0 : 1);
