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
 *   - labels reveal by selection, focus, or zoomed-in radius — never always
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
} from "../src/lib/constellationView.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? ` — ${detail}` : ""}`);
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

console.log(
  failures === 0 ? "\n✓ all checks pass" : `\n✗ ${failures} check(s) failed`,
);
process.exit(failures === 0 ? 0 : 1);
