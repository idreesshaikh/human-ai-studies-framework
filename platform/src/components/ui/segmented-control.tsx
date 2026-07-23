import { cn } from "@/lib/cn";

/* A small segmented control — a token-styled radio group for picking one of a
 * few short options (the platform has no ToggleGroup/Tabs primitive, and a
 * native <select> reads as a stray form control in a toolbar). Keyboard: the
 * selected segment is the tab stop; arrow keys move and select (roving
 * tabindex, WAI-ARIA radiogroup). Colours/radii/durations are all tokens. */

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  /** Optional longer description for the segment's title/tooltip. */
  hint?: string;
}

interface SegmentedControlProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: SegmentOption<T>[];
  "aria-label": string;
  className?: string;
}

export function SegmentedControl<T extends string>({
  value,
  onChange,
  options,
  className,
  "aria-label": ariaLabel,
}: SegmentedControlProps<T>) {
  const move = (dir: -1 | 1) => {
    const i = options.findIndex((o) => o.value === value);
    if (i < 0) return;
    const next = (i + dir + options.length) % options.length;
    onChange(options[next].value);
  };

  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-0.5 rounded-input border border-border bg-bg p-0.5",
        className,
      )}
    >
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            title={o.hint}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                e.preventDefault();
                move(1);
              } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                e.preventDefault();
                move(-1);
              }
            }}
            className={cn(
              "rounded-chip px-2.5 py-1 font-mono text-xs font-medium transition-colors duration-fast",
              selected
                ? "bg-accent-soft text-accent"
                : "text-text-muted hover:text-text",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
