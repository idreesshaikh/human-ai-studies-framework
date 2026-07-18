import { MoveCard } from "./MoveCard";
import { RecommendationCard } from "./RecommendationCard";
import { cn } from "@/lib/cn";
import type { Turn } from "@/lib/types";

/* A single conversation turn: the prose, then any design moves and paper
 * recommendations it carries. There's no token streaming yet (the assistant
 * responds synchronously) — an entrance animation stands in, and it's gone
 * under reduce-motion with nothing lost. */
export function StreamingTurn({
  turn,
  addedRefs,
  onDecide,
  onAddPaper,
}: {
  turn: Turn;
  addedRefs: Set<string>;
  onDecide: (moveId: string, status: "accepted" | "rejected") => void;
  onAddPaper: (ref: string) => void;
}) {
  const isPlatform = turn.role === "platform";
  return (
    <div
      className={cn(
        "flex flex-col gap-3",
        isPlatform ? "items-start" : "items-end",
      )}
    >
      <div
        className={cn(
          "max-w-[46ch] rounded-card px-4 py-3 text-sm animate-in fade-in duration-entrance",
          isPlatform
            ? "bg-surface border border-border text-text"
            : "bg-accent text-accent-contrast",
        )}
      >
        <span className="mb-1 block text-xs opacity-70">{turn.author}</span>
        {turn.text}
      </div>

      {turn.moves.length > 0 && (
        <div className="flex w-full max-w-[46ch] flex-col gap-2">
          {turn.moves.map((m) => (
            <MoveCard key={m.moveId} move={m} onDecide={onDecide} />
          ))}
        </div>
      )}

      {turn.recommendations.length > 0 && (
        <div className="grid w-full max-w-[46ch] gap-2 sm:grid-cols-2">
          {turn.recommendations.map((r) => (
            <RecommendationCard
              key={r.ref}
              rec={r}
              added={addedRefs.has(r.ref)}
              onAdd={onAddPaper}
            />
          ))}
        </div>
      )}
    </div>
  );
}
