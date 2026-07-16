/**
 * Viewport placement heuristics for the tooltip + guided-tour overlays
 * (FR-DASH-9). Pure module: node-testable, no DOM types beyond plain rects.
 */

export interface Rect {
  x: number
  y: number
  width: number
  height: number
}

export interface Size {
  width: number
  height: number
}

export type Placement = 'top' | 'bottom' | 'left' | 'right' | 'center'

const clamp = (v: number, lo: number, hi: number): number =>
  Math.min(Math.max(v, lo), Math.max(lo, hi))

/**
 * Anchored tooltip position: above the anchor, flipping below when there is
 * no headroom; horizontally centered and clamped to the viewport.
 */
export function placeTip(anchor: Rect, tip: Size, viewport: Size, gap = 8) {
  const cx = anchor.x + anchor.width / 2
  let y = anchor.y - tip.height - gap
  if (y < gap) y = anchor.y + anchor.height + gap
  return {
    x: clamp(cx - tip.width / 2, gap, viewport.width - tip.width - gap),
    y: clamp(y, gap, viewport.height - tip.height - gap),
  }
}

/**
 * Tour-card position relative to the spotlit anchor: prefer below, then
 * above, then right, then left; center when nothing fits (or no anchor).
 * Always clamped fully on-screen.
 */
export function placeCard(
  anchor: Rect | null,
  card: Size,
  viewport: Size,
  gap = 12,
): { placement: Placement; x: number; y: number } {
  const center = {
    placement: 'center' as const,
    x: (viewport.width - card.width) / 2,
    y: (viewport.height - card.height) / 2,
  }
  if (!anchor) return center

  const cx = clamp(
    anchor.x + anchor.width / 2 - card.width / 2,
    gap,
    viewport.width - card.width - gap,
  )
  const cy = clamp(
    anchor.y + anchor.height / 2 - card.height / 2,
    gap,
    viewport.height - card.height - gap,
  )
  if (anchor.y + anchor.height + gap + card.height <= viewport.height) {
    return { placement: 'bottom', x: cx, y: anchor.y + anchor.height + gap }
  }
  if (anchor.y - gap - card.height >= 0) {
    return { placement: 'top', x: cx, y: anchor.y - gap - card.height }
  }
  if (anchor.x + anchor.width + gap + card.width <= viewport.width) {
    return { placement: 'right', x: anchor.x + anchor.width + gap, y: cy }
  }
  if (anchor.x - gap - card.width >= 0) {
    return { placement: 'left', x: anchor.x - gap - card.width, y: cy }
  }
  return center
}
