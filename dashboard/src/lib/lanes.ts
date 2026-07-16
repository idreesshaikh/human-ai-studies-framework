/**
 * Timeline lane assembly (FR-DASH-4): interleave heterogeneous StudyEvents
 * from every leg onto one shared time axis as swimlane items.
 *
 * Pure logic - the Timeline component only draws what this returns. Three
 * geometries: `point` (an instant), `span` (an interval with meaning),
 * `band` (background shading, e.g. paused/idle). No event type is silently
 * dropped: anything unrecognized lands in the "Other" lane.
 */

import type { StudyEvent } from './api'

export type ItemKind = 'point' | 'span' | 'band'

export interface LaneItem {
  kind: ItemKind
  /** Epoch ms. */
  t0: number
  /** Epoch ms; spans/bands only. */
  t1?: number
  /** Short human label (tooltip headline). */
  label: string
  /** Semantic color key, resolved to a CSS variable by the component. */
  colorKey: string
  /** Marker glyph for points: dot | ring | cross | diamond | tick | flag. */
  glyph?: 'dot' | 'ring' | 'cross' | 'diamond' | 'tick' | 'flag'
  /** Relative size weight for points (1 = default). */
  weight?: number
  /** The seq(s) behind this item - the two-way link with other views. */
  seqs: number[]
  type: string
  payload: Record<string, unknown>
}

export interface Lane {
  key: string
  label: string
  /** Which instrument leg the lane belongs to (the four-legs claim). */
  leg: 'session' | 'cognitive' | 'behavioral' | 'agent' | 'other'
  items: LaneItem[]
}

const LANE_DEFS: { key: string; label: string; leg: Lane['leg'] }[] = [
  { key: 'session', label: 'Session', leg: 'session' },
  { key: 'selfreport', label: 'Self-report', leg: 'cognitive' },
  { key: 'edits', label: 'Edits', leg: 'behavioral' },
  { key: 'pastes', label: 'Pastes', leg: 'behavioral' },
  { key: 'ai', label: 'AI suggestions', leg: 'behavioral' },
  { key: 'viewport', label: 'Viewport', leg: 'behavioral' },
  { key: 'agent', label: 'Agent', leg: 'agent' },
  { key: 'other', label: 'Other', leg: 'other' },
]

/**
 * Edit-burst origin -> categorical slot, fixed assignment (never re-ranked):
 * human=1(blue), ai=2(aqua), paste=3(yellow), undo-redo=4(green).
 */
export const ORIGIN_COLOR: Record<string, string> = {
  human: 'series-1',
  ai: 'series-2',
  paste: 'series-3',
  'undo-redo': 'series-4',
}

const num = (v: unknown, fallback = 0): number =>
  typeof v === 'number' && Number.isFinite(v) ? v : fallback

const str = (v: unknown): string => (typeof v === 'string' ? v : '')

