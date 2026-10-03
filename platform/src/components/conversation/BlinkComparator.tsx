import { useEffect, useState } from "react";
import { Repeat } from "lucide-react";
import { cn } from "@/lib/cn";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { buildPlates, type DiffLine } from "@/lib/comparator";

export type { DiffLine };

/* Compare protocol versions in place. Reduced motion disables automatic alternation. */
export function BlinkComparator({
  lines,
  className,
}: {
  lines: DiffLine[];
  className?: string;
}) {
  const reducedMotion = usePrefersReducedMotion();
  const [running, setRunning] = useState(false);
  const [phase, setPhase] = useState<0 | 1>(0);

  useEffect(() => {
    if (!running || reducedMotion) return;
    const id = window.setInterval(() => setPhase((p) => (p === 0 ? 1 : 0)), 620);
    return () => window.clearInterval(id);
  }, [running, reducedMotion]);

  /* The plate arithmetic lives in `lib/comparator.ts` and is exercised by
   * `scripts/verify-comparator.mjs`: the marker stripping and the
   * first-version case are the two things that can be wrong in a way no
   * screenshot would show. */
  const { record, before, after, firstVersion, rows } = buildPlates(lines);

  const blinking = firstVersion ? null : running || reducedMotion ? phase : null;

  function toggle() {
    if (reducedMotion) {
      setPhase((p) => (p === 0 ? 1 : 0));
      return;
    }
    setRunning((r) => !r);
  }

  return (
    <div className={className}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="type-legend text-text-muted">
          {blinking === null
            ? "What this changes"
            : blinking === 0
              ? "Before"
              : "After"}
        </p>
        {firstVersion ? (
          <span className="type-caption text-text-muted">
            first version, nothing to compare
          </span>
        ) : (
        <button
          type="button"
          onClick={toggle}
          aria-pressed={reducedMotion ? undefined : running}
          className="type-caption inline-flex items-center gap-1.5 rounded-control border border-border px-2 py-1 text-text-muted transition-colors duration-fast hover:border-control-edge hover:text-text"
          title={
            reducedMotion
              ? "Show the other version of this protocol"
              : "Alternate the two versions in place, so the only thing that moves is what changed"
          }
        >
          <Repeat aria-hidden className="size-3" />
          {reducedMotion ? "Swap" : running ? "Stop" : "Blink"}
        </button>
        )}
      </div>

      <div
        className="relative overflow-auto rounded-plate border border-border bg-well p-3"
        style={{ minHeight: `${rows * 1.15 + 1.5}em` }}
      >
        {[record, before, after].map((plate, i) => {
          // 0 is the resting record; 1 and 2 are the two alternating plates.
          const visible = blinking === null ? i === 0 : blinking === i - 1;
          return (
            <pre
              key={i}
              aria-hidden={!visible}
              className={cn(
                "type-quantity m-0 whitespace-pre leading-relaxed",
                // Stacked so every state occupies identical coordinates. Only
                // the visible one is painted.
                i > 0 && "absolute inset-0 p-3",
                visible ? "opacity-100" : "opacity-0",
              )}
            >
              {plate.map((d, j) =>
                d.kind === "hunk" ? (
                  <div key={j} className="my-1 border-t border-border" />
                ) : (
                  <div key={j} className={LINE_CLASS[d.kind]}>
                    {d.line}
                  </div>
                ),
              )}
            </pre>
          );
        })}
      </div>
    </div>
  );
}

/* A removed line is struck and left readable, which is the same mark an
 * amendment uses everywhere else in this product. Nothing is tinted green or
 * red: while the plates alternate, a colour difference between "the before
 * plate's removal" and "the after plate's context" would make unchanged text
 * appear to move, which is the one thing a comparator must never do. */
const LINE_CLASS: Record<string, string> = {
  add: "text-text",
  remove: "superseded",
  context: "text-text-muted",
};
