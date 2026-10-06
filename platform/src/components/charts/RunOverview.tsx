import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { EmptyState } from "@/components/shell/EmptyState";
import { Select } from "@/components/ui/select";
import { studyApi } from "@/lib/studyApi";
import { useAsync } from "@/lib/useAsync";
import { captureTokenLabel, producerStateLabel } from "@/lib/uiText";

export function RunOverview({ studyId, preview = true, onReady, active = true }: {
  studyId: string; preview?: boolean; onReady?: (ready: boolean) => void; active?: boolean;
}) {
  const [participant, setParticipant] = useState(0);
  const { data: plan, loading, error, reload } = useAsync(
    () => studyApi.runPlan(studyId, participant, preview), [studyId, participant, preview],
  );
  useEffect(() => { onReady?.(Boolean(plan || error)); }, [plan, error, onReady]);
  const wasActive = useRef(active);
  useEffect(() => {
    if (active && !wasActive.current) reload();
    wasActive.current = active;
  }, [active, reload]);
  const empty = plan && !plan.hasProtocol && (
    plan.source !== "accepted-decisions" || (!plan.blocks?.length && !plan.participants?.design)
  );
  const draft = plan?.source === "accepted-decisions";
  const issues = [...(plan?.errors ?? []), ...(plan?.warnings ?? [])];
  const producers = Object.entries(plan?.producers ?? {}).filter(
    ([name, value]) => value.configured || plan?.requiredProducers?.includes(name),
  );

  return (
    <section className="flex flex-col gap-6" aria-label="Study-run overview" aria-busy={loading}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="type-section text-text">Study plan</h2>
        <Button size="sm" variant="ghost" onClick={reload} disabled={loading}>Refresh plan</Button>
      </div>
      {error ? (
        <Notice kind="problem">Could not load the plan. {error} Use Refresh plan to retry.</Notice>
      ) : loading && !plan ? (
        <div className="min-h-48 space-y-4" role="status" aria-label="Loading study plan">
          <p className="type-caption text-text-muted">Loading study plan…</p>
          <div className="h-4 w-2/3 animate-pulse rounded-control bg-zone-9" />
          <div className="h-12 w-full animate-pulse rounded-control bg-zone-9" />
        </div>
      ) : empty ? (
        <EmptyState
          line="Set a design and task in Setup to preview this study."
          action={<Button asChild size="sm"><Link to={{ search: "?tab=conversation" }}>Set up the study</Link></Button>}
        />
      ) : plan && (
        <>
          {plan.hasPendingChanges && <Notice>{draft ? "Preview of accepted decisions. Not yet applied to enrollment." : "Setup has unapplied decisions. This is the current enrollment protocol."}</Notice>}
          <dl className="grid grid-cols-1 gap-4 border-b border-border pb-5 sm:grid-cols-3">
            <div className="flex items-baseline justify-between gap-3 sm:block"><dt className="type-caption text-text-muted">Participants</dt><dd className="type-body text-text sm:mt-1">{plan.participants?.planned ?? "Unspecified"} planned participants</dd></div>
            <div className="flex items-baseline justify-between gap-3 sm:block"><dt className="type-caption text-text-muted">Design</dt><dd className="type-body text-text sm:mt-1">{plan.participants?.design?.replaceAll("-", " ") ?? "Not set"}</dd></div>
            <div className="flex items-baseline justify-between gap-3 sm:block"><dt className="type-caption text-text-muted">Session</dt><dd className="type-body text-text sm:mt-1">{plan.durationMinutes != null ? `${plan.durationMinutes} minutes per block` : "Timing not set"}</dd></div>
          </dl>
          <div className="flex flex-col gap-3">
            <label className="flex flex-wrap items-center justify-between gap-3 type-label text-text">
              Preview assignment for
              <Select aria-label="Preview assignment for" className="w-48" value={String(participant)} onValueChange={value => setParticipant(Number(value))}
                options={Array.from({ length: Math.min(Math.max(plan.participants?.planned ?? 2, 1), 12) }, (_, i) => ({ value: String(i), label: `Participant ${i + 1}` }))} />
            </label>
            {loading ? <p className="type-note text-text-muted" role="status">Updating assignment…</p> : plan.blocks?.length ? (
              <ol className="divide-y divide-border border-y border-border">
                {plan.blocks.map(block => <li key={block.index} className="py-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="type-body font-medium text-text">Block {block.index + 1}: {block.title}</span>
                    <span className="type-caption text-text-muted">{block.condition.replaceAll("-", " ")}</span>
                  </div>
                  {block.description && block.description !== block.title && <p className="mt-2 whitespace-pre-wrap break-words type-body text-text-muted">{block.description}</p>}
                </li>)}
              </ol>
            ) : <p className="type-body text-text-muted">Add conditions and tasks in Setup.</p>}
          </div>
          <details className="type-body text-text">
            <summary className="cursor-pointer type-control text-text-muted">Allocation and session steps</summary>
            <div className="mt-3 space-y-3">
              <p className="type-note text-text-muted">Preview only; no participant link is created. {plan.participants?.counterbalanced ? "Order is counterbalanced." : "Order is not counterbalanced."}</p>
              <p className="type-note text-text-muted">{plan.allocationNote}</p>
              <ol className="list-decimal space-y-2 pl-5">
                <li>Open the assigned folder in VS Code and review consent.</li>
                <li>Complete the blocks above, then end the session and debrief.</li>
                <li>Check capture integrity in Data and download the analysis bundle.</li>
              </ol>
            </div>
          </details>
          {issues.length > 0 && <details className="rounded-control border border-border p-3">
            <summary className="cursor-pointer type-control text-text">{issues.length} {issues.length === 1 ? "item" : "items"} to resolve before collecting data</summary>
            <ul className="mt-3 list-disc space-y-2 pl-5 type-caption text-text-muted">{issues.map((message, i) => <li key={i}>{message}</li>)}</ul>
          </details>}
          <details className="type-body text-text">
            <summary className="cursor-pointer type-control text-text-muted">Capture and privacy</summary>
            {plan.fatigueIntervalMinutes != null && <p className="mt-3 type-body">Fatigue prompts: every {plan.fatigueIntervalMinutes} minutes, subject to pause and quiet-tail settings.</p>}
            <ul className="mt-3 space-y-3">
              {producers.map(([name, value]) => <li key={name}><span className="font-medium">{captureTokenLabel(name)}</span>: {producerStateLabel(value.state)}{plan.requiredProducers?.includes(name) && " · Required"}<p className="mt-1 type-note text-text-muted">{value.reason}</p></li>)}
            </ul>
            {plan.privacy && <p className="mt-3 type-note text-text-muted">AI conversation policy: {plan.privacy.agentContentPolicy}. Raw code: {plan.privacy.rawCode ? "enabled; requires explicit consent" : "not collected"}. Clipboard text and individual keystrokes are not collected.</p>}
          </details>
          {preview && !loading && <div className="flex justify-end border-t border-border pt-4"><Button asChild size="sm"><Link to={{ search: draft ? "?tab=conversation" : "?tab=enrollment" }}>{draft ? "Review and apply in Setup" : "Go to Run"}</Link></Button></div>}
        </>
      )}
    </section>
  );
}