export function assembleLanes(events: StudyEvent[]): Lane[] {
  const lanes = new Map<string, LaneItem[]>(LANE_DEFS.map((d) => [d.key, []]))
  const add = (lane: string, item: LaneItem) => lanes.get(lane)!.push(item)

  const sorted = [...events].sort((a, b) => a.seq - b.seq)
  const tsOf = (e: StudyEvent) => new Date(e.ts).getTime()

  // Open state for span/band pairing.
  let pausedAt: { t: number; seq: number } | null = null
  let blurredAt: { t: number; seq: number } | null = null
  let stuckAt: { t: number; seq: number; payload: Record<string, unknown> } | null = null
  let loopAt: { t: number; seq: number; payload: Record<string, unknown> } | null = null
  let lastVisible: { t: number; seq: number; payload: Record<string, unknown> } | null = null
  const sessionEnd = sorted.length ? tsOf(sorted[sorted.length - 1]) : 0

  const flushVisible = (until: number) => {
    if (!lastVisible) return
    add('viewport', {
      kind: 'span',
      t0: lastVisible.t,
      t1: until,
      label: `${str(lastVisible.payload.file)} lines ${num(lastVisible.payload.topLine)}-${num(lastVisible.payload.bottomLine)}`,
      colorKey: 'muted',
      seqs: [lastVisible.seq],
      type: 'visible_range',
      payload: lastVisible.payload,
    })
    lastVisible = null
  }

  for (const e of sorted) {
    const t = tsOf(e)
    const base = { seqs: [e.seq], type: e.type, payload: e.payload }
    switch (e.type) {
      case 'session_start':
      case 'session_end':
      case 'session_timer_ended':
        add('session', {
          kind: 'point',
          t0: t,
          label: e.type.replace(/_/g, ' '),
          colorKey: 'ink',
          glyph: 'tick',
          ...base,
        })
        break
      case 'session_paused':
        pausedAt = { t, seq: e.seq }
        break
      case 'session_resumed':
        add('session', {
          kind: 'band',
          t0: pausedAt?.t ?? t - num(e.payload.pausedMs),
          t1: t,
          label: 'paused',
          colorKey: 'muted',
          seqs: pausedAt ? [pausedAt.seq, e.seq] : [e.seq],
          type: 'session_paused',
          payload: e.payload,
        })
        pausedAt = null
        break
      case 'window_blur':
        blurredAt = { t, seq: e.seq }
        break
      case 'window_focus':
        if (blurredAt) {
          add('session', {
            kind: 'band',
            t0: blurredAt.t,
            t1: t,
            label: 'window unfocused / idle',
            colorKey: 'muted',
            seqs: [blurredAt.seq, e.seq],
            type: 'window_blur',
            payload: e.payload,
          })
          blurredAt = null
        }
        break

      case 'fatigue_response':
        add('selfreport', {
          kind: 'point',
          t0: t,
          label: `fatigue ${num(e.payload.score)}/5`,
          colorKey: 'series-5',
          glyph: 'dot',
          weight: 0.6 + num(e.payload.score) / 5,
          ...base,
        })
        break
      case 'stuck_detected':
        stuckAt = { t, seq: e.seq, payload: e.payload }
        break
      case 'stuck_response': {
        const t0 = stuckAt?.t ?? t - num(e.payload.evidenceMs)
        add('selfreport', {
          kind: 'span',
          t0,
          t1: t,
          label: `stuck episode (${str(e.payload.answer) || 'no answer'})`,
          colorKey: 'series-6',
          seqs: stuckAt ? [stuckAt.seq, e.seq] : [e.seq],
          type: 'stuck_response',
          payload: e.payload,
        })
        stuckAt = null
        break
      }
      case 'end_survey':
        add('selfreport', {
          kind: 'point',
          t0: t,
          label: 'TLX debrief',
          colorKey: 'series-5',
          glyph: 'diamond',
          ...base,
        })
        break

      case 'edit_burst': {
        const origin = str(e.payload.origin) || 'human'
        add('edits', {
          kind: 'span',
          t0: t - num(e.payload.durationMs),
          t1: t,
          label: `${origin} edit: +${num(e.payload.charsAdded)}/-${num(e.payload.charsDeleted)} chars`,
          colorKey: ORIGIN_COLOR[origin] ?? 'muted',
          ...base,
        })
        break
      }
      case 'file_save':
        add('edits', {
          kind: 'point',
          t0: t,
          label: `save ${str(e.payload.file)}`,
          colorKey: 'ink',
          glyph: 'tick',
          ...base,
        })
        break
      case 'clipboard_paste':
        add('pastes', {
          kind: 'point',
          t0: t,
          label: `paste ${num(e.payload.charCount)} chars`,
          colorKey: 'series-3',
          glyph: 'dot',
          weight: 0.8 + Math.min(num(e.payload.charCount) / 400, 1.5),
          ...base,
        })
        break
      case 'ai_suggestion': {
        const action = str(e.payload.action)
        const glyph =
          action === 'accepted' ? 'dot' : action === 'shown' ? 'ring' : 'cross'
        const latency = num(e.payload.visibleMs)
        add('ai', {
          kind: 'point',
          t0: t,
          label:
            `suggestion ${action}` +
            (action !== 'shown' && latency ? ` after ${(latency / 1000).toFixed(1)}s review` : ''),
          colorKey: action === 'accepted' ? 'series-2' : 'muted',
          glyph,
          weight: action === 'accepted' ? 1.2 : 1,
          ...base,
        })
        break
      }
      case 'visible_range':
        flushVisible(t)
        lastVisible = { t, seq: e.seq, payload: e.payload }
        break

      // ---- agent leg (MP-12) - rendered as soon as the data exists ----
      case 'agent_turn':
        add('agent', {
          kind: 'point',
          t0: t,
          label: `agent turn (${num(e.payload.responseChars) || '?'} chars)`,
          colorKey: 'series-8',
          glyph: 'dot',
          weight: 0.8 + Math.min(num(e.payload.responseChars) / 2000, 1.7),
          ...base,
        })
        break
      case 'tool_call':
        add('agent', {
          kind: 'point',
          t0: t,
          label: `tool: ${str(e.payload.tool) || 'unknown'}`,
          colorKey: 'series-8',
          glyph: 'tick',
          ...base,
        })
        break
      case 'reliance_loop_start':
        loopAt = { t, seq: e.seq, payload: e.payload }
        break
      case 'reliance_loop':
      case 'reliance_loop_end': {
        const t0 = loopAt?.t ?? t - num(e.payload.durationMs)
        add('agent', {
          kind: 'span',
          t0,
          t1: t,
          label: 'reliance loop',
          colorKey: 'series-6',
          seqs: loopAt ? [loopAt.seq, e.seq] : [e.seq],
          type: 'reliance_loop',
          payload: e.payload,
        })
        loopAt = null
        break
      }
      case 'workspace_snapshot':
        add('agent', {
          kind: 'point',
          t0: t,
          label: 'workspace snapshot',
          colorKey: 'muted',
          glyph: 'tick',
          ...base,
        })
        break
      case 'task_outcome': {
        const passed = e.payload.passed === true || e.payload.firstGreen === true
        add('agent', {
          kind: 'point',
          t0: t,
          label: passed ? 'task outcome: first green' : 'task outcome',
          colorKey: passed ? 'status-good' : 'status-serious',
          glyph: 'flag',
          weight: 1.4,
          ...base,
        })
        break
      }

      default:
        add('other', {
          kind: 'point',
          t0: t,
          label: e.type.replace(/_/g, ' '),
          colorKey: 'muted',
          glyph: 'tick',
          ...base,
        })
    }
  }
  flushVisible(sessionEnd)
  // Unclosed opens (session cut off mid-pause / mid-stuck) still render.
  if (pausedAt) {
    add('session', {
      kind: 'band',
      t0: pausedAt.t,
      t1: sessionEnd,
      label: 'paused (never resumed)',
      colorKey: 'muted',
      seqs: [pausedAt.seq],
      type: 'session_paused',
      payload: {},
    })
  }
  if (stuckAt) {
    add('selfreport', {
      kind: 'span',
      t0: stuckAt.t,
      t1: sessionEnd,
      label: 'stuck episode (no response)',
      colorKey: 'series-6',
      seqs: [stuckAt.seq],
      type: 'stuck_detected',
      payload: stuckAt.payload,
    })
  }

  return LANE_DEFS.filter((d) => lanes.get(d.key)!.length > 0).map((d) => ({
    ...d,
    items: lanes.get(d.key)!,
  }))
}

/** Domain [min, max] over every item, padded so edge marks stay visible. */
export function timeDomain(lanesList: Lane[]): [number, number] {
  let min = Infinity
  let max = -Infinity
  for (const lane of lanesList) {
    for (const it of lane.items) {
      min = Math.min(min, it.t0)
      max = Math.max(max, it.t1 ?? it.t0)
    }
  }
  if (!Number.isFinite(min)) return [0, 1]
  const pad = Math.max((max - min) * 0.02, 1000)
  return [min - pad, max + pad]
}
