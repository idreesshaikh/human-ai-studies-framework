/* Deterministic force layout with study papers anchored across the canvas. */

interface GraphNodeIn {
  paperRef: string;
  title: string;
  authors?: string[];
  year: number | null;
  citationCount: number | null;
  ingested: boolean;
}

interface GraphEdgeIn {
  src: string;
  dst: string;
  kind: string;
}

export interface PositionedNode extends GraphNodeIn {
  x: number;
  y: number;
}

interface LayoutOptions {
  width?: number;
  height?: number;
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
  // Pairwise repulsion is O(n²); reduce iterations for large neighbourhoods.
  const iterations = nodes.length > 200 ? 80 : nodes.length > 100 ? 150 : 300;
  const charge = 4200;
  const spring = 0.012;
  const cx = width / 2;
  const cy = height / 2;

  if (nodes.length === 0) return [];

  // Phyllotaxis spreads anchors and suggestions through separate ellipses.
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const ingestedCount = nodes.filter((n) => n.ingested).length;
  const ingestedSeen = new Map<string, number>();
  const suggestedSeen = new Map<string, number>();
  const pos = nodes.map((n) => {
    const seen = n.ingested ? ingestedSeen : suggestedSeen;
    const index = seen.get(n.paperRef) ?? 0;
    seen.set(n.paperRef, index + 1);
    const count = n.ingested ? Math.max(ingestedCount, 1) : Math.max(nodes.length - ingestedCount, 1);
    const angle = index * goldenAngle + (n.ingested ? 0 : Math.PI / 5);
    const radius = Math.sqrt((index + 0.6) / count);
    const rx = n.ingested ? width * 0.38 : width * 0.46;
    const ry = n.ingested ? height * 0.34 : height * 0.44;
    return { x: cx + Math.cos(angle) * radius * rx, y: cy + Math.sin(angle) * radius * ry };
  });
  const anchors = pos.map((p) => ({ ...p }));

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
      const pull = nodes[i].ingested ? 0.004 : 0.002;
      fx[i] += (cx - pos[i].x) * pull;
      fy[i] += (cy - pos[i].y) * pull;
      // Anchors prevent edge springs from collapsing the initial arrangement.
      fx[i] += (anchors[i].x - pos[i].x) * 0.018;
      fy[i] += (anchors[i].y - pos[i].y) * 0.018;
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

/** Count incoming and outgoing edges for each node. */
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
