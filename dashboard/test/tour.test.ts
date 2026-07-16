import { describe, expect, it } from 'vitest'
import { placeCard, placeTip } from '../src/lib/place'
import { nextStepIndex, TOUR_STEPS, visibleSteps } from '../src/lib/tour'

const VIEWPORT = { width: 1280, height: 800 }
const CARD = { width: 340, height: 200 }

describe('TOUR_STEPS data sanity (FR-DASH-9)', () => {
  it('has unique ids and non-empty copy', () => {
    const ids = TOUR_STEPS.map((s) => s.id)
    expect(new Set(ids).size).toBe(ids.length)
    for (const s of TOUR_STEPS) {
      expect(s.title.length).toBeGreaterThan(0)
      expect(s.body.length).toBeGreaterThan(40)
    }
  })

  it('only the closing step is unanchored, only the timeline needs a session', () => {
    expect(TOUR_STEPS.filter((s) => !s.anchor).map((s) => s.id)).toEqual(['done'])
    expect(TOUR_STEPS.filter((s) => s.needsSession).map((s) => s.id)).toEqual([
      'timeline',
    ])
  })

  it('speaks plain English: no requirement IDs outside the decoder step', () => {
    for (const s of TOUR_STEPS) {
      if (s.id === 'trace-chips') continue
      expect(`${s.title} ${s.body} ${s.why ?? ''}`).not.toMatch(/\b(FR|NFR)-/)
    }
  })
})

describe('nextStepIndex sequencing', () => {
  it('walks forward and backward through every step when a session exists', () => {
    let i: number | null = 0
    const seen = [0]
    while ((i = nextStepIndex(TOUR_STEPS, i!, 1, true)) !== null) seen.push(i)
    expect(seen).toEqual(TOUR_STEPS.map((_, idx) => idx))
    expect(nextStepIndex(TOUR_STEPS, TOUR_STEPS.length - 1, 1, true)).toBeNull()
    expect(nextStepIndex(TOUR_STEPS, 0, -1, true)).toBeNull()
  })

  it('skips the timeline step when the study has no sessions', () => {
    const timeline = TOUR_STEPS.findIndex((s) => s.needsSession)
    const before = timeline - 1
    expect(nextStepIndex(TOUR_STEPS, before, 1, false)).toBe(timeline + 1)
    expect(nextStepIndex(TOUR_STEPS, timeline + 1, -1, false)).toBe(before)
    expect(visibleSteps(TOUR_STEPS, false)).toHaveLength(TOUR_STEPS.length - 1)
    expect(visibleSteps(TOUR_STEPS, true)).toHaveLength(TOUR_STEPS.length)
  })
})

describe('placeCard heuristic', () => {
  it('prefers below the anchor when there is room', () => {
    const anchor = { x: 400, y: 100, width: 200, height: 50 }
    const p = placeCard(anchor, CARD, VIEWPORT)
    expect(p.placement).toBe('bottom')
    expect(p.y).toBe(100 + 50 + 12)
  })

  it('flips above when the anchor hugs the bottom edge', () => {
    const anchor = { x: 400, y: 700, width: 200, height: 80 }
    expect(placeCard(anchor, CARD, VIEWPORT).placement).toBe('top')
  })

  it('falls to the side for a full-height anchor, centers when nothing fits', () => {
    const tall = { x: 0, y: 0, width: 190, height: 800 }
    expect(placeCard(tall, CARD, VIEWPORT).placement).toBe('right')
    const everything = { x: 0, y: 0, width: 1280, height: 800 }
    expect(placeCard(everything, CARD, VIEWPORT).placement).toBe('center')
  })

  it('centers with no anchor and always stays inside the viewport', () => {
    expect(placeCard(null, CARD, VIEWPORT).placement).toBe('center')
    const corner = { x: 1270, y: 790, width: 400, height: 100 }
    const p = placeCard(corner, CARD, VIEWPORT)
    expect(p.x).toBeGreaterThanOrEqual(0)
    expect(p.x + CARD.width).toBeLessThanOrEqual(VIEWPORT.width)
  })
})

describe('placeTip', () => {
  it('sits above the anchor, centered and clamped', () => {
    const p = placeTip(
      { x: 600, y: 400, width: 60, height: 20 },
      { width: 200, height: 40 },
      VIEWPORT,
    )
    expect(p.y).toBe(400 - 40 - 8)
    expect(p.x).toBe(600 + 30 - 100)
  })

  it('flips below near the top edge and clamps horizontally', () => {
    const p = placeTip(
      { x: 4, y: 10, width: 40, height: 16 },
      { width: 200, height: 40 },
      VIEWPORT,
    )
    expect(p.y).toBe(10 + 16 + 8)
    expect(p.x).toBe(8)
  })
})
