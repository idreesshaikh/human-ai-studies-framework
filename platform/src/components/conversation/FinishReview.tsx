import { useMemo } from "react";
import { Check, FileText, Sparkles, ShieldCheck, AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { SLOT_LABELS, type DesignMove } from "@/lib/types";
import type { CompileResult } from "@/lib/conversationApi";

/* Turns the server's unified diff (`---`/`+++`/`@@`/`+`/`-` lines) into
 * per-line pieces so each can be colored on its own — a flat <pre> string
 * can't do that. File-header lines are dropped; "draft-before"/"draft-after"
 * mean nothing to a researcher. */
function parseDiffLines(diff: string) {
  return diff
    .split("\n")
    .filter((line) => line && !line.startsWith("---") && !line.startsWith("+++"))
    .map((line) => {
      if (line.startsWith("@@")) return { line, kind: "hunk" as const };
      if (line.startsWith("+")) return { line, kind: "add" as const };
      if (line.startsWith("-")) return { line, kind: "remove" as const };
      return { line, kind: "context" as const };
    });
}

const DIFF_LINE_CLASS: Record<string, string> = {
  hunk: "text-text-muted font-medium",
  add: "text-grounded",
  remove: "text-unsourced",
  context: "text-text-muted",
};

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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogTitle className="flex items-center gap-2">
          <FileText className="size-5 text-accent" aria-hidden />
          Prepare your protocol draft
        </DialogTitle>
        <DialogDescription>
          This is what your conversation became. Review it, then apply it to the
          protocol: the study's document of record.
        </DialogDescription>

        <div className="mt-2 grid grid-cols-3 gap-3">
          <Tally icon={<Check className="size-4" aria-hidden />} n={accepted.length} label="moves accepted" />
          <Tally icon={<Sparkles className="size-4" aria-hidden />} n={grounded} label="grounded in papers" />
          <Tally icon={<ShieldCheck className="size-4" aria-hidden />} n={judgment} label="your judgment" />
        </div>

        {accepted.length > 0 && (
          <ul className="mt-3 max-h-48 overflow-auto rounded-input border border-border bg-surface">
            {accepted.map((m) => (
              <li
                key={m.moveId}
                className="flex items-start gap-2 border-b border-border px-3 py-2 text-sm last:border-0"
              >
                <span className="mt-0.5 shrink-0 font-mono text-xs text-text-muted">
                  {m.target.replace(/\[\]$/, "")}
                </span>
                <span className="min-w-0 flex-1 text-text">{m.proposal}</span>
                {m.grounding.length > 0 ? (
                  <span className="shrink-0 text-xs text-grounded" title="grounded in the corpus">
                    cited
                  </span>
                ) : (
                  <span className="shrink-0 text-xs text-unsourced" title="your own judgment">
                    your call
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}

        <div className="mt-3">
          <p className="mb-1 text-xs font-medium text-text-muted">
            Compiled protocol {valid ? "· validated" : "· not yet valid"}
          </p>
          <pre className="tabular max-h-56 overflow-auto whitespace-pre-wrap rounded-input border border-border-strong bg-bg p-3 font-mono text-xs leading-relaxed text-text">
            {compile?.yaml?.trim() ||
              (accepted.length > 0
                ? "The server couldn't compile this draft. Check your connection, then reopen this review."
                : "The draft is still empty. Accept a few design moves first.")}
          </pre>
          {hasDiff && (
            <>
              <p className="mb-1 mt-2 text-xs font-medium text-text-muted">
                What this changes
              </p>
              <pre className="tabular max-h-56 overflow-auto whitespace-pre rounded-input border border-border-strong bg-bg p-3 font-mono text-xs leading-relaxed">
                {diffLines.map((d, i) => (
                  <div key={i} className={DIFF_LINE_CLASS[d.kind]}>
                    {d.line}
                  </div>
                ))}
              </pre>
            </>
          )}
          {compile && !valid && compile.errors.length > 0 && (
            <ul className="mt-1.5 flex flex-col gap-1 rounded-input border border-unsourced/40 bg-unsourced-soft/40 p-2">
              {compile.errors.map((e, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-unsourced">
                  <AlertTriangle className="mt-0.5 size-3 shrink-0" aria-hidden />
                  <span>{e}</span>
                </li>
              ))}
            </ul>
          )}
          {compile && (compile.warnings?.length ?? 0) > 0 && (
            <ul className="mt-1.5 flex flex-col gap-1">
              {compile.warnings!.map((w, i) => (
                <li key={i} className="text-xs text-text-muted">
                  {w}
                </li>
              ))}
            </ul>
          )}
          {compile && !valid && compile.unresolved.length > 0 && (
            <p className="mt-1.5 rounded-input border border-border bg-surface p-2 text-xs text-text-muted">
              <span className="font-medium text-text">Still unresolved:</span>{" "}
              {compile.unresolved
                .map((s) => SLOT_LABELS[s as keyof typeof SLOT_LABELS] ?? s)
                .join(", ")}
              . You can keep talking to fill these.
            </p>
          )}
        </div>

        <div className="mt-3 flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={applying}>
            Keep editing
          </Button>
          <Button onClick={onApply} disabled={!valid || applying || applied}>
            {applied ? "Applied ✓" : applying ? "Applying…" : "Apply to protocol"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function Tally({ icon, n, label }: { icon: React.ReactNode; n: number; label: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5 rounded-input border border-border bg-surface p-3 text-center">
      <span className="text-accent">{icon}</span>
      <span className="tabular text-xl font-medium text-text">{n}</span>
      <span className="text-xs text-text-muted">{label}</span>
    </div>
  );
}
