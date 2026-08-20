import { useMemo } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, Check } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { SLOT_LABELS, targetLabel, type DesignMove } from "@/lib/types";
import type { CompileResult } from "@/lib/conversationApi";
import { BlinkComparator } from "./BlinkComparator";
import { hasEarlierVersion } from "@/lib/comparator";

/* A YAML-scalar line whose entire value is an empty collection, e.g.
 * "instruments: {}" or "  gates: []" — a still-unresolved slot rendered as
 * flow-style by the YAML dumper (empty mappings/sequences have no block
 * form). It carries no information the "Still unresolved" line below
 * doesn't already say in plain words, so it's dropped rather than shown
 * as bare braces. */
const EMPTY_COLLECTION = /^\s*[\w.]+:\s*(\{\}|\[\])\s*$/;

/* Turns the server's unified diff (`---`/`+++`/`@@`/`+`/`-` lines) into
 * per-line pieces so each can be colored on its own — a flat <pre> string
 * can't do that. File-header lines are dropped ("draft-before"/"draft-after"
 * mean nothing to a researcher), as are empty-collection placeholder lines;
 * hunk headers become a plain divider instead of raw `@@ -0,0 +1,3 @@` diff
 * jargon. */
function parseDiffLines(diff: string) {
  return diff
    .split("\n")
    .filter((line) => line && !line.startsWith("---") && !line.startsWith("+++"))
    .filter((line) => {
      const marker = line[0];
      if (marker !== "+" && marker !== "-") return true;
      return !EMPTY_COLLECTION.test(line.slice(1));
    })
    .map((line) => {
      if (line.startsWith("@@")) return { line: "", kind: "hunk" as const };
      if (line.startsWith("+")) return { line, kind: "add" as const };
      if (line.startsWith("-")) return { line, kind: "remove" as const };
      return { line, kind: "context" as const };
    });
}

/* The "finish the conversation → here's your protocol" moment. When the
 * researcher wraps up, this gathers everything the conversation produced —
 * the design moves they accepted, how many are grounded in the literature,
 * and the compiled protocol — into one calm review before it becomes the
 * document of record. It's the payoff: talk became a study. */
