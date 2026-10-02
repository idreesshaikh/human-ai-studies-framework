import type { CSSProperties } from "react";
import { cn } from "@/lib/cn";

export function groundingLabel(value: number): string {
  const step = Math.ceil(Math.min(Math.max(value, 0.001), 1) * 4);
  return (
    ["weak support", "some support", "well grounded", "strongly grounded"][
      Math.min(Math.max(step, 1), 4) - 1
    ] ?? "unsourced"
  );
}

export function GroundingMark({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  const scale = Math.min(Math.max(value, 0), 1);
  return (
    <span
      aria-hidden
      className={cn("mark-framed", className)}
      style={{ "--mark-scale": scale } as CSSProperties}
    />
  );
}

export function ConfidenceValue({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  return (
    <span aria-hidden className={cn("type-quantity text-mark", className)}>
      {value.toFixed(2)}
    </span>
  );
}

export function Confidence({
  value,
  words = true,
  className,
}: {
  value?: number;

  words?: boolean;
  className?: string;
}) {
  if (value == null) {
    return (
      <span
        className={cn("type-legend text-text-muted", className)}
        title="No quality score for this source"
      >
        unrated
      </span>
    );
  }
  const printed = value.toFixed(2);
  const band = groundingLabel(value);
  return (
    <span
      className={cn("inline-flex items-center gap-1.5", className)}
      role="img"
      aria-label={`Literature confidence ${printed}, ${band}`}
      title={`Literature confidence ${printed}  -  ${band}`}
    >
      <GroundingMark value={value} />

      <ConfidenceValue value={value} />
      {words && <span className="type-caption text-text-muted">{band}</span>}
    </span>
  );
}
