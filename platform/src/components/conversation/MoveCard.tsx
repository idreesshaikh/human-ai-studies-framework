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
  "set-field": "Field",
  "declare-task": "Task",
  "add-instrument": "Instrument",
  "reconfigure-instrument": "Instrument setting",
  "add-measure": "Measure",
  "merge-templates": "Design merge",
  "prescribe-statistics": "Analysis plan",
  caution: "Caution",
};

export function MoveCard({
  move,
  onDecide,
  autoFocus = false,
}: {
  move: DesignMove;
  onDecide: (moveId: string, status: MoveStatus, move?: DesignMove) => void;

  autoFocus?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const isCaution = move.kind === "caution";

  const compiled = Boolean(move.patch);
  const decided = move.status !== "proposed";
  const isMergedResearchQuestion =
    move.kind === "add-rq" && move.status === "accepted" && compiled;

  const grounded = move.grounding.length > 0;

  const onKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (decided) return;
      if (e.key === "a") onDecide(move.moveId, "accepted", move);
      if (e.key === "r") onDecide(move.moveId, "rejected", move);
    },
    [decided, move.moveId, onDecide],
  );

  useEffect(() => {
    if (autoFocus && !decided) ref.current?.focus();
  }, [autoFocus, decided]);

  return (
    <Card
      ref={ref}
      askew
      tabIndex={decided ? -1 : 0}
      onKeyDown={onKey}
      aria-label={`${KIND_LABEL[move.kind]} move: ${move.proposal}`}
      className={cn(
        "relative transition-all",

        move.status === "proposed" && "sheet-land",
        move.status === "accepted" && "duration-settle ease-sheet",
        move.status === "rejected" && "duration-standard",
        isMergedResearchQuestion && "move-card-merged",

        !grounded && !decided && "held-back",
      )}
    >

      <CardContent className="flex flex-col gap-1.5 p-2">
        <div className="min-w-0">
          <div
            className={cn(
              "flex flex-col gap-1.5",
            )}
          >
          <div className="flex items-center gap-2">
            <span className="type-legend text-text-muted">
              {KIND_LABEL[move.kind]}
            </span>
            {move.status === "accepted" && (
              <span
                className={cn(
                  "type-legend",
                  move.kind === "merge-templates" || isCaution ? "text-grounded" : "text-text-muted",
                )}
              >
                {move.kind === "merge-templates"
                  ? "merged"
                  : isCaution
                    ? "noted"
                    : "accepted"}
              </span>
            )}
            {move.status === "rejected" && (
              <span className="type-legend superseded">dismissed</span>
            )}
          </div>

          {move.kind === "merge-templates" && move.mergeData ? (
            <div className="flex flex-col gap-1.5">
              <p className="type-body leading-snug text-text">{move.proposal}</p>
              <p className="type-caption text-text-muted italic">{move.mergeData.reason}</p>
            </div>
          ) : (
            <p
              className={cn(
                "type-body pr-3 leading-snug text-text",
                move.status === "rejected" && "superseded",
              )}
            >
              {move.proposal}
            </p>
          )}
        </div>

        <div className="mt-1 flex min-w-0 flex-wrap items-start gap-1 border-t border-border pt-1">
          {move.grounding.length > 0 ? (
            move.grounding.map((g) => <GroundingChip key={g.ref} g={g} />)
          ) : (
            <UnsourcedLabel />
          )}
        </div>

        </div>

        <div className="flex flex-wrap items-center gap-1.5 border-t border-border pt-1 sm:justify-end">
          {!decided && (
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="subtle"
                className="!h-8 !px-2.5"
                onClick={() => onDecide(move.moveId, "accepted", move)}
              >
                <Check aria-hidden />
                {isCaution ? "Note it" : "Accept"}

                <kbd className="type-legend ml-1 hidden rounded-chip border border-border px-1.5 py-0.5 text-text-muted sm:inline">a</kbd>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="!h-8 !px-2.5"
                onClick={() => onDecide(move.moveId, "rejected", move)}
              >
                <X aria-hidden />
                Reject<kbd className="type-legend ml-1 hidden rounded-chip border border-border px-1.5 py-0.5 text-text-muted sm:inline">r</kbd>
              </Button>
            </div>
          )}

          {decided && (
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="ghost"
                className="!h-8 !px-2.5"
                onClick={() => onDecide(move.moveId, "proposed", move)}
              >
                <Undo2 aria-hidden />
                Undo
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
