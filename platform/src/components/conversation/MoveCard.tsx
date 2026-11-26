import { useCallback, useEffect, useRef } from "react";
import { Check, X, Undo2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { GroundingChip } from "./GroundingChip";
import { UnsourcedLabel } from "./UnsourcedLabel";
import { EvidenceDetails } from "./EvidenceDetails";
import { cn } from "@/lib/cn";
import { PLAN_FIELD_LABEL, cleanProposalText, moveEyebrow, moveStateLabel, planValueText } from "@/lib/uiText";
import { isPlanPatch, type DesignMove, type MoveStatus, type PlanPatch } from "@/lib/types";

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
  onDecide?: (moveId: string, status: MoveStatus, move?: DesignMove) => void;
  /** True only for the first undecided move of a reply the researcher just
   *  asked for (see ConversationView)  -  never on a page they merely opened. */
  autoFocus?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const isCaution = move.kind === "caution";
  const isPlanCard = move.kind === "set-plan";
  // A non-caution move can still land here with no patch (e.g. the LLM
  // proposed a section the compiler doesn't recognize and it got dropped
  // at validation)  -  "in draft" would be a lie in that case, since neither
  // compiler folds a patch-less move into the draft.
  const compiled = Boolean(move.patch);
  const decided = move.status !== "proposed";
  const eyebrow = moveEyebrow(move.kind, move.patch);
  const isMergedResearchQuestion =
    move.kind === "add-rq" && move.status === "accepted" && compiled;
  /* Which values on this card the researcher never stated. A researcher who
   * questions the plan needs to see which choices were not theirs, and why
   * the assistant made them, before accepting. */
  const suggestions = move.suggested;
  const chosen = suggestions?.length
    ? ` Chosen by the assistant: ${suggestions.map((s) => s.label).join(", ")}.`
    : "";
  /* Whether ANY citation stands behind this move. How strongly each one does
   * is carried by that citation's own printed score on its chip, so the card
   * needs the boolean and not the maximum. */

  const onKey = useCallback(
    (e: React.KeyboardEvent) => {
      if (!onDecide) return;
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
  const shouldFocus = Boolean(onDecide && autoFocus && !decided);
  useEffect(() => {
    if (shouldFocus) ref.current?.focus();
  }, [shouldFocus]);

  return (
    <Card
      ref={ref}
      role="group"
      tabIndex={onDecide && !decided ? 0 : undefined}
      data-move-id={move.moveId}
      onKeyDown={onKey}
      aria-label={`${eyebrow}: ${cleanProposalText(move.proposal)}.${chosen} ${move.status === "proposed" ? "Awaiting your decision" : moveStateLabel(move.status, move.kind)}`}
      className={cn(
        "relative transition-colors duration-fast",
      /* A proposed move is a compact decision sheet: it has enough framing to
         * separate a protocol choice from the conversation, without becoming a
         * second giant assistant message. Accepted and rejected moves remain
         * readable because nothing here is ever erased. */
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
          {/* A decided card recedes through its text tokens, not opacity:
            * fading the block took the muted eyebrow and status under
            * 4.5:1 (NFR-12). */}
          <div className="flex flex-col gap-1.5">
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

          {move.patch && isPlanPatch(move.patch) ? (
            <PlanRows patch={move.patch} status={move.status} />
          ) : move.kind === "merge-templates" && move.mergeData ? (
            <div className="flex flex-col gap-1.5">
              <p className="type-body leading-snug text-text">{cleanProposalText(move.proposal)}</p>
              <p className="type-note text-text-muted italic">{move.mergeData.reason}</p>
            </div>
          ) : (
            <p
              className={cn(
                "type-body pr-3 leading-snug",
                move.status === "rejected"
                  ? "superseded"
                  : move.status === "accepted"
                    ? "text-text-muted"
                    : "text-text",
              )}
            >
              {cleanProposalText(move.proposal)}
            </p>
          )}
          {suggestions && suggestions.length > 0 && (
            <div className="type-caption text-text-muted">
              <p className="text-text">Chosen by the assistant:</p>
              <ul className="mt-0.5 flex flex-col gap-0.5">
                {suggestions.map((s) => (
                  <li key={s.field}>
                    <span className="text-text">{s.label}</span>
                    {s.why && `: ${s.why}`}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {suggestions && suggestions.length === 0 && (
            <p className="type-caption text-text-muted">Based on what you said.</p>
          )}
        </div>

        {/* Citations stay fully legible regardless of the card's decided
         * state, same reasoning as the Undo button. Never fade an ancestor
         * here: opacity reaches every descendant, including a citation's
         * absolutely positioned hover card, which would render see-through.
         * A plan card without a citation says nothing: most plan values are
         * the researcher's own, and "Unsourced" on each read as a warning. */}
        {(move.grounding.length > 0 || !isPlanCard) && <div className="mt-1 flex min-w-0 flex-wrap items-start gap-1 border-t border-border pt-1">
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
        </div>}

        </div>

        {onDecide && move.status !== "superseded" && <div className="flex flex-wrap items-center gap-1.5 border-t border-border pt-1 sm:justify-end">
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
        </div>}
      </CardContent>
    </Card>
  );
}

/* What a plan card changes, one row per field: the proposed value, and the
 * decided value it replaces when there is one ("Now" while undecided, "Was"
 * once accepted; a rejected or replaced card changed nothing). */
function PlanRows({ patch, status }: { patch: PlanPatch; status: MoveStatus }) {
  const muted = status !== "proposed";
  const previous = status === "proposed" ? "Now" : status === "accepted" ? "Was" : null;
  return (
    <dl className="flex flex-col gap-2">
      {Object.entries(patch.plan).map(([field, value]) => {
        const now = planValueText(field, value, patch.names);
        const was = planValueText(field, patch.before[field], patch.names);
        const list = field === "researchQuestions" || (field === "measureIds" && now.length > 1);
        return (
          <div key={field} className="grid gap-0.5 sm:grid-cols-[8.5rem_1fr] sm:gap-3">
            <dt className="type-caption pt-0.5 text-text-muted">{PLAN_FIELD_LABEL[field] ?? field}</dt>
            <dd className={cn("type-body min-w-0 leading-snug [overflow-wrap:anywhere]", muted ? "text-text-muted" : "text-text")}>
              {list ? (
                <ol className={cn("flex flex-col gap-1", field === "researchQuestions" && "list-decimal pl-5")}>
                  {now.map((item, i) => <li key={i}>{item}</li>)}
                </ol>
              ) : (
                now.join(", ")
              )}
              {previous && was.length > 0 && (
                <span className="mt-0.5 block type-caption text-text-muted">
                  {previous}: {was.join(field === "researchQuestions" ? " · " : ", ")}
                </span>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
