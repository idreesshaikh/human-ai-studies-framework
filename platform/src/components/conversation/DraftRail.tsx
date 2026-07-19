import { MANDATORY_SLOTS, SLOT_LABELS, type ProtocolDraft } from "@/lib/types";
import { SlotMeter } from "./SlotMeter";

/* The draft rail: the protocol compiled so far. Deliberately plain —
 * tabular, hairline borders, minimal motion. It's a projection of the draft
 * model, rendered YAML-ish so the shape reads clearly; the real YAML comes
 * from the server compiler later. */
export function DraftRail({ draft }: { draft: ProtocolDraft }) {
  return (
    <aside
      data-agent="draft-rail"
      className="flex h-full flex-col gap-4 border-l-2 border-border-strong bg-surface p-4"
    >
      <div>
        <h2 className="font-display text-lg font-bold uppercase tracking-wide text-text">
          Protocol draft
        </h2>
        <p className="text-xs text-text-muted">
          Compiled from the moves you've accepted.
        </p>
      </div>

      <SlotMeter draft={draft} />

      <div className="min-h-0 flex-1 overflow-auto rounded-input border-2 border-border-strong bg-bg p-3">
        <pre className="tabular whitespace-pre-wrap font-mono text-xs leading-relaxed text-text">
          {MANDATORY_SLOTS.map((s) => {
            const items = draft[s];
            const head = `${s}:`;
            if (items.length === 0) {
              return `${head}  # unresolved — ${SLOT_LABELS[s]}\n`;
            }
            return (
              head +
              "\n" +
              items.map((v) => `  - ${v}`).join("\n") +
              "\n"
            );
          }).join("")}
        </pre>
      </div>
    </aside>
  );
}
