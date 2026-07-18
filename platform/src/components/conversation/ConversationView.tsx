import { useMemo, useRef, useState } from "react";
import { Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StreamingTurn } from "./StreamingTurn";
import { DraftRail } from "./DraftRail";
import { compileAll } from "@/lib/compiler";
import { openingTurn, respondTo } from "@/lib/designStub";
import type { DesignMove, Turn } from "@/lib/types";

/* The design conversation — the main surface. The draft rail beside it is a
 * review view this produces. Runs entirely client-side on the deterministic
 * assistant, so it works with no backend and no LLM key; the backend swaps
 * in later behind the same shapes. */
export function ConversationView() {
  const [turns, setTurns] = useState<Turn[]>(() => [openingTurn()]);
  const [input, setInput] = useState("");
  const [addedRefs, setAddedRefs] = useState<Set<string>>(new Set());
  const threadEnd = useRef<HTMLDivElement>(null);

  // The draft is recompiled from every move's current status, so rejecting
  // a move simply re-folds without it.
  const allMoves: DesignMove[] = useMemo(
    () => turns.flatMap((t) => t.moves),
    [turns],
  );
  const draft = useMemo(() => compileAll(allMoves), [allMoves]);

  function send() {
    const text = input.trim();
    if (!text) return;
    const researcherTurn: Turn = {
      turnId: `r-${turns.length}`,
      role: "researcher",
      author: "You",
      text,
      moves: [],
      recommendations: [],
    };
    const reply = respondTo(text);
    setTurns((prev) => [...prev, researcherTurn, reply]);
    setInput("");
    queueMicrotask(() =>
      threadEnd.current?.scrollIntoView({ block: "end" }),
    );
  }

  function decide(moveId: string, status: "accepted" | "rejected") {
    setTurns((prev) =>
      prev.map((t) => ({
        ...t,
        moves: t.moves.map((m) =>
          m.moveId === moveId ? { ...m, status } : m,
        ),
      })),
    );
  }

  function addPaper(ref: string) {
    setAddedRefs((prev) => new Set(prev).add(ref));
  }

  return (
    <div className="grid h-full grid-cols-1 lg:grid-cols-[1fr_380px]">
      <section className="flex h-full min-h-0 flex-col">
        <div className="min-h-0 flex-1 space-y-6 overflow-auto p-6">
          {turns.map((t) => (
            <StreamingTurn
              key={t.turnId}
              turn={t}
              addedRefs={addedRefs}
              onDecide={decide}
              onAddPaper={addPaper}
            />
          ))}
          <div ref={threadEnd} />
        </div>

        <form
          className="flex items-end gap-2 border-t border-border bg-surface p-4"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <textarea
            className="min-h-11 flex-1 resize-none rounded-input border border-border-strong bg-bg px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
            placeholder="Describe what you want to find out…"
            value={input}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            aria-label="Message the design assistant"
          />
          <Button type="submit" size="icon" aria-label="Send">
            <Send aria-hidden />
          </Button>
        </form>
      </section>

      <DraftRail draft={draft} />
    </div>
  );
}
