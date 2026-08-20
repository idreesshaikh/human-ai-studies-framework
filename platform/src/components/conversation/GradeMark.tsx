import { cn } from "@/lib/cn";

/*
 * It replaced a single dot that carried magnitude in its DIAMETER. That mark asked the
 * eye to judge absolute circle size with nothing to compare against, which it cannot
 * do: the smallest steps sat two pixels apart, a lone mark read as a list bullet, and
 * two cards in different rows could not be ranked against each other at all.
 */

export const GRADE_STEPS = 4;

/** A 0..1 confidence as a 1..4 GRADE level. */
export function magnitude(value: number): 1 | 2 | 3 | 4 {
  const step = Math.ceil(Math.min(Math.max(value, 0.001), 1) * GRADE_STEPS);
  return Math.min(Math.max(step, 1), GRADE_STEPS) as 1 | 2 | 3 | 4;
}

/** Plain words for a level, so the mark is never the only carrier. */
export function gradeLabel(level: number): string {
  return (
    ["weak support", "some support", "well grounded", "strongly grounded"][
      level - 1
    ] ?? "unsourced"
  );
}

export function GradeMark({
  level,
  unsourced,
  className,
}: {
  /** 1..4. */
  level?: number;
  unsourced?: boolean;
  className?: string;
}) {
  const filled = unsourced ? 0 : Math.min(Math.max(level ?? 0, 0), GRADE_STEPS);
  return (
    <span
      aria-hidden
      className={cn("grade", unsourced && "grade-unrated", className)}
    >
      {Array.from({ length: GRADE_STEPS }).map((_, i) => (
        <span
          key={i}
          className={cn("grade-pip", i >= filled && "grade-pip-off")}
        />
      ))}
    </span>
  );
}
