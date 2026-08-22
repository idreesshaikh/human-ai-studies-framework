/* Pure decision logic for the Obsidian-style constellation view  -  kept out
 * of the component so `verify-library.mjs` can assert every branch without
 * a DOM (the project has no component test tooling; see PROJECT_GUIDE /
 * docs/roadmap). `Constellation.tsx` is thin glue over these functions:
 * state wiring, SVG markup, and the pointer/keyboard event plumbing. */

export const NODE_RADIUS_MIN = 9;
export const NODE_RADIUS_MAX = 34;
export const LABEL_ZOOM_THRESHOLD = 12;
export const NEUTRAL_EDGE_OPACITY = 0.32;
export const INCIDENT_EDGE_OPACITY = 0.86;
export const DIMMED_EDGE_OPACITY = 0.06;
export const NEUTRAL_NODE_OPACITY = 1;
export const DIMMED_NODE_OPACITY = 0.14;
export const DRIFT_AMPLITUDE = 1.2;
export const SETTLE_ALPHA0 = 0.35;
export const SETTLE_DECAY_PER_FRAME = 0.94;
export const SETTLE_MAX_MS = 1000;
export const SETTLE_NODE_LIMIT = 150;
/** Above this many nodes, always-on labels stop being legible and the view
 * degrades to zoom-gated labels instead. Tuned well below `SETTLE_NODE_
 * LIMIT`: a node without a parsed author list falls back to its title
 * (Constellation.tsx's `nodeLabel`), which runs noticeably wider than an
 * "Author, Year" string  -  at 150 nodes a real harvested neighbourhood
 * (most of which lack authors) rendered as a solid wall of overlapping
 * title text, worse than the zoom-gated behaviour it replaced. 40 keeps
 * "always" for the genuinely small case (a new study and its first
 * citations) legible; anything larger falls back to the pre-existing,
 * already-legible hub-first zoom-gated reveal. */
export const LABEL_ALWAYS_NODE_LIMIT = 40;

export type LabelMode = "always" | "dense";

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Node size by degree, not raw citation count: hubs read as obviously
 * bigger, leaves stay dust-small, and a paper's centrality *to this study's
 * graph* is what's shown  -  not how well-cited it happens to be generally. */
export function nodeRadius(
  degree: number,
  citationCount: number | null = null,
  maxCitationCount = 0,
): number {
  const degreeRadius = NODE_RADIUS_MIN + 3.8 * Math.sqrt(Math.max(0, degree));
  const citationShare =
    citationCount != null && maxCitationCount > 0
      ? Math.sqrt(
          Math.log1p(Math.max(0, citationCount)) /
            Math.log1p(Math.max(1, maxCitationCount)),
        )
      : 0;
  return clamp(degreeRadius + citationShare * 11, NODE_RADIUS_MIN, NODE_RADIUS_MAX);
}

/** Every node's neighbours, both directions  -  an edge kind doesn't matter
 * for adjacency, only for its rendered colour. */
export function buildAdjacency(
  edges: { src: string; dst: string }[],
): Map<string, Set<string>> {
  const adjacency = new Map<string, Set<string>>();
  const link = (a: string, b: string) => {
    if (!adjacency.has(a)) adjacency.set(a, new Set());
    adjacency.get(a)!.add(b);
  };
  for (const e of edges) {
    link(e.src, e.dst);
    link(e.dst, e.src);
  }
  return adjacency;
}

/** The focused/hovered node plus its immediate neighbours  -  what lights up.
 * Empty when nothing is focused (the baseline, everything at rest). */
export function activeNeighbourhood(
  focusRef: string | null,
  adjacency: Map<string, Set<string>>,
): Set<string> {
  if (!focusRef) return new Set();
  const active = new Set<string>([focusRef]);
  for (const n of adjacency.get(focusRef) ?? []) active.add(n);
  return active;
}

/** A node's opacity: full at rest, full if it's the focus or one of its
 * neighbours, dimmed otherwise (something else has the focus). */
export function nodeOpacity(ref: string, active: Set<string>): number {
  if (active.size === 0) return NEUTRAL_NODE_OPACITY;
  return active.has(ref) ? NEUTRAL_NODE_OPACITY : DIMMED_NODE_OPACITY;
}

