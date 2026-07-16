import { describe, expect, it } from 'vitest'
import type { StudyEvent } from '../src/lib/api'
import { assembleLanes, ORIGIN_COLOR, timeDomain } from '../src/lib/lanes'

const T0 = Date.parse('2026-07-11T10:00:00.000Z')

function ev(
  seq: number,
  type: string,
  payload: Record<string, unknown> = {},
  offsetSec = seq * 10,
): StudyEvent {
  return {
    v: 3,
    ts: new Date(T0 + offsetSec * 1000).toISOString(),
    mono: offsetSec * 1000,
    sessionId: 'S-test',
    participantId: 'P01',
    condition: 'ai-assisted',
    seq,
    type,
    payload,
    flags: [],
  }
}

describe('assembleLanes', () => {
  it('interleaves heterogeneous events from several legs onto lanes', () => {
    const lanes = assembleLanes([
      ev(0, 'session_start'),
      ev(1, 'fatigue_response', { score: 3 }),
      ev(2, 'edit_burst', { origin: 'human', durationMs: 2000, charsAdded: 40 }),
      ev(3, 'clipboard_paste', { charCount: 120 }),
      ev(4, 'ai_suggestion', { action: 'accepted', visibleMs: 1500 }),
      ev(5, 'session_end'),
    ])
    const byKey = Object.fromEntries(lanes.map((l) => [l.key, l]))
    expect(Object.keys(byKey)).toEqual([
      'session',
      'selfreport',
      'edits',
      'pastes',
      'ai',
    ])
    // Two legs on one axis: cognitive + behavioral.
    expect(new Set(lanes.map((l) => l.leg))).toEqual(
      new Set(['session', 'cognitive', 'behavioral']),
    )
    expect(byKey.session.items).toHaveLength(2)
    expect(byKey.selfreport.items[0].label).toBe('fatigue 3/5')
  })

  it('renders edit bursts as spans colored by origin, fixed assignment', () => {
    const lanes = assembleLanes([
      ev(0, 'edit_burst', { origin: 'human', durationMs: 3000 }),
      ev(1, 'edit_burst', { origin: 'ai', durationMs: 500 }),
      ev(2, 'edit_burst', { origin: 'paste', durationMs: 100 }),
    ])
    const edits = lanes.find((l) => l.key === 'edits')!
    expect(edits.items.map((i) => i.kind)).toEqual(['span', 'span', 'span'])
    expect(edits.items.map((i) => i.colorKey)).toEqual([
      ORIGIN_COLOR.human,
      ORIGIN_COLOR.ai,
      ORIGIN_COLOR.paste,
    ])
    // Origins keep distinct categorical slots - the acceptance criterion
    // "origin coloring visibly distinguishes human/ai/paste".
    expect(new Set(edits.items.map((i) => i.colorKey)).size).toBe(3)
    // The span covers [ts - durationMs, ts].
    expect(edits.items[0].t1! - edits.items[0].t0).toBe(3000)
  })

  it('pairs stuck_detected with stuck_response into one span carrying both seqs', () => {
    const lanes = assembleLanes([
      ev(0, 'stuck_detected', {}, 0),
      ev(1, 'stuck_response', { answer: 'yes' }, 90),
    ])
    const [item] = lanes.find((l) => l.key === 'selfreport')!.items
    expect(item.kind).toBe('span')
    expect(item.seqs).toEqual([0, 1])
    expect(item.t1! - item.t0).toBe(90_000)
  })

  it('reconstructs a stuck span from evidenceMs when the detect event was lost', () => {
    const lanes = assembleLanes([
      ev(1, 'stuck_response', { answer: 'no', evidenceMs: 45_000 }, 100),
    ])
    const [item] = lanes.find((l) => l.key === 'selfreport')!.items
    expect(item.t1! - item.t0).toBe(45_000)
  })

  it('turns pause/resume into a background band and closes dangling pauses', () => {
    const paired = assembleLanes([
      ev(0, 'session_paused', {}, 10),
      ev(1, 'session_resumed', { pausedMs: 20_000 }, 30),
      ev(2, 'session_end', {}, 40),
    ])
    const bands = paired
      .find((l) => l.key === 'session')!
      .items.filter((i) => i.kind === 'band')
    expect(bands).toHaveLength(1)
    expect(bands[0].t1! - bands[0].t0).toBe(20_000)

    const dangling = assembleLanes([
      ev(0, 'session_paused', {}, 10),
      ev(1, 'fatigue_response', { score: 2 }, 50),
    ])
    const band = dangling
      .find((l) => l.key === 'session')!
      .items.find((i) => i.kind === 'band')!
    expect(band.label).toContain('never resumed')
    expect(band.t1! - band.t0).toBe(40_000)
  })

  it('annotates accepted suggestions with review latency', () => {
    const lanes = assembleLanes([
      ev(0, 'ai_suggestion', { action: 'shown' }),
      ev(1, 'ai_suggestion', { action: 'accepted', visibleMs: 2400 }),
      ev(2, 'ai_suggestion', { action: 'dismissed', visibleMs: 900 }),
    ])
    const ai = lanes.find((l) => l.key === 'ai')!
    expect(ai.items.map((i) => i.glyph)).toEqual(['ring', 'dot', 'cross'])
    expect(ai.items[1].label).toContain('2.4s review')
  })

  it('converts consecutive visible_range events into contiguous bands', () => {
    const lanes = assembleLanes([
      ev(0, 'visible_range', { file: 'a.py', topLine: 0, bottomLine: 40 }, 0),
      ev(1, 'visible_range', { file: 'a.py', topLine: 40, bottomLine: 80 }, 20),
      ev(2, 'session_end', {}, 30),
    ])
    const vp = lanes.find((l) => l.key === 'viewport')!
    expect(vp.items).toHaveLength(2)
    expect(vp.items[0].t1).toBe(vp.items[1].t0)
    expect(vp.items[0].label).toContain('lines 0-40')
    // The trailing range extends to the last event.
    expect(vp.items[1].t1! - vp.items[1].t0).toBe(10_000)
  })

  it('renders the agent lane: sized turns, tool ticks, loop spans, outcome flags', () => {
    const lanes = assembleLanes([
      ev(0, 'agent_turn', { responseChars: 1200 }),
      ev(1, 'tool_call', { tool: 'Edit' }),
      ev(2, 'reliance_loop_start', {}, 20),
      ev(3, 'reliance_loop_end', {}, 50),
      ev(4, 'workspace_snapshot', {}),
      ev(5, 'task_outcome', { passed: true, firstGreen: true }),
    ])
    const agent = lanes.find((l) => l.key === 'agent')!
    expect(agent.leg).toBe('agent')
    const kinds = Object.fromEntries(agent.items.map((i) => [i.type, i]))
    expect(kinds.agent_turn.weight).toBeGreaterThan(1)
    expect(kinds.tool_call.glyph).toBe('tick')
    expect(kinds.reliance_loop.kind).toBe('span')
    expect(kinds.reliance_loop.seqs).toEqual([2, 3])
    expect(kinds.task_outcome.glyph).toBe('flag')
    expect(kinds.task_outcome.colorKey).toBe('status-good')
  })

  it('drops no event type silently - unknown types land in Other', () => {
    const lanes = assembleLanes([ev(0, 'environment_snapshot')])
    const other = lanes.find((l) => l.key === 'other')!
    expect(other.items[0].label).toBe('environment snapshot')
  })

  it('omits empty lanes and orders items by seq regardless of input order', () => {
    const lanes = assembleLanes([
      ev(1, 'fatigue_response', { score: 4 }),
      ev(0, 'session_start'),
    ])
    expect(lanes.map((l) => l.key)).toEqual(['session', 'selfreport'])
  })
})

describe('timeDomain', () => {
  it('spans min..max across every lane with padding', () => {
    const lanes = assembleLanes([
      ev(0, 'session_start', {}, 0),
      ev(1, 'session_end', {}, 100),
    ])
    const [lo, hi] = timeDomain(lanes)
    expect(lo).toBeLessThan(T0)
    expect(hi).toBeGreaterThan(T0 + 100_000)
  })

  it('falls back to a unit domain with no events', () => {
    expect(timeDomain([])).toEqual([0, 1])
  })
})
