import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { MoveCard } from "./MoveCard";
import { cn } from "@/lib/cn";
import type { MoveStatus, Turn } from "@/lib/types";

/* A saved conversation turn and its study decisions. */
export function StreamingTurn({
  turn,
  onDecide,
  onAcceptBatch,
  onAnswer,
  focusMoveId = null,
  active = false,
  showKeyHint = false,
  queuedCount = 0,
}: {
  turn: Turn;
  onDecide?: (moveId: string, status: MoveStatus, move?: Turn["moves"][number]) => void;
  onAcceptBatch?: (moves: Turn["moves"]) => void;
  /** Sends one of a question's answer options as the researcher's reply;
   *  given only for the latest reply. */
  onAnswer?: (text: string) => void;
  /** The one move the thread is handing the caret to, if any  -  set only when
   *  a reply lands in answer to something the researcher just sent. */
  focusMoveId?: string | null;
  /** Only the active reply gets full prose treatment. Older turns are compact
   * history rows so the workspace remains a decision surface. */
  active?: boolean;
  /** Show the shortcut caption once, above the first pending card. */
  showKeyHint?: boolean;
  queuedCount?: number;
}) {
  const isPlatform = turn.role === "platform";
  const isUnavailable = turn.source === "unavailable";
  const isScope = turn.source === "scope";
  /* One click may accept what the researcher said, never what the assistant
   * chose for them: those cards wait for their own decision. */
  const pending = turn.moves.filter((m) => m.status === "proposed" && m.kind !== "caution");
  const batch = pending.filter((m) => !m.suggested?.length);
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-3",
        isPlatform ? "items-start" : "items-end")}
    >
      {turn.text && (isPlatform ? (
        <AssistantReply text={turn.text} label={isUnavailable ? "Not answered" : isScope ? "Supported scope" : "Assistant"} muted={isUnavailable} />
      ) : (
        <p className="type-body-lg max-w-bubble whitespace-pre-wrap rounded-card bg-zone-9 px-4 py-3 text-text [overflow-wrap:anywhere]">{turn.text}</p>
      ))}

      {isPlatform && turn.questions && turn.questions.length > 0 && (
        <div className="flex w-full flex-col gap-2">
          {turn.questions.map((q) => (
            <Card key={q.ask} className="border-accent/30 bg-accent/5">
              <CardContent className="flex flex-col gap-3 p-4">
                <p className="type-body-lg font-medium text-text [overflow-wrap:anywhere]">{q.ask}</p>
                {onAnswer && q.options.length > 0 && (
                  <div className="flex min-w-0 flex-col gap-2" role="group" aria-label={`Answers to: ${q.ask}`}>
                    {q.options.map((option) => (
                      <Button
                        key={option}
                        size="sm"
                        variant="ghost"
                        className="h-auto min-h-11 w-full justify-start border-border bg-surface px-3 py-2 text-left text-text shadow-none whitespace-normal hover:border-control-edge"
                        onClick={() => onAnswer(option)}
                      >
                        <span className="min-w-0 [overflow-wrap:anywhere]">{option}</span>
                      </Button>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {turn.moves.length > 0 && (
        <div className="flex w-full min-w-0 flex-col gap-2">
          {onAcceptBatch && batch.length > 1 && (
            <div className="flex items-center justify-between gap-3 rounded-card border border-accent/30 bg-accent/5 px-3 py-2">
              <p className="type-caption text-text-muted">
                Suggested protocol changes
              </p>
              <Button
                size="sm"
                variant="subtle"
                className="shrink-0 !h-8 !px-2.5"
                onClick={() => onAcceptBatch(batch)}
              >
                <Check aria-hidden />
                Accept both
              </Button>
            </div>
          )}
          {onDecide && showKeyHint && turn.moves.some((m) => m.status === "proposed") && <KeyHint />}
          {queuedCount > 0 && (
            <p className="type-caption text-text-muted" role="status">{queuedCount} more {queuedCount === 1 ? "decision" : "decisions"} waiting</p>
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
                Decisions ({turn.moves.filter(move => move.status !== "proposed").length})
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

/* Quiet caption, not a toolbar: the shortcuts act on the focused card. The
 * "?" is a real button so the same text is reachable by keyboard. */
function KeyHint() {
  const hint = "With a card focused: A accept, R reject, U undo.";
  return (
    <p className="flex items-center gap-2 type-caption text-text-muted">
      <span>A accept · R reject · U undo</span>
      <button
        type="button"
        className="inline-flex size-6 items-center justify-center rounded-chip border border-border type-caption text-text-muted hover:text-text"
        title={hint}
        aria-label={`Keyboard shortcuts. ${hint}`}
      >
        ?
      </button>
    </p>
  );
}

const BULLET_LINE = /^\s*[-*•]\s+(.*)$/;
const NUMBERED_LINE = /^\s*(\d+)[.)]\s+(.*)$/;
const HEADING_LINE = /^\s*#{1,6}\s+(.*)$/;
const FENCE_LINE = /^\s*```[^`]*$/;
const BLOCK_START = [FENCE_LINE, HEADING_LINE, BULLET_LINE, NUMBERED_LINE];

function Inline({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g).map((part, i) =>
        /^\*\*[^*\n]+\*\*$/.test(part) ? <strong key={i}>{part.slice(2, -2)}</strong> :
        /^\*[^*\n]+\*$/.test(part) ? <em key={i}>{part.slice(1, -1)}</em> :
        /^`[^`\n]+`$/.test(part) ? <code key={i}>{part.slice(1, -1)}</code> : part,
      )}
    </>
  );
}

// Keep the author's block order and line breaks. Reply text is rendered as
// React text and elements so HTML from the model stays inert.
function ReplyParagraphs({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let index = 0;
  while (index < lines.length) {
    const start = index;
    const line = lines[index++];
    if (!line.trim()) continue;
    if (FENCE_LINE.test(line)) {
      const code = [];
      while (index < lines.length && !FENCE_LINE.test(lines[index])) code.push(lines[index++]);
      if (index < lines.length) index++;
      blocks.push(<pre key={start} className="whitespace-pre-wrap rounded-control bg-zone-9 p-3 [overflow-wrap:anywhere]"><code>{code.join("\n")}</code></pre>);
      continue;
    }
    const heading = HEADING_LINE.exec(line);
    if (heading) {
      blocks.push(<h3 key={start} className="font-semibold"><Inline text={heading[1]} /></h3>);
      continue;
    }
    const numbered = NUMBERED_LINE.exec(line);
    if (numbered || BULLET_LINE.test(line)) {
      const pattern = numbered ? NUMBERED_LINE : BULLET_LINE;
      const items = [];
      let next = pattern.exec(line);
      let lineIndex = start;
      while (next) {
        items.push(<li key={lineIndex}><Inline text={numbered ? next[2] : next[1]} /></li>);
        next = pattern.exec(lines[++lineIndex] ?? "");
      }
      index = lineIndex;
      blocks.push(numbered ? (
        <ol key={start} start={Number(numbered[1])} className="list-decimal space-y-1 pl-5">{items}</ol>
      ) : (
        <ul key={start} className="list-disc space-y-1 pl-5">{items}</ul>
      ));
      continue;
    }
    const paragraph = [line];
    while (lines[index]?.trim() && !BLOCK_START.some((pattern) => pattern.test(lines[index]))) {
      paragraph.push(lines[index++]);
    }
    blocks.push(<p key={start} className="whitespace-pre-wrap"><Inline text={paragraph.join("\n")} /></p>);
  }

  return <div className="flex min-w-0 flex-col gap-3 [overflow-wrap:anywhere]">{blocks}</div>;
}

export function AssistantReply({ text, label = "Assistant", muted = false, streaming = false }: {
  text: string;
  label?: string;
  muted?: boolean;
  streaming?: boolean;
}) {
  return (
    <div className={cn("type-body-lg w-full min-w-0 py-1", muted ? "text-text-muted" : "text-text")}>
      <span className="mb-2 block type-caption text-text-muted" aria-hidden={streaming || undefined}>{label}</span>
      {text ? (
        <div aria-hidden={streaming || undefined}><ReplyParagraphs text={text} /></div>
      ) : (
        <p role="status" className="text-text-muted">Preparing reply…</p>
      )}
    </div>
  );
}