export function FinishReview({
  open,
  onOpenChange,
  moves,
  compile,
  applying,
  applied,
  onApply,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  moves: DesignMove[];
  compile: CompileResult | null;
  applying: boolean;
  applied: boolean;
  onApply: () => void;
}) {
  const accepted = useMemo(
    () => moves.filter((m) => m.status === "accepted"),
    [moves],
  );
  const grounded = accepted.filter((m) => m.grounding.length > 0).length;
  const judgment = accepted.length - grounded;
  const valid = compile?.valid ?? false;
  const diffLines = useMemo(
    () => (compile?.diff ? parseDiffLines(compile.diff) : []),
    [compile?.diff],
  );
  const hasDiff = diffLines.some((d) => d.kind === "add" || d.kind === "remove");
  /* Something existed before this compile, so the two plates genuinely differ.
   * Shared with the comparator itself (lib/comparator.ts) so the dialog's
   * decision to show it and the component's own first-version branch can never
   * disagree; `verify-comparator.mjs` exercises both. */
  const earlier = hasEarlierVersion(diffLines);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogTitle>Prepare your protocol draft</DialogTitle>
        <DialogDescription>
          This is what your conversation became. Review it, then apply it to the
          protocol: the study's document of record.
        </DialogDescription>

        {/* One line, not three cells. Three big numbers over three small
          * labels is the hero-metric template, and it was the loudest thing in
          * a dialog whose actual subject is the protocol below it. The counts
          * still align and still compare, in the measurement voice, at the
          * weight a summary deserves. */}
        <p className="mt-3 type-body text-text-muted">
          <span className="type-quantity text-text">{accepted.length}</span>{" "}
          {accepted.length === 1 ? "move" : "moves"} accepted:{" "}
          <span className="type-quantity text-text">{grounded}</span> grounded in
          papers, <span className="type-quantity text-text">{judgment}</span> on
          your judgment.
        </p>

        {accepted.length > 0 && (
          <ul className="mt-3 max-h-48 overflow-auto rounded-input border border-border bg-surface">
            {accepted.map((m) => (
              <li
                key={m.moveId}
                className="flex items-start gap-2 border-b border-border px-3 py-2 type-body last:border-0"
              >
                <span className="mt-0.5 w-32 shrink-0 type-caption text-text-muted">
                  {/* The plain-words label, never the raw dotted path (see
                    * targetLabel: an earlier prompt version had the model
                    * literally echoing "protocol.design" as a real target,
                    * and even a well-formed path like "researchQuestions[]"
                    * is still code, not a name a researcher reads). A fixed
                    * width here — not just shrink-0 — is what makes every
                    * row's proposal text start at the same x position;
                    * without it "Design" and "Research questions" left each
                    * row's second column starting somewhere different. */}
                  {targetLabel(m.target)}
                </span>
                <span className="min-w-0 flex-1 text-text">{m.proposal}</span>
                {m.grounding.length > 0 ? (
                  <span className="shrink-0 type-caption text-grounded" title="grounded in the corpus">
                    cited
                  </span>
                ) : (
                  <span className="shrink-0 type-caption text-unsourced" title="your own judgment">
                    your call
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}

        <div className="mt-3">
          <p className="mb-1 type-caption font-medium text-text-muted">
            Compiled protocol {valid ? "· validated" : "· not yet valid"}
          </p>
          <pre className="tabular max-h-56 overflow-auto whitespace-pre-wrap rounded-input border border-border-strong bg-bg p-3 type-quantity text-text">
            {compile?.yaml?.trim() ||
              (accepted.length > 0
                ? "The server couldn't compile this draft. Check your connection, then reopen this review."
                : "The draft is still empty. Accept a few design moves first.")}
          </pre>
          {/* On a first compile the comparator's at-rest record is the same
            * document as the block above, line for line, so showing both
            * stacked two ~200-line monospace slabs in one dialog and marked
            * nothing as changed. The comparator earns its place only once
            * there is an earlier version to alternate against. */}
          {hasDiff && earlier && (
            <BlinkComparator lines={diffLines} className="mt-3" />
          )}
          {compile && !valid && compile.errors.length > 0 && (
            <ul className="mt-1.5 flex flex-col gap-1 rounded-control border border-critical/40 bg-well p-2">
              {compile.errors.map((e, i) => (
                <li key={i} className="flex items-start gap-1.5 type-caption text-critical">
                  <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
                  <span>{e}</span>
                </li>
              ))}
            </ul>
          )}
          {compile && (compile.warnings?.length ?? 0) > 0 && (
            <ul className="mt-1.5 flex flex-col gap-1">
              {compile.warnings!.map((w, i) => (
                <li key={i} className="type-caption text-text-muted">
                  {w}
                </li>
              ))}
            </ul>
          )}
          {compile && !valid && compile.unresolved.length > 0 && (
            <p className="mt-1.5 rounded-input border border-border bg-surface p-2 type-caption text-text-muted">
              <span className="font-medium text-text">Still unresolved:</span>{" "}
              {compile.unresolved
                .map((s) => SLOT_LABELS[s as keyof typeof SLOT_LABELS] ?? s)
                .join(", ")}
              . You can keep talking to fill these.
            </p>
          )}
        </div>

        {/* Pinned to the foot of the dialog's scroller. Measured at 1440x900
          * this dialog is taller than the viewport, and the action row sat
          * ~370px below the fold: the one thing the review exists to let the
          * researcher do was invisible when it opened. */}
        {/* Applying used to be the end of the road: the button read "Applied"
          * and the dialog just sat there, which had a reviewer asking "when
          * the proposal is complete, how do I continue?". The protocol is
          * only half the job — it still has to reach participants' editors —
          * so the next step is named here, where the question is asked. */}
        {applied && (
          <div
            data-agent="applied-next-step"
            className="mt-3 rounded-card border border-border bg-well p-3"
          >
            <p className="type-body text-text">
              The protocol is applied. Next: bring participants in.
            </p>
            <p className="type-caption mt-1 text-text-muted">
              Mint a link for each participant and their editor joins the study
              configured exactly the way you just designed it.
            </p>
            <Link
              to="?tab=enrollment"
              onClick={() => onOpenChange(false)}
              className="type-control mt-2 inline-flex items-center gap-1.5 rounded-control text-accent underline decoration-border underline-offset-4 hover:decoration-control-edge"
            >
              Go to Participants
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        )}

        <div className="sticky bottom-0 -mx-5 mt-3 flex items-center justify-end gap-2 border-t border-border bg-surface-raised px-5 py-3">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={applying}>
            Keep editing
          </Button>
          <Button onClick={onApply} disabled={!valid || applying || applied}>
            {applied ? (
              <>
                <Check aria-hidden /> Applied
              </>
            ) : applying ? (
              "Applying…"
            ) : (
              "Apply to protocol"
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
