import { Lock } from "lucide-react";
import { cn } from "@/lib/cn";
import type { Amendment } from "@/lib/types";

/* The amendment history — a quiet vertical list on the study page. Versions, summaries, approvers, artifacts. Precise register,
 * unanimated (a consent-adjacent surface). The binding parts (degrees of
 * freedom): version chips, plain-language summaries, and the consent register.
 * No drama: evolution is normal, and its record reads calmly. */

/** A monospace revision chip so two revisions are distinguishable at a glance
 * (F4.3 renders the same chip beside sessions and dataset rows). */
export function VersionChip({ version }: { version: number }) {
  return (
    <span
      data-agent="version-chip"
      className="inline-flex items-center rounded-chip border border-border-strong px-2 py-0.5 font-mono text-xs text-text-muted"
    >
      v{version}
    </span>
  );
}

export function AmendmentHistory({ amendments }: { amendments: Amendment[] }) {
  if (amendments.length === 0) {
    return (
      <p className="px-1 text-sm text-text-muted">
        No amendments yet. After ethics approval, every change is recorded here
        with its consent impact.
      </p>
    );
  }
  return (
    <ol data-agent="amendment-history" className="flex flex-col gap-3">
      {[...amendments]
        .sort((a, b) => b.fromVersion - a.fromVersion)
        .map((a,) => (
          <li
            key={a.id}
            className="rounded-card border border-border bg-surface p-4 text-sm"
          >
            <div className="flex flex-wrap items-center gap-2">
              <VersionChip version={a.fromVersion} />
              <span aria-hidden className="text-text-muted">
                →
              </span>
              <VersionChip version={a.toVersion} />
              {a.consentRelevant ? (
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-chip px-2 py-0.5 text-xs",
                    a.reapprovalArtifact
                      ? "text-grounded"
                      : "bg-unsourced-soft text-unsourced")}
                >
                  <Lock className="size-3" aria-hidden />
                  {a.reapprovalArtifact
                    ? "consent-relevant · re-approved"
                    : "consent-relevant · awaiting re-approval"}
                </span>
              ) : (
                <span className="rounded-chip px-2 py-0.5 text-xs text-text-muted">
                  config change
                </span>
              )}
            </div>

            <ul className="mt-2 flex flex-col gap-0.5">
              {a.changes.map((c, i) => (
                <li key={i} className="text-text">
                  {c}
                </li>
              ))}
            </ul>

            {a.rationale && (
              <p className="mt-1 text-text-muted">{a.rationale}</p>
            )}

            {a.consentRelevant && a.consentReasons.length > 0 && (
              <ul className="mt-2 border-l-2 border-unsourced pl-3 text-xs text-text-muted">
                {a.consentReasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            )}

            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
              <span>approved by {a.approvedBy}</span>
              <span>{a.at.slice(0, 10)}</span>
              {a.reapprovalArtifact && (
                <span className="text-grounded">
                  re-approval: {a.reapprovalArtifact}
                </span>
              )}
            </div>
          </li>
        ))}
    </ol>
  );
}
