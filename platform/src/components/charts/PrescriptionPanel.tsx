import { useState } from "react";
import { ChevronDown, ChevronRight, FlaskConical, Loader2 } from "lucide-react";
import { studyApi, type Prescription } from "@/lib/studyApi";
import { cn } from "@/lib/cn";
import { useAsync } from "@/lib/useAsync";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";

/* Analysis guidance comes from the study's recorded plan. */
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

export function PrescriptionPanel({ studyId }: { studyId: string }) {
  const { data: rows, error, reload } = useAsync<Prescription[]>(
    () => studyApi.prescriptions(studyId), [studyId],
  );
  const [open, setOpen] = useState<string | null>(null);

  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="type-subhead flex items-center gap-2 text-text">
          <FlaskConical className="size-4 text-text-muted" aria-hidden />
          Recorded analysis plan
        </h2>
        <p className="mt-1 type-note text-text-muted">
          Planned tests, effect sizes and corrections. Review their assumptions
          before interpreting results.
        </p>
      </div>

      {error ? (
        <Notice kind="problem">Could not load the analysis plan. {error} <Button size="sm" variant="outline" onClick={reload}>Retry analysis plan</Button></Notice>
      ) : rows === null ? (
        <p className="flex items-center gap-2 type-body text-text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading…
        </p>
      ) : rows.length === 0 ? (
        <p className="type-body text-text-muted">
          No analysis plan recorded. Add one in Setup.
        </p>
      ) : (
        <div className="overflow-hidden rounded-card border border-border bg-surface">
          <ul>
            {rows.map((p, i) => {
              const isOpen = open === p.designShape;
              return (
                <li key={p.designShape} className={cn(i > 0 && "border-t border-border")}>
                  <button
                    className="flex w-full items-center gap-2 px-4 py-3 text-left hover:bg-zone-9"
                    onClick={() => setOpen(isOpen ? null : p.designShape)}
                    aria-expanded={isOpen}
                  >
                    {isOpen ? (
                      <ChevronDown className="size-4 shrink-0 text-text-muted" aria-hidden />
                    ) : (
                      <ChevronRight className="size-4 shrink-0 text-text-muted" aria-hidden />
                    )}
                    <span className="min-w-0 flex-1">
                      <span className="block type-body font-medium text-text">
                        {SHAPE_LABEL[p.designShape] ?? p.designShape}
                      </span>
                      <span className="block truncate type-caption text-text-muted">{p.test}</span>
                    </span>
                  </button>
                  {isOpen && (
                    <dl className="grid grid-cols-1 gap-x-6 gap-y-2 border-t border-border bg-bg px-4 py-3 type-body sm:grid-cols-[10rem_1fr]">
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
      <dt className="type-legend text-text-muted">{label}</dt>
      <dd className={cn("mb-1 sm:mb-0", muted ? "text-text-muted" : "text-text")}>{value}</dd>
    </>
  );
}
