import { MANDATORY_SLOTS, SLOT_LABELS, type ProtocolDraft } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { SlotMeter } from "./SlotMeter";

/* The draft rail: the protocol compiled so far. Deliberately plain —
 * tabular, hairline borders, minimal motion. It's a projection of the draft
 * model, rendered YAML-ish so the shape reads clearly; the real YAML comes
 * from the server compiler later. */
export function DraftRail({
  draft,
  serverYaml,
  compileValid,
  onApply,
  applying,
  onFinish,
}: {
  draft: ProtocolDraft;
  serverYaml?: string;
  compileValid?: boolean;
  onApply?: () => void;
  applying?: boolean;
  onFinish?: () => void;
}) {
  const complete = MANDATORY_SLOTS.every((s) => draft[s].length > 0);
  const body = serverYaml?.trim()
    ? serverYaml
    : MANDATORY_SLOTS.map((s) => {
        const items = draft[s];
        const head = `${s}:`;
        if (items.length === 0) {
          return `${head}  # unresolved — ${SLOT_LABELS[s]}\n`;
        }
        return head + "\n" + items.map((v) => `  - ${v}`).join("\n") + "\n";
      }).join("");

  return (
    <aside
      data-agent="draft-rail"
      className="flex h-full flex-col gap-stack bg-surface p-gutter"
    >
      <div>
        <h2 className="type-subhead text-text">
          Protocol draft
        </h2>
        <p className="text-xs text-text-muted">
          Compiled from the moves you've accepted.
        </p>
      </div>

      <SlotMeter draft={draft} />

      {onFinish && (
        <Button
          size="sm"
          variant={complete ? "default" : "subtle"}
          data-agent="draft-finish"
          onClick={onFinish}
        >
          {complete ? "Finish & prepare protocol draft" : "Review protocol draft"}
        </Button>
      )}

      {onApply && (
        <Button
          size="sm"
          variant="subtle"
          disabled={!compileValid || applying}
          data-agent="draft-apply"
          onClick={onApply}
        >
          {applying ? "Applying…" : "Apply validated draft"}
        </Button>
      )}

      <div className="min-h-0 flex-1 overflow-auto rounded-input border border-border-strong bg-bg p-3">
        <pre className="tabular whitespace-pre-wrap font-mono text-xs leading-relaxed text-text">
          {body}
        </pre>
      </div>
    </aside>
  );
}
