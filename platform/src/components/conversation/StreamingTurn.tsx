import { Check, CloudOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MoveCard } from "./MoveCard";
import { cn } from "@/lib/cn";
import type { MoveStatus, Turn } from "@/lib/types";

/* A single conversation turn: the prose, then any design moves it carries.
 * Paper recommendations live in the persistent recommender rail (one mental
 * model), not inline here. Platform prose stays lightweight and conversational;
 * only an actual design decision earns a framed working sheet. The reply's
 * prose streams in above this (see ConversationView); a turn's own entrance is
 * one settle, gone under reduce-motion with nothing lost. */
export function StreamingTurn({
  turn,
  onDecide,
  onAcceptBatch,
  focusMoveId = null,
  active = false,
}: {
  turn: Turn;
  onDecide: (moveId: string, status: MoveStatus, move?: Turn["moves"][number]) => void;
  onAcceptBatch?: (moves: Turn["moves"]) => void;
  /** The one move the thread is handing the caret to, if any  -  set only when
   *  a reply lands in answer to something the researcher just sent. */
  focusMoveId?: string | null;
  /** Only the active reply gets full prose treatment. Older turns are compact
   * history rows so the workspace remains a decision surface. */
  active?: boolean;
}) {
  const isPlatform = turn.role === "platform";
  const isUnavailable = turn.source === "unavailable";
  const isScope = turn.source === "scope";
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-3",
        isPlatform ? "items-start" : "items-end")}
    >
      {turn.text && <div
        className={cn(
          "type-body-lg",
          isPlatform
            ? "w-full py-1 text-text"
            : "max-w-bubble rounded-card bg-zone-9 px-4 py-3 text-text",
          /* A holding turn is not the conversation  -  the model could not be
           * reached, so it proposes nothing and cites nothing. It reads as a
           * notice rather than a reply, because mistaking one for the other
           * is the whole failure the keyword assistant used to cause. */
          isUnavailable && "border-dashed bg-transparent text-text-muted")}
      >
        {isPlatform && (
          <span className="mb-2 flex items-center gap-1 type-caption text-text-muted">
            {isUnavailable ? "Not answered" : isScope ? "Supported scope" : "Assistant"}
            {isUnavailable && (
              <CloudOff
                className="size-3"
                aria-hidden
              />
            )}
          </span>
        )}
        {isPlatform ? (
          <ReplyParagraphs text={turn.text} />
        ) : (
          <p className="whitespace-pre-wrap">{turn.text}</p>
        )}
      </div>}

      {turn.moves.length > 0 && (
        <div className="flex w-full min-w-0 flex-col gap-2">
          {onAcceptBatch && turn.moves.filter((m) => m.status === "proposed" && m.kind !== "caution").length > 1 && (
            <div className="flex items-center justify-between gap-3 rounded-card border border-accent/30 bg-accent/5 px-3 py-2">
              <p className="type-caption text-text-muted">
                Suggested protocol changes
              </p>
              <Button
                size="sm"
                variant="subtle"
                className="shrink-0 !h-8 !px-2.5"
                onClick={() => onAcceptBatch(turn.moves.filter((m) => m.status === "proposed" && m.kind !== "caution"))}
              >
                <Check aria-hidden />
                Accept all
              </Button>
            </div>
          )}
          {turn.moves.filter(move => !active || move.status === "proposed").map((m) => (
            <MoveCard
              key={m.moveId}
              move={m}
              onDecide={onDecide}
              /* At most one card takes focus, and only for a reply the
               * researcher asked for. Every card claiming it meant the last
               * one won, so a page load scrolled past the proposals it was
               * meant to show and armed a / r on an unread card. */
              autoFocus={m.moveId === focusMoveId}
            />
          ))}
          {active && turn.moves.some(move => move.status !== "proposed") && (
            <details className="mt-2">
              <summary className="type-caption cursor-pointer text-text-muted">
                View recorded decisions ({turn.moves.filter(move => move.status !== "proposed").length})
              </summary>
              <div className="mt-2 flex flex-col gap-2">
                {turn.moves.filter(move => move.status !== "proposed").map(move => (
                  <MoveCard key={move.moveId} move={move} onDecide={onDecide} />
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

function ReplyParagraphs({ text }: { text: string }) {
  const blocks = text
    .split(/\n{2,}/)
    .flatMap((block) => {
      const sentences = block.trim().split(/(?<=[.!?])\s+(?=[A-Z0-9“])/);
      if (sentences.length < 4) return [block.trim()];
      const chunks: string[] = [];
      for (let i = 0; i < sentences.length; i += 2) {
        chunks.push(sentences.slice(i, i + 2).join(" "));
      }
      return chunks;
    })
    .filter(Boolean);

  return (
    <div className="flex flex-col gap-2.5">
      {blocks.map((block, index) => (
        <p key={`${index}-${block.slice(0, 12)}`}>
          {block.split(/(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g).map((part, i) =>
            /^\*\*[^*\n]+\*\*$/.test(part) ? <strong key={i}>{part.slice(2, -2)}</strong> :
            /^\*[^*\n]+\*$/.test(part) ? <em key={i}>{part.slice(1, -1)}</em> :
            /^`[^`\n]+`$/.test(part) ? <code key={i}>{part.slice(1, -1)}</code> : part,
          )}
        </p>
      ))}
    </div>
  );
}
