import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, FlaskConical } from "lucide-react";
import { studyApi, type Prescription } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The prescription table (FR-TPL-6, NFR-8): for each design shape, the exact
 * test, effect size, correction, and sample-size guidance — each with its
 * plain-language rationale, never a bare test name. This is the reassurance a
 * researcher needs before collecting data: the statistical formulation they
 * most fear getting wrong, made explicit and honest. Deterministic, LLM-free.
 *
 * Nice-to-read labels for the design shapes; the server is the source of the
 * rows themselves. */
const SHAPE_LABEL: Record<string, string> = {
  "two-group": "Two independent groups",
  paired: "Paired / within-subjects",
  "multi-group": "Three or more groups",
  "multi-factorial": "Factorial (2+ factors)",
  "repeated-measures": "Repeated measures",
  proportion: "Proportions (2×2)",
  correlation: "Correlation",
  "single-arm": "Single arm (descriptive)",
};

export function PrescriptionPanel() {
  const [rows, setRows] = useState<Prescription[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    studyApi.prescriptions().then((r) => live && setRows(r));
    return () => {
      live = false;
    };
  }, []);

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="flex items-center gap-2 text-sm font-medium text-text">
          <FlaskConical className="size-4 text-text-muted" aria-hidden />
          What analysis your design calls for
        </h2>
        <p className="mt-1 text-xs text-text-muted">
          The exact test, effect size, and correction for each design shape — with the reasoning.
          Honest by construction: effect sizes and per-cell n, never a bare p-value.
        </p>
      </div>

      {rows === null ? (
        <p className="text-sm text-text-muted">Loading…</p>
      ) : (
        <div className="overflow-hidden rounded-card border border-border bg-surface">
          <ul>
            {rows.map((p, i) => {
              const isOpen = open === p.designShape;
              return (
                <li key={p.designShape} className={cn(i > 0 && "border-t border-border")}>
                  <button
                    className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-surface-raised/50"
                    onClick={() => setOpen(isOpen ? null : p.designShape)}
                    aria-expanded={isOpen}
                  >
                    {isOpen ? (
                      <ChevronDown className="size-4 shrink-0 text-text-muted" aria-hidden />
                    ) : (
                      <ChevronRight className="size-4 shrink-0 text-text-muted" aria-hidden />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium text-text">
                        {SHAPE_LABEL[p.designShape] ?? p.designShape}
                      </span>
                      <span className="block truncate text-xs text-text-muted">{p.test}</span>
                    </span>
                  </button>
                  {isOpen && (
                    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 border-t border-border bg-bg px-4 py-3 text-sm sm:grid-cols-[10rem_1fr]">
                      <Row label="Test" value={p.test} />
                      <Row label="Effect size" value={p.effectSize} />
                      <Row label="Correction" value={p.correction} />
                      <Row label="Sample size" value={p.sampleSizeGuidance} />
                      <Row label="Why" value={p.rationale} muted />
                    </dl>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}

function Row({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <>
      <dt className="font-mono text-xs uppercase tracking-wide text-text-muted">{label}</dt>
      <dd className={cn("mb-1 sm:mb-0", muted ? "text-text-muted" : "text-text")}>{value}</dd>
    </>
  );
}
