import { useMemo } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, Check } from "lucide-react";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { SLOT_LABELS, type DesignMove } from "@/lib/types";
import { rowLabel } from "@/lib/slotRowLabels";
import type { CompileResult } from "@/lib/conversationApi";
import { BlinkComparator } from "./BlinkComparator";
import { hasEarlierVersion } from "@/lib/comparator";
import { cleanProposalText } from "@/lib/uiText";

/* A YAML line whose whole value is an empty collection ("gates: []"): an unresolved slot
* the "Still unresolved" line already names, so it is dropped. */
const EMPTY_COLLECTION = /^\s*[\w.]+:\s*(\{\}|\[\])\s*$/;

/* Splits the server's unified diff into per-line pieces so each can be coloured. File headers,
* empty-collection placeholders and raw `@@` hunk headers become a plain divider or are dropped. */
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

/* Gathers what the conversation produced (accepted moves, grounding, compiled protocol) into one review. */
export function FinishReview({
  open,
  onOpenChange,
  moves,
  earlierMoves = [],
  compile,
  compiling,
  applying,
  applyError,
  applied,
  onApply,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  moves: DesignMove[];
  earlierMoves?: DesignMove[];
  compile: CompileResult | null;
  compiling: boolean;
  applying: boolean;
  applyError: string | null;
  applied: boolean;
  onApply: () => void;
}) {
  const accepted = useMemo(
    () => moves.filter((m) => m.status === "accepted"),
    [moves],
  );
  const grounded = accepted.filter((m) => m.grounding.length > 0).length;
  const judgment = accepted.length - grounded;
  const earlierSourced = earlierMoves.filter(
    (move) => move.status === "accepted" && move.grounding.length > 0,
  );
  const valid = compile?.valid ?? false;
  const warnings = compile?.warnings ?? [];
  const diffLines = useMemo(
    () => (compile?.diff ? parseDiffLines(compile.diff) : []),
    [compile?.diff],
  );
  const hasDiff = diffLines.some((d) => d.kind === "add" || d.kind === "remove");
  /* Something existed before this compile, so the two plates genuinely differ. Shared with the
  * comparator (lib/comparator.ts) so the dialog and the component agree on the first-version case. */
  const earlier = hasEarlierVersion(diffLines);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent wide>
        <DialogHeader>
          <DialogTitle>Review draft</DialogTitle>
          <DialogDescription>
            Check the draft, then apply it as the study's protocol.
          </DialogDescription>
        </DialogHeader>
        {applyError && <Notice kind="problem" className="mx-gutter mt-2">{applyError}</Notice>}
        <DialogBody>

        {/* One summary line, not three hero-metric cells. */}
        <p className="type-body text-text-muted">
          <span className="type-quantity text-text">{accepted.length}</span>{" "}
          {accepted.length === 1 ? "decision" : "decisions"} accepted:{" "}
          <span className="type-quantity text-text">{grounded}</span> with linked
          sources, <span className="type-quantity text-text">{judgment}</span> without
          linked sources.
        </p>
        {accepted.length > 0 && (
          <p className="mt-1 type-note text-text-muted">
            Only sources linked to a decision are counted. Papers in Literature
            are listed separately.
          </p>
        )}
        {earlierSourced.length > 0 && (
          <details className="mt-3 type-note text-text-muted">
            <summary className="cursor-pointer rounded-control text-text">
              Earlier sourced decisions ({earlierSourced.length})
            </summary>
            <p className="mt-2">
              These decisions preceded the current plan replacement. Their
              sources are not counted as support for the current decisions.
            </p>
            <ul className="mt-2 flex flex-col gap-2">
              {earlierSourced.map((move) => (
                <li key={move.moveId} className="break-words">
                  <span className="text-text">{cleanProposalText(move.proposal)}</span>
                  <span className="block">{move.grounding.map((source) => source.title || source.ref).join("; ")}</span>
                </li>
              ))}
            </ul>
          </details>
        )}

        {accepted.length > 0 && (
          <ul className="mt-3 rounded-input border border-border bg-surface">
            {accepted.map((m) => (
              <li
                key={m.moveId}
                className="flex items-start gap-2 border-b border-border px-3 py-2 type-body last:border-0"
              >
                <span className="mt-0.5 w-32 shrink-0 type-caption text-text-muted">
                  {/* Plain-words label, never the raw dotted path; a fixed width keeps every row's proposal text aligned. */}
                  {rowLabel(m.target)}
                </span>
                <span className="min-w-0 flex-1 break-words text-text">{cleanProposalText(m.proposal)}</span>
                {m.grounding.length > 0 ? (
                  <span className="shrink-0 type-caption text-grounded" title="source linked to this decision">
                    cited
                  </span>
                ) : (
                  <span className="shrink-0 type-caption text-unsourced" title="no source linked to this decision">
                    no linked source
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}

        <div className="mt-3">
          <p className="mb-1 type-caption font-medium text-text-muted">
            Compiled protocol {compiling ? "· checking latest draft" : valid ? "· validated" : "· not yet valid"}
          </p>
          <pre className="tabular whitespace-pre-wrap break-words rounded-input border border-border-strong bg-bg p-3 type-quantity text-text">
            {compile?.yaml?.trim() ||
              (accepted.length > 0
                ? "The server couldn't compile this draft. Check your connection, then reopen this review."
                : "The draft is still empty. Accept a few design moves first.")}
          </pre>
          {/* The comparator earns its place only once there is an earlier version to alternate against. */}
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
          {compile && warnings.length > 0 && (
            <Notice kind="note" className="mt-1.5">
              <p className="font-medium">
                What the compiler added or changed in your draft:
              </p>
              <ul className="mt-1 flex list-disc flex-col gap-1.5 pl-4">
                {warnings.map((w, i) => (
                  <li key={i} className="max-w-reading break-words leading-snug [overflow-wrap:anywhere]">{w.charAt(0).toUpperCase() + w.slice(1)}</li>
                ))}
              </ul>
            </Notice>
          )}
          {compile && !valid && compile.unresolved.length > 0 && (
            <p className="mt-1.5 rounded-input border border-border bg-surface p-2 type-note text-text-muted">
              <span className="font-medium text-text">Still unresolved:</span>{" "}
              {compile.unresolved
                .map((s) => SLOT_LABELS[s as keyof typeof SLOT_LABELS] ?? s)
                .join(", ")}
              . You can keep talking to fill these.
            </p>
          )}
        </div>

        {/* Pinned to the foot of the dialog's scroller so the action row stays visible when the dialog is taller than the viewport. */}
        </DialogBody>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={applying}
          >
            Keep editing
          </Button>
          {/* Once applied, the pinned primary action becomes the next step: sample-size planning. */}
          {applied ? (
            <Button size="sm" asChild>
              <Link to="?tab=planning" onClick={() => onOpenChange(false)}>
                <Check aria-hidden /> Applied. Plan recruitment
                <ArrowRight aria-hidden />
              </Link>
            </Button>
          ) : (
            <Button size="sm" onClick={onApply} disabled={!valid || compiling || applying}>
              {applying ? "Applying…" : "Apply protocol"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
