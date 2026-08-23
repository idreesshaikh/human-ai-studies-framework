/* Deterministic force layout for the citation constellation (FR-LIT-2).
 *
 * Hand-rolled rather than pulling in d3-force / react-force-graph: the graph is
 * small (a study cites dozens of papers), and the charting discipline is to
 * build the marks ourselves (D17). A fixed number of iterations with seeded
 * start positions makes the layout deterministic  -  the same graph always
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
  /** Spread nodes through the available canvas instead of a centre ring. */
  spread?: boolean;
  /** Keep the physics, but reserve the x-axis for publication year and the
   * y-axis for citation weight so a researcher can read time and influence
   * without needing to decode a cloud of dots. */
  timeline?: boolean;
}

/** Position every node in `[0,width] × [0,height]`. Ingested nodes anchor the
 * layout (they seed near the centre); suggestions drift to the periphery. */
export function layoutGraph(
  nodes: GraphNodeIn[],
  edges: GraphEdgeIn[],
  opts: LayoutOptions = {},
): PositionedNode[] {
  if (opts.timeline) return layoutTimelineGraph(nodes, edges, opts);
  const width = opts.width ?? 640;
  const height = opts.height ?? 440;
  // Each iteration is O(n²); harvested neighbourhoods reach hundreds of nodes,
  // so scale iterations down as n grows to keep a relayout under a frame budget
  // (still deterministic  -  n is data).
  const spread = opts.spread ?? false;
  const iterations =
    opts.iterations ??
    (nodes.length > 200 ? 80 : nodes.length > 100 ? 150 : 300);
  // Exploration needs more air than the compact fixture layout. Keep the
  // edges readable without allowing a harvested neighbourhood to collapse
  // into one centre knot.
  const charge = opts.charge ?? (spread ? 4200 : 2200);
  const spring = opts.spring ?? (spread ? 0.012 : 0.02);
  const cx = width / 2;
  const cy = height / 2;

  if (nodes.length === 0) return [];

  // Seeded start positions are deterministic, with two deliberately different
  // modes. The compact ring remains the stable primitive-layout default used
  // by the pure fixture; the rendered constellation opts into a phyllotaxis
  // seed so a real graph starts across the canvas rather than in a central
  // knot. The inner/outer ellipses preserve the useful visual distinction
  // between papers in the study and suggested neighbours without wasting the
  // pane's width.
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const ingestedCount = nodes.filter((n) => n.ingested).length;
  const ingestedSeen = new Map<string, number>();
  const suggestedSeen = new Map<string, number>();
  const pos = nodes.map((n, i) => {
    if (!spread) {
      const angle = (i / nodes.length) * Math.PI * 2;
      const radius = n.ingested ? width * 0.16 : width * 0.34;
      return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
    }
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
      const pull = spread ? (nodes[i].ingested ? 0.004 : 0.002) : nodes[i].ingested ? 0.012 : 0.006;
      fx[i] += (cx - pos[i].x) * pull;
      fy[i] += (cy - pos[i].y) * pull;
      if (spread) {
        // Keep the semantic seed visible. Without an anchor, edge springs
        // turn a well-spread constellation into a compact citation knot.
        fx[i] += (anchors[i].x - pos[i].x) * 0.018;
        fy[i] += (anchors[i].y - pos[i].y) * 0.018;
      }
    }

    const cool = 0.85 * (1 - step / iterations) + 0.05;
    for (let i = 0; i < nodes.length; i++) {
      pos[i].x = clamp(pos[i].x + fx[i] * cool * 0.02, 12, width - 12);
      pos[i].y = clamp(pos[i].y + fy[i] * cool * 0.02, 12, height - 12);
    }
  }

  return nodes.map((n, i) => ({ ...n, x: pos[i].x, y: pos[i].y }));
}

/**
 * A soft semantic layer over the same deterministic physics used by the classic
 * constellation. Publication year remains a quiet reading cue from left to
 * right, but it does not pin every paper to a date column. The graph's
 * relationships and the anchors' breathing room stay more important than a
 * perfectly straight timeline, especially for fresh papers with sparse metadata.
 *
 * Missing years stay in a small discovery lane at the right edge. They are
 * visibly unknown rather than being assigned a fake year, which matters in a
 * literature map where “new” and “not dated” are different claims.
 */
