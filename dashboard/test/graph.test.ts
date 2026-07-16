import { describe, expect, it } from 'vitest'
import { ingestIdForRef, layoutGraph, type GraphNodeIn } from '../src/lib/graph'

const nodes: GraphNodeIn[] = [
  { paperRef: 'arxiv:2302.06590', title: 'Peng', year: 2023, citationCount: 400, ingested: true },
  { paperRef: 'arxiv:2205.06537', title: 'Ziegler', year: 2022, citationCount: 300, ingested: false },
  { paperRef: 'doi:10.1000/x', title: 'Neighbour', year: 2021, citationCount: 120, ingested: false },
]
const edges = [
  { src: 'arxiv:2302.06590', dst: 'arxiv:2205.06537', kind: 'references' },
  { src: 'arxiv:2302.06590', dst: 'doi:10.1000/x', kind: 'citations' },
]

describe('layoutGraph', () => {
  it('positions every node inside the canvas', () => {
    const out = layoutGraph(nodes, edges, { width: 640, height: 440 })
    expect(out).toHaveLength(3)
    for (const n of out) {
      expect(n.x).toBeGreaterThanOrEqual(0)
      expect(n.x).toBeLessThanOrEqual(640)
      expect(n.y).toBeGreaterThanOrEqual(0)
      expect(n.y).toBeLessThanOrEqual(440)
    }
  })

  it('is deterministic — same input, same output', () => {
    const a = layoutGraph(nodes, edges)
    const b = layoutGraph(nodes, edges)
    expect(a.map((n) => [n.x, n.y])).toEqual(b.map((n) => [n.x, n.y]))
  })

  it('keeps ingested nodes nearer the centre than peripheral suggestions', () => {
    const out = layoutGraph(nodes, edges, { width: 640, height: 440 })
    const dist = (r: string) => {
      const n = out.find((x) => x.paperRef === r)!
      return Math.hypot(n.x - 320, n.y - 220)
    }
    // The single ingested node is pulled harder to centre than the isolated
    // suggestion with no edge back to the seed.
    expect(dist('arxiv:2302.06590')).toBeLessThan(dist('doi:10.1000/x') + 1e-6)
  })

  it('handles an empty graph', () => {
    expect(layoutGraph([], [])).toEqual([])
  })
})

describe('ingestIdForRef', () => {
  it('maps refs to the ingest identifier', () => {
    expect(ingestIdForRef('arxiv:2302.06590')).toEqual({ arxivId: '2302.06590' })
    expect(ingestIdForRef('doi:10.1/x')).toEqual({ doi: '10.1/x' })
    expect(ingestIdForRef('s2:abc')).toBeNull()
  })
})