/** An edge's state: `neutral` at rest, `incident` (touches the focused
 * node directly  -  reveal its real kind colour) or `dimmed` (anything else,
 * once something has focus) otherwise. Two neighbours of the focused node
 * that happen to cite each other are `dimmed`, not `incident`  -  "incident"
 * means touching the focus node itself, not merely inside its neighbourhood. */
export function edgeState(
  src: string,
  dst: string,
  focusRef: string | null,
): "neutral" | "incident" | "dimmed" {
  if (!focusRef) return "neutral";
  return src === focusRef || dst === focusRef ? "incident" : "dimmed";
}

export function edgeOpacity(state: "neutral" | "incident" | "dimmed"): number {
  return state === "neutral"
    ? NEUTRAL_EDGE_OPACITY
    : state === "incident"
      ? INCIDENT_EDGE_OPACITY
      : DIMMED_EDGE_OPACITY;
}

/** Whether a node's label shows: always for the selected node or the
 * current focus/neighbourhood (so a highlighted cluster reads by name), and
 * otherwise only once its rendered radius (`r * zoomK`) clears a threshold  -
 * zooming in is what reveals more names. This is the *dense* mode's contract;
 * below `LABEL_ALWAYS_NODE_LIMIT` nodes the view uses always-on labels
 * (`labelMode`), never this zoom gate. */
export function labelVisible(opts: {
  selected: boolean;
  inFocusNeighbourhood: boolean;
  radius: number;
  zoomK: number;
}): boolean {
  if (opts.selected || opts.inFocusNeighbourhood) return true;
  return opts.radius * opts.zoomK >= LABEL_ZOOM_THRESHOLD;
}

/** Which label treatment a graph of this size gets: always-on author+year
 * labels (reference-manager-grade by default) below the node-count limit,
 * zoom-gated labels above it where permanent labels would paint over each
 * other. Deliberately a single, honest threshold rather than a per-node guess. */
export function labelMode(nodeCount: number): LabelMode {
  return nodeCount <= LABEL_ALWAYS_NODE_LIMIT ? "always" : "dense";
}

/** A deterministic per-node phase from its ref, so the idle drift has no
 * randomness (replay-stable) and doesn't depend on array order. */
