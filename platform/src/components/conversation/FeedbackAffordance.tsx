import { useState } from "react";
import { MessageSquarePlus, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

/* Marking a turn as platform feedback. Warm register, a
 * subtle affordance under a researcher's turn — the platform grows its own SRS
 * from its users' conversations exactly as a study grows from its researcher's.
 *
 * Detection may *offer* the marking (a gentle nudge when a turn reads as
 * feedback), but marking is always the researcher's confirm — never auto-filed.
 * The confirm reveals a short note + a kind, so the finding lands with intent. */

const KINDS: { value: string; label: string }[] = [
  { value: "ux-defect", label: "Something's clunky" },
  { value: "template-gap", label: "Missing template / method" },
  { value: "unclassified", label: "Just a thought" },
];

export function FeedbackAffordance({
  suggested,
  marked,
  onMark,
}: {
  suggested: boolean;
  marked: boolean;
  onMark: (note: string, kind: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [kind, setKind] = useState(KINDS[0].value);

  if (marked) {
    return (
      <span
        data-agent="feedback-marked"
        className="inline-flex items-center gap-1 text-xs text-grounded"
      >
        <Check className="size-3" aria-hidden />
        Sent to platform findings
      </span>
    );
  }

  if (!open) {
    return (
      <Button
        size="sm"
        variant="ghost"
        data-agent="feedback-mark"
        onClick={() => setOpen(true)}
        className={cn(
          "text-xs text-text-muted min-h-9",
          // The detection nudge: a soft highlight when the turn reads as
          // feedback. Still just an offer — nothing files without the confirm.
          suggested && "text-accent")}
      >
        <MessageSquarePlus className="size-3" aria-hidden />
        {suggested ? "Sounds like feedback — flag it?" : "Flag for the platform"}
      </Button>
    );
  }

  return (
    <div
      data-agent="feedback-composer"
      className="flex w-full max-w-bubble flex-col gap-2 rounded-card border border-border bg-surface p-3"
    >
      <div className="flex flex-wrap gap-1">
        {KINDS.map((k) => (
          <button
            key={k.value}
            type="button"
            onClick={() => setKind(k.value)}
            className={cn(
              "rounded-chip border px-2 py-0.5 text-xs transition-colors duration-fast",
              kind === k.value
                ? "border-accent bg-accent-soft text-accent"
                : "border-border text-text-muted hover:text-text")}
          >
            {k.label}
          </button>
        ))}
      </div>
      <textarea
        rows={2}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="What would make this better? (optional)"
        aria-label="Feedback note"
        className="resize-none rounded-input border border-border-strong bg-bg px-2 py-1.5 text-sm text-text outline-none focus-visible:border-accent"
      />
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="subtle"
          data-agent="feedback-send"
          onClick={() => {
            onMark(note.trim(), kind);
            setOpen(false);
          }}
        >
          Send to platform findings
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
