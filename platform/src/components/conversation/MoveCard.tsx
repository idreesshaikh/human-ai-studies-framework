import { useCallback, useEffect, useRef } from "react";
import { Check, X, Undo2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { GroundingChip } from "./GroundingChip";
import { UnsourcedLabel } from "./UnsourcedLabel";
import { EvidenceDetails } from "./EvidenceDetails";
import { cn } from "@/lib/cn";
import { cleanProposalText, moveEyebrow, moveStateLabel } from "@/lib/uiText";
import type { DesignMove, MoveStatus } from "@/lib/types";

/* A proposed design move with accept/reject, and an Undo once decided  -
 * reopens the card to "proposed" rather than flipping straight to the
 * opposite decision. Keyboard-first: a / r when the card is focused, u to undo.
 * Accepted moves fold toward the draft rail; rejected ones fade out. A
 * caution has no patch, so accepting it just marks it noted  -  it never
 * changes the draft. */
export function MoveCard({
  move,
  onDecide,
  autoFocus = false,
}: {
  move: DesignMove;
  onDecide: (moveId: string, status: MoveStatus, move?: DesignMove) => void;
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
  const eyebrow = moveEyebrow(move.kind, move.patch);
  const isMergedResearchQuestion =
    move.kind === "add-rq" && move.status === "accepted" && compiled;
  /* Whether ANY citation stands behind this move. How strongly each one does
   * is carried by that citation's own printed score on its chip, so the card
   * needs the boolean and not the maximum. */

  const onKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.target !== e.currentTarget || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || e.repeat || e.nativeEvent.isComposing) return;
      if (decided) {
        if (e.key !== "u") return;
        e.preventDefault();
        onDecide(move.moveId, "proposed", move);
        return;
      }
      if (e.key !== "a" && e.key !== "r") return;
      e.preventDefault();
      onDecide(move.moveId, e.key === "a" ? "accepted" : "rejected", move);
    },
    [decided, move, onDecide],
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
      tabIndex={decided ? -1 : 0}
      data-move-id={move.moveId}
      onKeyDown={onKey}
      aria-label={`${eyebrow}: ${cleanProposalText(move.proposal)}. ${move.status === "proposed" ? "Awaiting your decision" : moveStateLabel(move.status, move.kind)}`}
      className={cn(
        "relative transition-all",
      /* A proposed move is a compact decision sheet: it has enough framing to
         * separate a protocol choice from the conversation, without becoming a
         * second giant assistant message. Accepted and rejected moves remain
         * readable because nothing here is ever erased. */
        move.status === "accepted" && "duration-settle ease-sheet",
        move.status === "rejected" && "duration-standard",
        isMergedResearchQuestion && "move-card-merged",
        /* No citation, no score: an undecided unsourced move wears the
         * open ring's dashed outline until the researcher rules on it. */
      )}
    >
      {/* No card-level score. Its strength IS the strength of the citation
        * behind it, and the grounding chip below already prints that
        * citation's own score: the card was stating the same value twice,
        * once floating in the top-right corner where it read as a
        * notification dot rather than as evidence. The score belongs beside
        * the source it measures. */}
      <CardContent className="flex flex-col gap-3 p-4">
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
              {eyebrow}
            </span>
            {decided && (
              <span
                className={cn(
                  "type-legend",
                  move.kind === "merge-templates" || isCaution ? "text-grounded" : "text-text-muted",
                )}
              >
                {moveStateLabel(move.status, move.kind)}
              </span>
            )}
          </div>

          {move.kind === "merge-templates" && move.mergeData ? (
            <div className="flex flex-col gap-1.5">
              <p className="type-body leading-snug text-text">{cleanProposalText(move.proposal)}</p>
              <p className="type-caption text-text-muted italic">{move.mergeData.reason}</p>
            </div>
          ) : (
            <p
              className={cn(
                "type-body pr-3 leading-snug text-text",
                move.status === "rejected" && "superseded",
              )}
            >
              {cleanProposalText(move.proposal)}
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
            move.grounding.map((g) => g.evidence ? (
              <details key={g.ref} className="w-full">
                <summary className="type-caption cursor-pointer text-accent">Evidence and conditions · {g.evidence.mapVersion}</summary>
                <p className="mt-2 type-caption text-text-muted">{g.evidence.mapDescription}</p>
                <EvidenceDetails candidate={g.evidence.candidate} />
                <p className="mt-2 break-all type-caption text-text-muted">Map: {g.evidence.mapId} · {g.evidence.mapDigest}</p>
              </details>
            ) : <GroundingChip key={g.ref} g={g} />)
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
                {/* Drawn as a key cap, the same one the command hint in
                  * ProjectSwitcher wears. As a bare dimmed letter butted
                  * against the label it read as part of the sentence  -
                  * "Note it a…" had a reviewer asking "note it as what?" */}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="!h-8 !px-2.5"
                onClick={() => onDecide(move.moveId, "rejected", move)}
              >
                <X aria-hidden />
                Reject
              </Button>
            </div>
          )}

          {decided && (
            <div className="flex gap-2">
              <Button
                data-move-undo={move.moveId}
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