export function driftPhase(ref: string): number {
  let h = 0;
  for (let i = 0; i < ref.length; i++) h = (h * 31 + ref.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000 * Math.PI * 2;
}

/** Render-only per-node offset at time `t` (seconds)  -  never written back
 * to any position state, so it cannot accumulate or diverge; a caller adds
 * this to a node's settled (x, y) purely for the current frame's paint. */
export function driftOffset(ref: string, t: number): { dx: number; dy: number } {
  const phase = driftPhase(ref);
  return {
    dx: Math.sin(t + phase) * DRIFT_AMPLITUDE,
    dy: Math.cos(t * 0.8 + phase) * DRIFT_AMPLITUDE,
  };
}

/** The settle animation's alpha schedule: given the previous frame's alpha,
 * the next one  -  decays geometrically until it's negligible. Pure so the
 * schedule (and therefore roughly how many frames it takes) is assertable
 * without a rAF loop. */
export function nextSettleAlpha(alpha: number): number {
  return alpha * SETTLE_DECAY_PER_FRAME;
}

/** Whether the bounded rAF settle should run at all for this graph size  -
 * skipped above the node limit (each frame is an O(n²) relaxStep) so a large
 * harvested neighbourhood never costs a dropped-frame animation for a
 * refinement that was already good enough after `layoutGraph`'s own solve. */
export function shouldSettle(nodeCount: number): boolean {
  return nodeCount > 0 && nodeCount <= SETTLE_NODE_LIMIT;
}

/* ---- Lenses -----------------------------------------------------------
 *
 * A citation graph answers three different questions at once, and drawn all
 * together it answers none of them clearly: what this study's papers cite,
 * what cites them, and what merely resembles them are three separate reading
 * tasks sharing one canvas. The lens is which of those three is on screen.
 *
 * The vocabulary is the researcher's, not the API's: `references` is *earlier
 * work* (the study's papers point back at it), `citations` is *later work*
 * (it points forward at the study's papers), `recommendations` is *similar
 * work* (no direction, just resemblance). "All" stays the default, because a
 * researcher opening the tab has not yet asked one of the three questions. */

export type Lens = "all" | "references" | "citations" | "recommendations";

export const LENSES: { id: Lens; label: string; hint: string }[] = [
  {
    id: "all",
    label: "All",
    hint: "Every relation at once: earlier, later, and similar work",
  },
  {
    id: "references",
    label: "Earlier work",
    hint: "Papers your library cites  -  where this study's thinking comes from",
  },
  {
    id: "citations",
    label: "Later work",
    hint: "Papers citing your library  -  what happened after",
  },
  {
    id: "recommendations",
    label: "Similar work",
    hint: "Papers that resemble your library without citing it either way",
  },
];

/** A readable map is a curated view of the graph, not a dump of every API
 * neighbour. Keep the data in storage, but give the canvas a bounded number of
 * high-signal suggestions around the papers the researcher actually ingested. */
export const MAX_SUGGESTED_NODES = 48;
export const MAX_SUGGESTIONS_PER_ANCHOR = 12;
export const MAX_SUGGESTIONS_PER_RELATION = 6;

const RELATION_ORDER = ["references", "citations", "recommendations"] as const;

type CuratableNode = {
  paperRef: string;
  ingested: boolean;
  citationCount?: number | null;
};

type CuratableEdge = {
  src: string;
  dst: string;
  kind: string;
};

/** Keep ingested papers and direct study-to-study links, then select a small,
 * balanced neighbourhood around each ingested paper. Suggestions are ranked
 * by citation weight, de-duplicated when several relations point to the same
 * paper, and capped globally so four ingested papers cannot paint hundreds of
 * circles over the anchors. */
export function curateGraph<
  N extends CuratableNode,
  E extends CuratableEdge,
  G extends { nodes: N[]; edges: E[] },
>(graph: G): G {
  const ingested = graph.nodes.filter((node) => node.ingested);
  const ingestedRefs = new Set(ingested.map((node) => node.paperRef));
  const nodesByRef = new Map(graph.nodes.map((node) => [node.paperRef, node]));
  const supportedEdges = graph.edges.filter((edge) =>
    RELATION_ORDER.includes(edge.kind as (typeof RELATION_ORDER)[number]),
  );
  const directEdges = supportedEdges.filter(
    (edge) => ingestedRefs.has(edge.src) && ingestedRefs.has(edge.dst),
  );

  type Candidate = { edge: E; anchor: string; suggestion: string };
  const relationRank = new Map<string, number>(
    RELATION_ORDER.map((kind, index) => [kind, RELATION_ORDER.length - index]),
  );
  const candidatesByPair = new Map<string, Candidate>();
  for (const edge of supportedEdges) {
    const srcIsAnchor = ingestedRefs.has(edge.src);
    const dstIsAnchor = ingestedRefs.has(edge.dst);
    if (srcIsAnchor === dstIsAnchor) continue;
    const anchor = srcIsAnchor ? edge.src : edge.dst;
    const suggestion = srcIsAnchor ? edge.dst : edge.src;
    if (ingestedRefs.has(suggestion)) continue;
    const key = `${anchor}\u0000${suggestion}`;
    const current = candidatesByPair.get(key);
    const nextScore = [
      nodesByRef.get(suggestion)?.citationCount ?? 0,
      relationRank.get(edge.kind) ?? 0,
    ];
    const currentScore = current
      ? [
          nodesByRef.get(current.suggestion)?.citationCount ?? 0,
          relationRank.get(current.edge.kind) ?? 0,
        ]
      : null;
    if (
      current === undefined ||
      nextScore[0] > currentScore![0] ||
      (nextScore[0] === currentScore![0] && nextScore[1] > currentScore![1])
    ) {
      candidatesByPair.set(key, { edge, anchor, suggestion });
    }
  }

  const selectedByAnchor = new Map<string, Candidate[]>();
  for (const anchor of ingested.map((node) => node.paperRef)) {
    const candidates = [...candidatesByPair.values()]
      .filter((candidate) => candidate.anchor === anchor)
      .sort((a, b) => {
        const citationDelta =
          (nodesByRef.get(b.suggestion)?.citationCount ?? 0) -
          (nodesByRef.get(a.suggestion)?.citationCount ?? 0);
        if (citationDelta !== 0) return citationDelta;
        const relationDelta =
          (relationRank.get(b.edge.kind) ?? 0) -
          (relationRank.get(a.edge.kind) ?? 0);
        return relationDelta || a.suggestion.localeCompare(b.suggestion);
      });
    const buckets = new Map<string, Candidate[]>();
    for (const kind of RELATION_ORDER) {
      buckets.set(
        kind,
        candidates.filter((candidate) => candidate.edge.kind === kind),
      );
    }
    const chosen: Candidate[] = [];
    for (let round = 0; chosen.length < MAX_SUGGESTIONS_PER_ANCHOR; round += 1) {
      let progressed = false;
      for (const kind of RELATION_ORDER) {
        const bucket = buckets.get(kind)!;
        const candidate = bucket[round];
        if (candidate && round < MAX_SUGGESTIONS_PER_RELATION) {
          chosen.push(candidate);
          progressed = true;
        }
        if (chosen.length >= MAX_SUGGESTIONS_PER_ANCHOR) break;
      }
      if (!progressed) break;
    }
    selectedByAnchor.set(anchor, chosen);
  }

  const selected: Candidate[] = [];
  const selectedSuggestions = new Set<string>();
  const maxRounds = Math.max(...[...selectedByAnchor.values()].map((items) => items.length), 0);
  for (let round = 0; round < maxRounds && selected.length < MAX_SUGGESTED_NODES; round += 1) {
    for (const anchor of ingested.map((node) => node.paperRef)) {
      const candidate = selectedByAnchor.get(anchor)?.[round];
      if (!candidate) continue;
      if (
        selectedSuggestions.size >= MAX_SUGGESTED_NODES &&
        !selectedSuggestions.has(candidate.suggestion)
      ) {
        continue;
      }
      selected.push(candidate);
      selectedSuggestions.add(candidate.suggestion);
      if (selected.length >= MAX_SUGGESTED_NODES) break;
    }
  }

  const edges = [
    ...directEdges,
    ...selected.map((candidate) => candidate.edge),
  ];
  const retainedRefs = new Set(ingested.map((node) => node.paperRef));
  for (const edge of edges) {
    retainedRefs.add(edge.src);
    retainedRefs.add(edge.dst);
  }
  return {
    ...graph,
    nodes: graph.nodes.filter((node) => retainedRefs.has(node.paperRef)),
    edges,
  };
}

/** The edges a lens keeps. `all` is the identity, deliberately returning the
 * same array so the common case allocates nothing. */
export function lensEdges<E extends { kind: string }>(edges: E[], lens: Lens): E[] {
  return lens === "all" ? edges : edges.filter((e) => e.kind === lens);
}

/**
 * The nodes a lens keeps.
 *
 * Every ingested paper survives every lens, even when the lens leaves it with
 * no edges at all: those are the study's own library  -  its anchors  -  and a
 * lens that made a researcher's own papers vanish would read as data loss
 * rather than as a filter. Suggestions are the opposite: one exists only as
 * the far end of a harvested relation, so it survives only while the relation
 * that introduced it does.
 */
export function lensNodes<N extends { paperRef: string; ingested: boolean }>(
  nodes: N[],
  edges: { src: string; dst: string; kind: string }[],
  lens: Lens,
): N[] {
  if (lens === "all") return nodes;
  const reachable = new Set<string>();
  for (const e of lensEdges(edges, lens)) {
    reachable.add(e.src);
    reachable.add(e.dst);
  }
  return nodes.filter((n) => n.ingested || reachable.has(n.paperRef));
}

/**
 * How many *suggested* papers each lens has to offer, for the control's own
 * badges. Counting suggestions rather than nodes is the point: the number a
 * researcher is choosing between is how much undiscovered work sits behind
 * each question, and the papers already in the study are not that.
 */
export function lensCounts(
  nodes: { paperRef: string; ingested: boolean }[],
  edges: { src: string; dst: string; kind: string }[],
): Record<Lens, number> {
  const counts = {} as Record<Lens, number>;
  for (const { id } of LENSES) {
    counts[id] = lensNodes(nodes, edges, id).filter((n) => !n.ingested).length;
  }
  return counts;
}
