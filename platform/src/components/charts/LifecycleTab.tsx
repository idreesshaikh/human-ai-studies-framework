import { useEffect, useState } from "react";
import { Check, Circle, Lock } from "lucide-react";
import { studyApi, type LifecycleDoc } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The lifecycle board (FR-DASH-2) — the study's phases and their gate
 * artifacts, derived from the protocol, never hand-set. A calm, precise
 * surface: the current phase is highlighted, satisfied gates read green, and an
 * unsatisfied gate names exactly what's missing. Consent-adjacent, so it does
 * not animate. */
export function LifecycleTab({ studyId }: { studyId: string }) {
  const [doc, setDoc] = useState<LifecycleDoc | null>(null);

  useEffect(() => {
    let live = true;
    studyApi.lifecycle(studyId).then((d) => live && setDoc(d));
    return () => {
      live = false;
    };
  }, [studyId]);

  if (!doc) return <p className="p-6 text-sm text-text-muted">Loading…</p>;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 overflow-auto p-6">
      <h2 className="text-sm font-medium text-text">
        Lifecycle · <span className="text-text-muted">{doc.currentPhase}</span>
      </h2>
      <ol className="flex flex-col">
        {doc.phases.map((p, i) => {
          const isLast = i === doc.phases.length - 1;
          return (
            <li key={p.name} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={cn(
                    "flex size-6 items-center justify-center rounded-chip border",
                    p.status === "complete" && "border-grounded bg-grounded text-accent-contrast",
                    p.status === "current" && "border-accent text-accent",
                    p.status === "upcoming" && "border-border text-text-muted",
                  )}
                >
                  {p.status === "complete" ? (
                    <Check className="size-3.5" aria-hidden />
                  ) : (
                    <Circle className="size-2 fill-current" aria-hidden />
                  )}
                </span>
                {!isLast && (
                  <span
                    className={cn(
                      "w-px flex-1",
                      p.status === "complete" ? "bg-grounded" : "bg-border",
                    )}
                  />
                )}
              </div>
              <div className={cn("flex-1 pb-6", isLast && "pb-0")}>
                <p
                  className={cn(
                    "text-sm font-medium",
                    p.status === "current" ? "text-accent" : "text-text",
                  )}
                >
                  {p.name}
                </p>
                {p.gates.length > 0 && (
                  <ul className="mt-1 flex flex-col gap-1">
                    {p.gates.map((g) => (
                      <li
                        key={g.artifact}
                        className="flex items-center gap-2 text-xs"
                      >
                        {g.satisfied ? (
                          <Check className="size-3 text-grounded" aria-hidden />
                        ) : (
                          <Lock className="size-3 text-unsourced" aria-hidden />
                        )}
                        <span className="font-mono text-text-muted">
                          {g.artifact}
                        </span>
                        {g.satisfied && g.satisfiedBy && (
                          <span className="text-text-muted">
                            · {g.satisfiedBy.uploadedAt}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
