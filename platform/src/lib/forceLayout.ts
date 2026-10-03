

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

  charge?: number;
  spring?: number;

  spread?: boolean;

  timeline?: boolean;
}

export function layoutGraph(
  nodes: GraphNodeIn[],
  edges: GraphEdgeIn[],
  opts: LayoutOptions = {},
): PositionedNode[] {
  if (opts.timeline) return layoutTimelineGraph(nodes, edges, opts);
  const width = opts.width ?? 640;
  const height = opts.height ?? 440;

  const spread = opts.spread ?? false;
  const iterations =
    opts.iterations ??
    (nodes.length > 200 ? 80 : nodes.length > 100 ? 150 : 300);

  const charge = opts.charge ?? (spread ? 4200 : 2200);
  const spring = opts.spring ?? (spread ? 0.012 : 0.02);
  const cx = width / 2;
  const cy = height / 2;

  if (nodes.length === 0) return [];

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

    for (let a = 0; a < nodes.length; a++) {
      for (let b = a + 1; b < nodes.length; b++) {
        let dx = pos[a].x - pos[b].x;
        let dy = pos[a].y - pos[b].y;
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
      const dx = pos[b].x - pos[a].x;
      const dy = pos[b].y - pos[a].y;
      fx[a] += dx * spring;
      fy[a] += dy * spring;
      fx[b] -= dx * spring;
      fy[b] -= dy * spring;
    }

    for (let i = 0; i < nodes.length; i++) {
      const pull = spread ? (nodes[i].ingested ? 0.004 : 0.002) : nodes[i].ingested ? 0.012 : 0.006;
      fx[i] += (cx - pos[i].x) * pull;
      fy[i] += (cy - pos[i].y) * pull;
      if (spread) {

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

  for (let pass = 0; pass < 4; pass++) pushApart();

  return out.map((p) => ({ ...p, x: clamp(p.x, 0, width), y: clamp(p.y, 0, height) }));
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

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

export function ingestIdForRef(
  ref: string,
): { arxivId?: string; doi?: string } | null {
  if (ref.startsWith("arxiv:")) return { arxivId: ref.slice("arxiv:".length) };
  if (ref.startsWith("doi:")) return { doi: ref.slice("doi:".length) };
  return null;
}
