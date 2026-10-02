

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

export const LABEL_ALWAYS_NODE_LIMIT = 40;

export type LabelMode = "always" | "dense";

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

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

export function activeNeighbourhood(
  focusRef: string | null,
  adjacency: Map<string, Set<string>>,
): Set<string> {
  if (!focusRef) return new Set();
  const active = new Set<string>([focusRef]);
  for (const n of adjacency.get(focusRef) ?? []) active.add(n);
  return active;
}

export function nodeOpacity(ref: string, active: Set<string>): number {
  if (active.size === 0) return NEUTRAL_NODE_OPACITY;
  return active.has(ref) ? NEUTRAL_NODE_OPACITY : DIMMED_NODE_OPACITY;
}

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

export function labelVisible(opts: {
  selected: boolean;
  inFocusNeighbourhood: boolean;
  radius: number;
  zoomK: number;
}): boolean {
  if (opts.selected || opts.inFocusNeighbourhood) return true;
  return opts.radius * opts.zoomK >= LABEL_ZOOM_THRESHOLD;
}

export function labelMode(nodeCount: number): LabelMode {
  return nodeCount <= LABEL_ALWAYS_NODE_LIMIT ? "always" : "dense";
}

export function driftPhase(ref: string): number {
  let h = 0;
  for (let i = 0; i < ref.length; i++) h = (h * 31 + ref.charCodeAt(i)) >>> 0;
  return (h % 1000) / 1000 * Math.PI * 2;
}

export function driftOffset(ref: string, t: number): { dx: number; dy: number } {
  const phase = driftPhase(ref);
  return {
    dx: Math.sin(t + phase) * DRIFT_AMPLITUDE,
    dy: Math.cos(t * 0.8 + phase) * DRIFT_AMPLITUDE,
  };
}

export function nextSettleAlpha(alpha: number): number {
  return alpha * SETTLE_DECAY_PER_FRAME;
}

export function shouldSettle(nodeCount: number): boolean {
  return nodeCount > 0 && nodeCount <= SETTLE_NODE_LIMIT;
}

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

export const MAX_SUGGESTED_NODES = 120;
export const MAX_SUGGESTIONS_PER_ANCHOR = 30;
export const MAX_SUGGESTIONS_PER_RELATION = 12;

const RELATION_ORDER = ["references", "citations", "recommendations"] as const;
const CORPUS_DISCOVERY_KIND = "harvested-via";

type CuratableNode = {
  paperRef: string;
  ingested: boolean;
  title?: string;
  abstract?: string;
  citationCount?: number | null;
  year?: number | null;
};

type CuratableEdge = {
  src: string;
  dst: string;
  kind: string;
};

export function curateGraph<
  N extends CuratableNode,
  E extends CuratableEdge,
  G extends { nodes: N[]; edges: E[] },
>(graph: G): G {
  const ingested = graph.nodes.filter((node) => node.ingested);
  const ingestedRefs = new Set(ingested.map((node) => node.paperRef));
  const nodesByRef = new Map(graph.nodes.map((node) => [node.paperRef, node]));
  const years = graph.nodes.flatMap((node) =>
    node.year == null ? [] : [node.year],
  );
  const minYear = years.length ? Math.min(...years) : 0;
  const maxYear = years.length ? Math.max(...years) : 0;
  const yearSpan = Math.max(maxYear - minYear, 1);
  const maxCitations = Math.max(
    ...graph.nodes.map((node) => node.citationCount ?? 0),
    1,
  );
  const topicStopwords = new Set([
    "all",
    "and",
    "about",
    "also",
    "are",
    "been",
    "but",
    "between",
    "can",
    "does",
    "from",
    "into",
    "is",
    "need",
    "not",
    "paper",
    "papers",
    "study",
    "that",
    "their",
    "these",
    "those",
    "through",
    "using",
    "with",
    "you",
  ]);
  const topicTokens = (node: CuratableNode): Set<string> =>
    new Set(
      `${node.title ?? ""} ${node.abstract ?? ""}`
        .toLowerCase()
        .match(/[a-z0-9][a-z0-9-]{2,}/g)
        ?.filter((term) => !topicStopwords.has(term)) ?? [],
    );
  const topicsByRef = new Map(
    graph.nodes.map((node) => [node.paperRef, topicTokens(node)]),
  );
  const supportedEdges = graph.edges.flatMap((edge) => {
    if (RELATION_ORDER.includes(edge.kind as (typeof RELATION_ORDER)[number])) {
      return [edge];
    }

    if (edge.kind === CORPUS_DISCOVERY_KIND) {
      return [{ ...edge, kind: "recommendations" } as E];
    }
    return [];
  });
  const directEdges = supportedEdges.filter(
    (edge) => ingestedRefs.has(edge.src) && ingestedRefs.has(edge.dst),
  );

  type Candidate = { edge: E; anchor: string; suggestion: string };
  const relationRank = new Map<string, number>(
    RELATION_ORDER.map((kind, index) => [kind, RELATION_ORDER.length - index]),
  );
  const topicRelevance = (candidate: Candidate): number => {
    const anchorTerms = topicsByRef.get(candidate.anchor) ?? new Set<string>();
    const suggestionTerms =
      topicsByRef.get(candidate.suggestion) ?? new Set<string>();
    if (anchorTerms.size === 0 || suggestionTerms.size === 0) return 0.25;
    let overlap = 0;
    for (const term of suggestionTerms) {
      if (anchorTerms.has(term)) overlap += 1;
    }

    return Math.min(1, overlap / Math.max(2, Math.min(anchorTerms.size, 8)));
  };
  const candidateScore = (candidate: Candidate) => {
    const node = nodesByRef.get(candidate.suggestion);
    const citations = Math.log1p(Math.max(0, node?.citationCount ?? 0));
    const citationSignal = citations / Math.log1p(maxCitations);
    const freshnessSignal =
      node?.year == null ? 0.35 : (node.year - minYear) / yearSpan;
    const relationSignal = (relationRank.get(candidate.edge.kind) ?? 0) / 3;
    return (
      topicRelevance(candidate) * 0.55 +
      citationSignal * 0.15 +
      freshnessSignal * 0.2 +
      relationSignal * 0.1
    );
  };
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
    const nextScore = candidateScore({ edge, anchor, suggestion });
    const currentScore = current ? candidateScore(current) : null;
    if (
      current === undefined ||
      nextScore > currentScore! ||
      (nextScore === currentScore! && suggestion.localeCompare(current.suggestion) < 0)
    ) {
      candidatesByPair.set(key, { edge, anchor, suggestion });
    }
  }

  const selectedByAnchor = new Map<string, Candidate[]>();
  for (const anchor of ingested.map((node) => node.paperRef)) {
      const candidates = [...candidatesByPair.values()]
        .filter((candidate) => candidate.anchor === anchor)
        .sort((a, b) => {
        const scoreDelta = candidateScore(b) - candidateScore(a);
        return scoreDelta || a.suggestion.localeCompare(b.suggestion);
      });

    const curatedCandidates = candidates;
    const buckets = new Map<string, Candidate[]>();
    for (const kind of RELATION_ORDER) {
      buckets.set(
        kind,
        curatedCandidates.filter((candidate) => candidate.edge.kind === kind),
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
      if (selectedSuggestions.has(candidate.suggestion)) continue;
      if (selectedSuggestions.size >= MAX_SUGGESTED_NODES) {
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

export function lensEdges<E extends { kind: string }>(edges: E[], lens: Lens): E[] {
  return lens === "all" ? edges : edges.filter((e) => e.kind === lens);
}

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
