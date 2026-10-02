

export const MEASURES = ["narrow", "reading", "work", "wide"] as const;
export type Measure = (typeof MEASURES)[number];

export interface SurfaceClasses {

  root: string;

  body: string;

  column: string;
}

export function surfaceClasses(measure: Measure): SurfaceClasses {
  return {
    root: "flex h-full min-h-0 flex-col overflow-hidden",
    body: "min-h-0 flex-1 overflow-auto overscroll-contain",
    column: `mx-auto flex w-full flex-col gap-section p-gutter max-w-${measure}`,
  };
}
