/**
 * Deterministic force layout for the related-papers graph (FR-LIT-2).
 *
 * Hand-rolled rather than pulling in d3-force / react-force-graph: the graph
 * is small (a study cites dozens of papers), and the project's charting
 * discipline is to build the marks ourselves (decision D17). A fixed number
 * of iterations with seeded start positions makes the layout deterministic -
 * the same graph always renders the same way, and it is unit-testable
 * (D19) with no DOM.
 */

export interface GraphNodeIn {
  paperRef: string
  title: string
  year: number | null
  citationCount: number | null
  ingested: boolean
}

export interface GraphEdgeIn {
  src: string
  dst: string
  kind: string
}

export interface PositionedNode extends GraphNodeIn {
  x: number
  y: number
}

export interface LayoutOptions {
  width?: number
  height?: number
  iterations?: number
  /** Charge (node repulsion) and spring (edge attraction) strengths. */
  charge?: number
  spring?: number
}

/**
 * Position every node in `[0,width] x [0,height]`. Ingested nodes anchor the
 * layout (they seed near the centre); suggestions drift to the periphery.
 */
export function layoutGraph(
  nodes: GraphNodeIn[],
  edges: GraphEdgeIn[],
  opts: LayoutOptions = {},
): PositionedNode[] {
  const width = opts.width ?? 640
  const height = opts.height ?? 440
  const iterations = opts.iterations ?? 300
  const charge = opts.charge ?? 2200
  const spring = opts.spring ?? 0.02
  const cx = width / 2
  const cy = height / 2

  if (nodes.length === 0) return []

  // Seeded start positions on a circle — deterministic, no randomness.
  const pos = nodes.map((n, i) => {
    const angle = (i / nodes.length) * Math.PI * 2
    const radius = n.ingested ? width * 0.16 : width * 0.34
    return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius }
  })

  const index = new Map(nodes.map((n, i) => [n.paperRef, i]))
  const links = edges
    .map((e) => [index.get(e.src), index.get(e.dst)] as [number?, number?])
    .filter((l): l is [number, number] => l[0] !== undefined && l[1] !== undefined)

  for (let step = 0; step < iterations; step++) {
    const fx = new Array(nodes.length).fill(0)
    const fy = new Array(nodes.length).fill(0)

    // Repulsion between every pair (Coulomb-like).
    for (let a = 0; a < nodes.length; a++) {
      for (let b = a + 1; b < nodes.length; b++) {
        let dx = pos[a].x - pos[b].x
        let dy = pos[a].y - pos[b].y
        let d2 = dx * dx + dy * dy || 0.01
        // Deterministic nudge for exactly-coincident points.
        if (d2 < 0.02) {
          dx = (a - b) * 0.1
          dy = 0.1
          d2 = dx * dx + dy * dy
        }
        const f = charge / d2
        const d = Math.sqrt(d2)
        fx[a] += (dx / d) * f
        fy[a] += (dy / d) * f
        fx[b] -= (dx / d) * f
        fy[b] -= (dy / d) * f
      }
    }

    // Spring attraction along edges.
    for (const [a, b] of links) {
      const dx = pos[b].x - pos[a].x
      const dy = pos[b].y - pos[a].y
      fx[a] += dx * spring
      fy[a] += dy * spring
      fx[b] -= dx * spring
      fy[b] -= dy * spring
    }

    // Gentle pull to centre so disconnected nodes don't drift off-canvas;
    // ingested nodes are pulled harder so they stay central.
    for (let i = 0; i < nodes.length; i++) {
      const pull = nodes[i].ingested ? 0.012 : 0.006
      fx[i] += (cx - pos[i].x) * pull
      fy[i] += (cy - pos[i].y) * pull
    }

    const cool = 0.85 * (1 - step / iterations) + 0.05
    for (let i = 0; i < nodes.length; i++) {
      pos[i].x = clamp(pos[i].x + fx[i] * cool * 0.02, 12, width - 12)
      pos[i].y = clamp(pos[i].y + fy[i] * cool * 0.02, 12, height - 12)
    }
  }

  return nodes.map((n, i) => ({ ...n, x: pos[i].x, y: pos[i].y }))
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

/** The paper-ref → {arxivId|doi} an "add to study" click ingests with. */
export function ingestIdForRef(ref: string): { arxivId?: string; doi?: string } | null {
  if (ref.startsWith('arxiv:')) return { arxivId: ref.slice('arxiv:'.length) }
  if (ref.startsWith('doi:')) return { doi: ref.slice('doi:'.length) }
  return null
}
