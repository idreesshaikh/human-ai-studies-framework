import { MANDATORY_SLOTS, SLOT_LABELS, type ProtocolDraft } from "@/lib/types";
import { cn } from "@/lib/cn";

/* Protocol completeness as a row of dots, one per required section. Dots
 * light as sections fill; the sections still empty are named explicitly,
 * never silently skipped. */
export function SlotMeter({ draft }: { draft: ProtocolDraft }) {
  const filled = MANDATORY_SLOTS.filter((s) => draft[s].length > 0);
  const unresolved = MANDATORY_SLOTS.filter((s) => draft[s].length === 0);
  const complete = unresolved.length === 0;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <div className="flex gap-1" role="img" aria-label={`${filled.length} of ${MANDATORY_SLOTS.length} protocol sections filled`}>
          {MANDATORY_SLOTS.map((s) => (
            <span
              key={s}
              className={cn(
                "size-2.5 rounded-chip border transition-colors duration-standard",
                draft[s].length > 0
                  ? "border-transparent bg-accent"
                  : "border-border-strong bg-transparent",
              )}
            />
          ))}
        </div>
        <span className="tabular text-xs text-text-muted">
          {filled.length}/{MANDATORY_SLOTS.length}
        </span>
      </div>
      {complete ? (
        <p className="text-xs text-grounded">
          Every mandatory section has a move: ready to compile & validate.
        </p>
      ) : (
        <p className="text-xs text-text-muted">
          Still unresolved: {unresolved.map((s) => SLOT_LABELS[s]).join(", ")}.
        </p>
      )}
    </div>
  );
}