function layoutTimelineGraph(
  nodes: GraphNodeIn[],
  edges: GraphEdgeIn[],
  opts: LayoutOptions,
): PositionedNode[] {
  const width = opts.width ?? 640;
  const height = opts.height ?? 440;
  const base = layoutGraph(nodes, edges, {
    ...opts,
    timeline: false,
    spread: true,
  });
  const years = nodes.flatMap((n) => (n.year == null ? [] : [n.year]));
  if (years.length === 0) return base;

  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);
  const yearSpan = Math.max(maxYear - minYear, 1);
  const byYear = new Map<number, number[]>();
  nodes.forEach((n, i) => {
    if (n.year == null) return;
    const group = byYear.get(n.year) ?? [];
    group.push(i);
    byYear.set(n.year, group);
  });
  const cited = nodes.map((n) => Math.log1p(Math.max(0, n.citationCount ?? 0)));
  const maxCited = Math.max(...cited, 1);
  const left = 76;
  const right = width - 76;
  const top = 52;
  const bottom = height - 58;
  const mix = (semantic: number, physics: number, semanticWeight: number) =>
    semantic * semanticWeight + physics * (1 - semanticWeight);

  const semantic = base.map((n, i) => {
    const sameYear = n.year == null ? [] : byYear.get(n.year) ?? [];
    const yearIndex = sameYear.indexOf(i);
    /* Keep the year axis honest while giving same-year papers a small orbit.
     * Without this, a harvested batch from one publication year forms a
     * vertical stack and its labels collapse into one another. */
    const sameYearOffset =
      sameYear.length > 1
        ? (yearIndex - (sameYear.length - 1) / 2) * Math.min(52, (right - left) / (sameYear.length + 1))
        : 0;
    const yearX =
      n.year == null
        ? right
        : left + ((n.year - minYear) / yearSpan) * (right - left) + sameYearOffset;
    const citationY =
      bottom - (cited[i] / maxCited) * (bottom - top);
    return {
      ...n,
      x: mix(yearX, n.x, 0.58),
      y: mix(citationY, n.y, 0.38),
    };
  });

  // The semantic projection is intentionally strong, but it can put a large
  // ingested hub and many same-year suggestions on the same coordinate. A
  // normal force solve would separate them, yet it would also erase the year
  // axis. Resolve only the visual collisions here: suggestions yield first,
  // ingested papers stay close to their semantic anchors, and a light return
  // pull keeps the publication scale readable.
  return separateTimelineNodes(nodes, edges, semantic, width, height);
}

function separateTimelineNodes(
  nodes: GraphNodeIn[],
  edges: GraphEdgeIn[],
  points: PositionedNode[],
  width: number,
  height: number,
): PositionedNode[] {
  const degree = new Map(nodes.map((n) => [n.paperRef, 0]));
  for (const edge of edges) {
    if (degree.has(edge.src)) degree.set(edge.src, degree.get(edge.src)! + 1);
    if (degree.has(edge.dst)) degree.set(edge.dst, degree.get(edge.dst)! + 1);
  }
  const citationValues = nodes.map((n) => Math.log1p(Math.max(0, n.citationCount ?? 0)));
  const maxCitation = Math.max(...citationValues, 1);
  const radius = nodes.map((n, i) => {
    const degreeRadius = 9 + 3.8 * Math.sqrt(degree.get(n.paperRef) ?? 0);
    const citationShare = Math.sqrt(citationValues[i] / maxCitation);
    return Math.min(34, degreeRadius + citationShare * 11);
  });
  const target = points.map((p) => ({ x: p.x, y: p.y }));
  const out = points.map((p) => ({ ...p }));
  const iterations = nodes.length > 180 ? 48 : 90;

  const pushApart = () => {
    for (let a = 0; a < out.length; a++) {
      for (let b = a + 1; b < out.length; b++) {
        let dx = out[a].x - out[b].x;
        let dy = out[a].y - out[b].y;
        let distance = Math.hypot(dx, dy);
        if (distance < 0.01) {
          dx = (a - b) * 0.17;
          dy = 0.23;
          distance = Math.hypot(dx, dy);
        }
        const minimum = radius[a] + radius[b] + 7;
        if (distance >= minimum) continue;

        const amount = (minimum - distance) / distance;
        const ux = dx * amount;
        const uy = dy * amount;
        // A study paper is an anchor. Let its suggested neighbours move away
        // from it, instead of letting a crowded harvest drag the anchor into
        // an unreadable knot.
        const aWeight = nodes[a].ingested ? 0.14 : 1;
        const bWeight = nodes[b].ingested ? 0.14 : 1;
        const total = aWeight + bWeight;
        out[a].x += ux * (aWeight / total);
        out[a].y += uy * (aWeight / total);
        out[b].x -= ux * (bWeight / total);
        out[b].y -= uy * (bWeight / total);
      }
    }
  };

  for (let step = 0; step < iterations; step++) {
    pushApart();
    for (let i = 0; i < out.length; i++) {
      const pull = nodes[i].ingested ? 0.035 : 0.012;
      out[i].x += (target[i].x - out[i].x) * pull;
      out[i].y += (target[i].y - out[i].y) * pull;
      const margin = radius[i] + 10;
      out[i].x = clamp(out[i].x, margin, width - margin);
      out[i].y = clamp(out[i].y, margin, height - margin);
    }
  }
  // A short collision-only tail prevents the semantic return pull from
  // reintroducing a final one-pixel overlap after the main solve.
  for (let pass = 0; pass < 4; pass++) pushApart();

  return out.map((p) => ({ ...p, x: clamp(p.x, 0, width), y: clamp(p.y, 0, height) }));
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** How many edges touch each node (in + out). Additive  -  the Obsidian-style
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
  spread?: boolean;
}

/** One frame of a *live* settle animation, separate from `layoutGraph`'s own
 * fixed-iteration solve  -  which stays untouched by this addition, so its
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
  const spread = opts.spread ?? false;
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
    const pull = spread ? (nodes[i].ingested ? 0.004 : 0.002) : nodes[i].ingested ? 0.012 : 0.006;
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
