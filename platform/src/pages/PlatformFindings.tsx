import { ArrowDown, MessageSquare, FileText } from "lucide-react";
import { useEvolution } from "@/lib/evolutionStub";
import { cn } from "@/lib/cn";

/* The platform-findings surface. The loop
 * rendered: feedback → finding → drafted proposal, so the self-application is
 * *visible*, not just implemented. The platform grows its own SRS from its
 * users' conversations exactly as a study grows from its researcher's.
 *
 * Cross-project learning aggregates anonymous shape only; this surface shows a
 * project's own feedback loci (rendering a locus needs project membership) and
 * the inert proposal drafted from them — a person approves it, nothing
 * self-applies. */

const KIND_LABEL: Record<string, string> = {
  "ux-defect": "clunky",
  "template-gap": "template gap",
  "template-improvement": "template",
  "new-template": "new template",
  unclassified: "thought",
};

export function PlatformFindings() {
  const { findings, proposal } = useEvolution();

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-text">
          How the platform is evolving
        </h1>
        <p className="text-sm text-text-muted">
          Feedback you flag in a design conversation becomes a finding, and
          findings are drafted into an improvement proposal — the same loop your
          study runs on, turned on the platform itself.
        </p>
      </header>

      {/* Stage 1 — the feedback, from conversations. */}
      <section className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-text">
          <MessageSquare className="size-4 text-accent" aria-hidden />
          Feedback, from your conversations
          <span className="text-text-muted">({findings.length})</span>
        </div>
        {findings.length === 0 ? (
          <p className="text-sm text-text-muted">
            Nothing flagged yet. In a conversation, flag a turn for the platform
            and it lands here.
          </p>
        ) : (
          <ul data-agent="platform-findings" className="flex flex-col gap-2">
            {findings.map((f,) => (
              <li
                key={f.id}
                className="rounded-card border border-border bg-surface p-3 text-sm"
              >
                <div className="flex items-center gap-2">
                  <span className="rounded-chip bg-accent-soft px-2 py-0.5 text-xs text-accent">
                    {KIND_LABEL[f.locus.kind] ?? f.locus.kind}
                  </span>
                  <span className="text-xs text-text-muted">
                    finding #{f.id} · turn {f.locus.seq}
                  </span>
                </div>
                <p className="mt-1 text-text">{f.note}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="flex items-center justify-center gap-2 text-xs text-text-muted">
        <ArrowDown className="size-4" aria-hidden />
        drafted from {proposal.generatedFrom.feedbackFindings} finding
        {proposal.generatedFrom.feedbackFindings === 1 ? "" : "s"}
      </div>

      {/* Stage 2 — the inert drafted proposal. */}
      <section
        data-agent="retrospective-proposal"
        className="flex flex-col gap-3 rounded-card border border-border bg-surface-raised p-4"
      >
        <div className="flex items-center gap-2">
          <FileText className="size-4 text-text-muted" aria-hidden />
          <span className="text-sm font-medium text-text">{proposal.title}</span>
          <span className="rounded-chip border border-border-strong px-2 py-0.5 text-xs text-text-muted">
            inert draft
          </span>
        </div>
        <p className="text-sm text-text-muted">
          A person approves this — nothing self-applies. It cites the findings
          it drew on:{" "}
          {proposal.citedFindingIds.map((id,) => `#${id}`).join(", ") || "none"}.
        </p>
        {proposal.items.length > 0 && (
          <ul className="flex flex-col gap-2">
            {proposal.items.map((item, i) => (
              <li
                key={i}
                className="rounded-input border border-border bg-surface p-3 text-sm"
              >
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "rounded-chip px-2 py-0.5 text-xs",
                      item.kind === "ux-defect"
                        ? "bg-unsourced-soft text-unsourced"
                        : "bg-accent-soft text-accent")}
                  >
                    {KIND_LABEL[item.kind] ?? item.kind}
                  </span>
                  <span className="text-text">{item.title}</span>
                </div>
                <p className="mt-1 font-mono text-xs text-text-muted">
                  {JSON.stringify(item.evidence)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
