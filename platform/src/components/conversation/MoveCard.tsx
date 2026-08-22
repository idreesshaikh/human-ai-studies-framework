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
  caution: "Caution",
};

/* A proposed design move with accept/reject, and an Undo once decided  -
 * reopens the card to "proposed" rather than flipping straight to the
 * opposite decision. Keyboard-first: a / r when the card is focused (undo
 * is click-only; a long-since-decided card isn't the one holding focus).
 * Accepted moves fold toward the draft rail; rejected ones fade out. A
 * caution has no patch, so accepting it just marks it noted  -  it never
 * changes the draft. */
export function MoveCard({
  move,
  onDecide,
  autoFocus = false,
}: {
  move: DesignMove;
  onDecide: (moveId: string, status: MoveStatus) => void;
  /** True only for the first undecided move of a reply the researcher just
   *  asked for (see ConversationView)  -  never on a page they merely opened. */
  autoFocus?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const isCaution = move.kind === "caution";
  // A non-caution move can still land here with no patch (e.g. the LLM
  // proposed a section the compiler doesn't recognize and it got dropped
  // at validation)  -  "in draft" would be a lie in that case, since neither
  // compiler folds a patch-less move into the draft.
  const compiled = Boolean(move.patch);
  const decided = move.status !== "proposed";
  /* Whether ANY citation stands behind this move. How strongly each one does
   * is carried by that citation's own printed score on its chip, so the card
   * needs the boolean and not the maximum. */
  const grounded = move.grounding.length > 0;

  const onKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (decided) return;
      if (e.key === "a") onDecide(move.moveId, "accepted");
      if (e.key === "r") onDecide(move.moveId, "rejected");
    },
    [decided, move.moveId, onDecide],
  );

  /* The caret goes to this card only when it answers something the researcher
   * just sent. `a` and `r` decide a design move from one unmodified keystroke,
   * so a card that takes focus on a page they merely opened arms a decision on
   * a proposal they have not read  -  the human decides, and they cannot decide
   * what they have not been shown. The thread's own scroll-to-end brings a new
   * reply into view either way. */
  useEffect(() => {
    if (autoFocus && !decided) ref.current?.focus();
  }, [autoFocus, decided]);

  return (
    <Card
      ref={ref}
      askew
      data-agent="move-card"
      data-agent-kind={move.kind}
      data-agent-status={move.status}
      tabIndex={decided ? -1 : 0}
      onKeyDown={onKey}
      aria-label={`${KIND_LABEL[move.kind]} move: ${move.proposal}`}
      className={cn(
        "relative transition-all",
      /* A proposed move is a compact decision sheet: it has enough framing to
         * separate a protocol choice from the conversation, without becoming a
         * second giant assistant message. Accepted and rejected moves remain
         * readable because nothing here is ever erased. */
        move.status === "proposed" && "sheet-land",
        move.status === "accepted" && "duration-settle ease-sheet",
        move.status === "rejected" && "duration-standard",
        /* No citation, no score: an undecided unsourced move wears the
         * open ring's dashed outline until the researcher rules on it. */
        !grounded && !decided && "held-back",
      )}
    >
      {/* No card-level score. Its strength IS the strength of the citation
        * behind it, and the grounding chip below already prints that
        * citation's own score: the card was stating the same value twice,
        * once floating in the top-right corner where it read as a
        * notification dot rather than as evidence. The score belongs beside
        * the source it measures. */}
      <CardContent className="flex flex-col gap-1.5 p-2">
        <div className="min-w-0">
          <div
            className={cn(
              "flex flex-col gap-1.5",
              move.status === "accepted" && "opacity-70",
              move.status === "rejected" && "opacity-60",
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
                  move.kind === "merge-templates" || compiled ? "text-grounded" : "text-text-muted",
                )}
              >
                {move.kind === "merge-templates" || compiled ? "merged" : "noted"}
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

        {/* Outside the faded wrapper above, deliberately: CSS opacity always
         * applies to every descendant, including a popover positioned
         * absolutely outside its parent's box  -  a citation's hover card would
         * inherit the card's 40/60% fade and render see-through, which is
         * worse than not fading it. Citations stay fully legible regardless
         * of the card's decided state, same reasoning as the Undo button. */}
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
                data-agent="move-accept"
                className="!h-8 !px-2.5"
                onClick={() => onDecide(move.moveId, "accepted")}
              >
                <Check aria-hidden />
                {isCaution ? "Note it" : "Accept"}
                {/* Drawn as a key cap, the same one the command hint in
                  * ProjectSwitcher wears. As a bare dimmed letter butted
                  * against the label it read as part of the sentence  -
                  * "Note it a…" had a reviewer asking "note it as what?" */}
                <kbd className="type-legend ml-1 hidden rounded-chip border border-border px-1.5 py-0.5 text-text-muted sm:inline">a</kbd>
              </Button>
              <Button
                size="sm"
                variant="ghost"
                data-agent="move-reject"
                className="!h-8 !px-2.5"
                onClick={() => onDecide(move.moveId, "rejected")}
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
                data-agent="move-undo"
                className="!h-8 !px-2.5"
                onClick={() => onDecide(move.moveId, "proposed")}
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
