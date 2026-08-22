import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, SlidersHorizontal } from "lucide-react";
import { cn } from "@/lib/cn";
import { STEER_STOPS, steerStop, type SteerLevel } from "@/lib/steer";

/* The steer mode  -  how much the assistant drives this conversation.
 *
 * It belongs in the composer command bar because it changes how the assistant
 * responds to the next message. The bar exposes the current mode as a compact
 * button; the four choices live in a small picker so the input stays the main
 * thing to look at and the mode remains one click away.
 *
 * The four options are real modes, not decorative labels: selecting one keeps
 * the existing server profile and initiative levers, and the active mode is
 * announced with aria-pressed. */
export function SteerDial({
  value,
  onChange,
  className,
}: {
  value: SteerLevel;
  onChange: (next: SteerLevel) => void;
  className?: string;
}) {
  const stop = steerStop(value);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div
      data-agent="steer-dial"
      ref={rootRef}
      className={cn("relative shrink-0", className)}
    >
      <button
        type="button"
        className={cn(
          "plate-lift inline-flex h-8 items-center gap-1.5 rounded-control border border-control-edge bg-surface px-2 text-text shadow-mark transition-colors duration-fast hover:bg-zone-9",
          open && "border-accent bg-zone-9",
        )}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={`Steer mode: ${stop.label}`}
        onClick={() => setOpen((current) => !current)}
      >
        <SlidersHorizontal className="size-4 text-text-muted" aria-hidden />
        <span className="type-control">{stop.label}</span>
        <ChevronDown
          className={cn("size-3.5 text-text-muted transition-transform duration-fast", open && "rotate-180")}
          aria-hidden
        />
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Choose steer mode"
          className="absolute bottom-full right-0 z-50 mb-2 w-80 rounded-card border border-border bg-surface-raised p-2 shadow-lifted"
        >
          <div className="px-2 pb-2 pt-1">
            <p className="type-subhead text-text">Steer the assistant</p>
            <p className="type-caption mt-0.5 text-text-muted">
              Choose how much initiative it takes in this study.
            </p>
          </div>
          <div className="space-y-1">
            {STEER_STOPS.map((option) => {
              const selected = option.level === value;
              return (
                <button
                  key={option.id}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => {
                    onChange(option.level);
                    setOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-input px-2 py-2 text-left transition-colors duration-fast hover:bg-zone-9",
                    selected && "bg-accent-wash",
                  )}
                >
                  <span className="flex size-4 shrink-0 items-center justify-center rounded-dot border border-control-edge bg-surface">
                    {selected && <Check className="size-3 text-accent" aria-hidden />}
                  </span>
                  <span className="min-w-0">
                    <span className="type-control block text-text">{option.label}</span>
                    <span className="type-caption block text-text-muted">{option.summary}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
