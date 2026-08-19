import { cn } from "@/lib/cn";

/* A small segmented control — the record's tab strip: a row of ruled cells
 * where the selected one is struck at full density and the rest stay paper.
 * A radio group for picking one of a few short options (the platform has no
 * ToggleGroup/Tabs primitive, and a native <select> reads as a stray form
 * control in a toolbar). Keyboard: the selected segment is the tab stop; arrow
 * keys move and select (roving tabindex, WAI-ARIA radiogroup). */

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
        "inline-flex items-stretch gap-0.5 rounded-control border border-border bg-surface p-0.5",
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
              "type-control relative rounded-control-inner px-3 py-1.5 transition-colors duration-standard",
              selected
                ? "control-axis axis-under"
                : "text-text-muted hover:bg-zone-9 hover:text-text",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
