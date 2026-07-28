/* Deterministic force layout for the citation constellation (FR-LIT-2).
 *
 * Hand-rolled rather than pulling in d3-force / react-force-graph: the graph is
 * small (a study cites dozens of papers), and the charting discipline is to
 * build the marks ourselves (D17). A fixed number of iterations with seeded
 * start positions makes the layout deterministic — the same graph always
 * renders the same way, and it is unit-testable with no DOM. */

export interface GraphNodeIn {
  paperRef: string;
  title: string;
  authors?: string[];
  year: number | null;
  citationCount: number | null;
  ingested: boolean;
}

export interface GraphEdgeIn {
  src: string;
  dst: string;
  kind: string;
}

export interface PositionedNode extends GraphNodeIn {
  x: number;
  y: number;
}

export interface LayoutOptions {
  width?: number;
  height?: number;
  iterations?: number;
  /** Charge (node repulsion) and spring (edge attraction) strengths. */
  charge?: number;
  spring?: number;
}

/** Position every node in `[0,width] × [0,height]`. Ingested nodes anchor the
 * layout (they seed near the centre); suggestions drift to the periphery. */
export function layoutGraph(
  nodes: GraphNodeIn[],
  edges: GraphEdgeIn[],
  opts: LayoutOptions = {},
): PositionedNode[] {
  const width = opts.width ?? 640;
  const height = opts.height ?? 440;
  // Each iteration is O(n²); harvested neighbourhoods reach hundreds of nodes,
  // so scale iterations down as n grows to keep a relayout under a frame budget
  // (still deterministic — n is data).
  const iterations =
    opts.iterations ??
    (nodes.length > 200 ? 80 : nodes.length > 100 ? 150 : 300);
  const charge = opts.charge ?? 2200;
  const spring = opts.spring ?? 0.02;
  const cx = width / 2;
  const cy = height / 2;

  if (nodes.length === 0) return [];

  // Seeded start positions on a circle — deterministic, no randomness.
  const pos = nodes.map((n, i) => {
    const angle = (i / nodes.length) * Math.PI * 2;
    const radius = n.ingested ? width * 0.16 : width * 0.34;
    return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
  });

  const index = new Map(nodes.map((n, i) => [n.paperRef, i]));
  const links = edges
    .map((e) => [index.get(e.src), index.get(e.dst)] as [number?, number?])
    .filter((l): l is [number, number] => l[0] !== undefined && l[1] !== undefined);

  for (let step = 0; step < iterations; step++) {
    const fx = new Array(nodes.length).fill(0);
    const fy = new Array(nodes.length).fill(0);

    // Repulsion between every pair (Coulomb-like).
    for (let a = 0; a < nodes.length; a++) {
      for (let b = a + 1; b < nodes.length; b++) {
        let dx = pos[a].x - pos[b].x;
        let dy = pos[a].y - pos[b].y;
        let d2 = dx * dx + dy * dy || 0.01;
        // Deterministic nudge for exactly-coincident points.
        if (d2 < 0.02) {
          dx = (a - b) * 0.1;
          dy = 0.1;
          d2 = dx * dx + dy * dy;
        }
        const f = charge / d2;
        const d = Math.sqrt(d2);
        fx[a] += (dx / d) * f;
        fy[a] += (dy / d) * f;
        fx[b] -= (dx / d) * f;
        fy[b] -= (dy / d) * f;
      }
    }

    // Spring attraction along edges.
    for (const [a, b] of links) {
      const dx = pos[b].x - pos[a].x;
      const dy = pos[b].y - pos[a].y;
      fx[a] += dx * spring;
      fy[a] += dy * spring;
      fx[b] -= dx * spring;
      fy[b] -= dy * spring;
    }

    // Gentle pull to centre so disconnected nodes don't drift off-canvas;
    // ingested nodes are pulled harder so they stay central.
    for (let i = 0; i < nodes.length; i++) {
      const pull = nodes[i].ingested ? 0.012 : 0.006;
      fx[i] += (cx - pos[i].x) * pull;
      fy[i] += (cy - pos[i].y) * pull;
    }

    const cool = 0.85 * (1 - step / iterations) + 0.05;
    for (let i = 0; i < nodes.length; i++) {
      pos[i].x = clamp(pos[i].x + fx[i] * cool * 0.02, 12, width - 12);
      pos[i].y = clamp(pos[i].y + fy[i] * cool * 0.02, 12, height - 12);
    }
  }

  return nodes.map((n, i) => ({ ...n, x: pos[i].x, y: pos[i].y }));
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** How many edges touch each node (in + out). Additive — the Obsidian-style
 * constellation sizes a node by degree (`3.5 + 2.6*sqrt(deg)`: hubs obvious,
 * leaves dust) rather than by raw citation count, which conflates "central
 * to this study" with "generally well-cited". Computed straight from the
 * same edges `layoutGraph` already takes; has no effect on the layout. */
export function degreeMap(
  nodes: GraphNodeIn[],
  edges: GraphEdgeIn[],
): Map<string, number> {
  const degree = new Map(nodes.map((n) => [n.paperRef, 0]));
  for (const e of edges) {
    if (degree.has(e.src)) degree.set(e.src, degree.get(e.src)! + 1);
    if (degree.has(e.dst)) degree.set(e.dst, degree.get(e.dst)! + 1);
  }
  return degree;
}

export interface RelaxOptions {
  width?: number;
  height?: number;
  charge?: number;
  spring?: number;
}

/** One frame of a *live* settle animation, separate from `layoutGraph`'s own
 * fixed-iteration solve — which stays untouched by this addition, so its
 * golden-snapshot output (`verify-library.mjs`) can never drift underneath
 * it. Same physics shape as one pass of that loop (repulsion + spring +
 * centre-pull), but driven by a decaying `alpha` rather than a fixed
 * iteration count, since a `requestAnimationFrame` loop doesn't know in
 * advance how many frames it will get: the caller seeds `nodes` from
 * `layoutGraph`'s own output, then calls this once per frame with `alpha`
 * multiplied by ~0.94 each time, stopping once the motion is imperceptible. */
export function relaxStep(
  nodes: PositionedNode[],
  edges: GraphEdgeIn[],
  alpha: number,
  opts: RelaxOptions = {},
): PositionedNode[] {
  const width = opts.width ?? 640;
  const height = opts.height ?? 440;
  const charge = opts.charge ?? 2200;
  const spring = opts.spring ?? 0.02;
  const cx = width / 2;
  const cy = height / 2;

  if (nodes.length === 0) return [];

  const index = new Map(nodes.map((n, i) => [n.paperRef, i]));
  const links = edges
    .map((e) => [index.get(e.src), index.get(e.dst)] as [number?, number?])
    .filter((l): l is [number, number] => l[0] !== undefined && l[1] !== undefined);

  const fx = new Array(nodes.length).fill(0);
  const fy = new Array(nodes.length).fill(0);

  for (let a = 0; a < nodes.length; a++) {
    for (let b = a + 1; b < nodes.length; b++) {
      let dx = nodes[a].x - nodes[b].x;
      let dy = nodes[a].y - nodes[b].y;
      let d2 = dx * dx + dy * dy || 0.01;
      if (d2 < 0.02) {
        dx = (a - b) * 0.1;
        dy = 0.1;
        d2 = dx * dx + dy * dy;
      }
      const f = charge / d2;
      const d = Math.sqrt(d2);
      fx[a] += (dx / d) * f;
      fy[a] += (dy / d) * f;
      fx[b] -= (dx / d) * f;
      fy[b] -= (dy / d) * f;
    }
  }

  for (const [a, b] of links) {
    const dx = nodes[b].x - nodes[a].x;
    const dy = nodes[b].y - nodes[a].y;
    fx[a] += dx * spring;
    fy[a] += dy * spring;
    fx[b] -= dx * spring;
    fy[b] -= dy * spring;
  }

  for (let i = 0; i < nodes.length; i++) {
    const pull = nodes[i].ingested ? 0.012 : 0.006;
    fx[i] += (cx - nodes[i].x) * pull;
    fy[i] += (cy - nodes[i].y) * pull;
  }

  return nodes.map((n, i) => ({
    ...n,
    x: clamp(n.x + fx[i] * alpha * 0.02, 12, width - 12),
    y: clamp(n.y + fy[i] * alpha * 0.02, 12, height - 12),
  }));
}

/** The paper-ref → {arxivId|doi} an "add to study" click ingests with. */
export function ingestIdForRef(
  ref: string,
): { arxivId?: string; doi?: string } | null {
  if (ref.startsWith("arxiv:")) return { arxivId: ref.slice("arxiv:".length) };
  if (ref.startsWith("doi:")) return { doi: ref.slice("doi:".length) };
  return null;
}
