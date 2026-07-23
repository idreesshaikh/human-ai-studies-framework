import { cn } from "@/lib/cn";

/* A paper's continuous quality confidence (0..1) — the signal that replaces
 * the binary Tier A/B hierarchy. Rendered as a compact meter so a high-merit
 * harvested paper reads as strong on its own terms, whatever its provenance.
 * A source with no score reads honestly as "unrated", never a faked number. */
export function Confidence({
  value,
  className,
}: {
  value?: number;
  className?: string;
}) {
  if (value == null) {
    return (
      <span
        className={cn("text-[0.6875rem] text-text-muted", className)}
        title="No quality score for this source"
      >
        unrated
      </span>
    );
  }
  const pct = Math.round(value * 100);
  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      role="img"
      aria-label={`Literature confidence ${pct} percent`}
      title={`Literature confidence ${pct}%`}
    >
      <span className="h-1.5 w-12 overflow-hidden rounded-chip bg-border">
        <span
          className="block h-full rounded-chip bg-accent"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="tabular text-[0.6875rem] font-medium text-text-muted">{pct}%</span>
    </span>
  );
}
