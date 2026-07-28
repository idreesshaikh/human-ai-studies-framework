/* The layout contract, as data: every screen is a Surface owning exactly
 * four things — one measure, one gutter, one rhythm, one scroller. Screens
 * used to each pick their own p-, gap-, and max-w- values with no shared
 * rule, which is what made panel-to-panel navigation read as different
 * tools.
 *
 * Pure and dependency-free so `verify-layout.mjs` can assert every branch
 * without a DOM — the same pattern as `role.ts`. */

export const MEASURES = ["narrow", "reading", "work", "wide"] as const;
export type Measure = (typeof MEASURES)[number];

export interface SurfaceClasses {
  /** Clips; never scrolls itself — a Surface has exactly one scroller. */
  root: string;
  /** The one scroller. Carries the actual overflow. */
  body: string;
  /** The measured, centred column inside the scroller. */
  column: string;
}

/** The three class strings a `<Surface measure>` renders. Kept as pure
 * string-building (no JSX) so it can be asserted on directly: the root must
 * never carry `overflow-auto`, the body must carry exactly one, and the
 * column's measure must be one of the four tokens — never a bare
 * `max-w-<n>` escape. */
export function surfaceClasses(measure: Measure): SurfaceClasses {
  return {
    root: "flex h-full min-h-0 flex-col overflow-hidden",
    body: "min-h-0 flex-1 overflow-auto overscroll-contain",
    column: `mx-auto flex w-full flex-col gap-section p-gutter max-w-${measure}`,
  };
}
