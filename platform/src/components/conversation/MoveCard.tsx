import { useCallback, useEffect, useRef } from "react";
import { Check, X, Undo2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { GroundingChip } from "./GroundingChip";
import { UnsourcedLabel } from "./UnsourcedLabel";
import { cn } from "@/lib/cn";
import type { DesignMove, MoveStatus } from "@/lib/types";

const KIND_LABEL: Record<DesignMove["kind"], string> = {
  "add-rq": "Research question",
  "choose-template": "Design",
  "set-parameter": "Parameter",
  "add-instrument": "Instrument",
  "add-measure": "Measure",
  "set-threshold": "Threshold",
  caution: "Caution",
};

/* A proposed design move with accept/reject, and an Undo once decided —
 * reopens the card to "proposed" rather than flipping straight to the
 * opposite decision. Keyboard-first: a / r when the card is focused (undo
 * is click-only; a long-since-decided card isn't the one holding focus).
 * Accepted moves fold toward the draft rail; rejected ones fade out. A
 * caution has no patch, so accepting it just marks it noted — it never
 * changes the draft. */
export function MoveCard({
  move,
  onDecide,
}: {
  move: DesignMove;
  onDecide: (moveId: string, status: MoveStatus) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const isCaution = move.kind === "caution";
  // A non-caution move can still land here with no patch (e.g. the LLM
  // proposed a section the compiler doesn't recognize and it got dropped
  // at validation) — "in draft" would be a lie in that case, since neither
  // compiler folds a patch-less move into the draft.
  const compiled = Boolean(move.patch);
  const decided = move.status !== "proposed";

  const onKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (decided) return;
      if (e.key === "a") onDecide(move.moveId, "accepted");
      if (e.key === "r") onDecide(move.moveId, "rejected");
    },
    [decided, move.moveId, onDecide],
  );

  // Focus the card on appearance so a / r work right away.
  useEffect(() => {
    if (!decided) ref.current?.focus();
  }, [decided]);

  return (
    <Card
      ref={ref}
      data-agent="move-card"
      data-agent-kind={move.kind}
      data-agent-status={move.status}
      tabIndex={decided ? -1 : 0}
      onKeyDown={onKey}
      aria-label={`${KIND_LABEL[move.kind]} move: ${move.proposal}`}
      className={cn(
        "transition-all",
        move.status === "proposed" &&
          "animate-in fade-in slide-in-from-bottom-2 duration-entrance ease-out",
        move.status === "accepted" &&
          "duration-settle ease-in-out translate-x-2",
        move.status === "rejected" && "duration-standard scale-95",
      )}
    >
      <CardContent className="flex flex-col gap-2 p-3">
        <div
          className={cn(
            "flex flex-col gap-2",
            move.status === "accepted" && "opacity-60",
            move.status === "rejected" && "opacity-40",
          )}
        >
          <div className="flex items-center gap-2">
            <span className="type-eyebrow text-text-muted">
              {KIND_LABEL[move.kind]}
            </span>
            {move.status === "accepted" && (
              <span
                className={cn(
                  "text-xs",
                  compiled ? "text-grounded" : "text-text-muted",
                )}
              >
                {compiled ? "in draft" : "noted"}
              </span>
            )}
            {move.status === "rejected" && (
              <span className="text-xs text-text-muted">dismissed</span>
            )}
          </div>

          <p className="text-sm text-text">{move.proposal}</p>
        </div>

        {/* Outside the faded wrapper above, deliberately: CSS opacity always
         * applies to every descendant, including a popover positioned
         * absolutely outside its parent's box — a citation's hover card would
         * inherit the card's 40/60% fade and render see-through, which is
         * worse than not fading it. Citations stay fully legible regardless
         * of the card's decided state, same reasoning as the Undo button. */}
        <div className="flex flex-wrap items-center gap-1">
          {move.grounding.length > 0 ? (
            move.grounding.map((g) => <GroundingChip key={g.ref} g={g} />)
          ) : (
            <UnsourcedLabel />
          )}
        </div>

        {!decided && (
          <div className="mt-1 flex gap-2">
            <Button
              size="sm"
              variant="subtle"
              data-agent="move-accept"
              className="min-h-9"
              onClick={() => onDecide(move.moveId, "accepted")}
            >
              <Check aria-hidden />
              {isCaution ? "Note it" : "Accept"} <kbd className="hidden sm:inline opacity-60">a</kbd>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              data-agent="move-reject"
              className="min-h-9"
              onClick={() => onDecide(move.moveId, "rejected")}
            >
              <X aria-hidden />
              Reject <kbd className="hidden sm:inline opacity-60">r</kbd>
            </Button>
          </div>
        )}

        {decided && (
          <div className="mt-1 flex gap-2">
            <Button
              size="sm"
              variant="ghost"
              data-agent="move-undo"
              className="min-h-9"
              onClick={() => onDecide(move.moveId, "proposed")}
            >
              <Undo2 aria-hidden />
              Undo
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
