import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Select } from "@/components/ui/select";
import { studyApi } from "@/lib/studyApi";
import { useAsync } from "@/lib/useAsync";

const SOURCE_LABEL: Record<string, string> = {
  tern: "Editor capture", metrics: "Code metrics", "agent-capture": "AI interaction capture",
  "workspace-snapshot": "Workspace snapshots", "participant-git": "Git history",
  "task-harness": "Task outcomes", "agent-derived": "Derived AI measures",
};
const STATE_LABEL: Record<string, string> = {
  enabled: "Configured", disabled: "Off", "external-required": "Separate runner needed",
  unsupported: "Not supported", unavailable: "Not configured",
};

export function RunOverview({ studyId, preview = true }: { studyId: string; preview?: boolean }) {
  const [participant, setParticipant] = useState(0);
  const { data: plan, loading, error, reload } = useAsync(
    () => studyApi.runPlan(studyId, participant, preview), [studyId, participant, preview],
  );
  const empty = plan && !plan.hasProtocol && plan.source !== "accepted-decisions";
  const draft = plan?.source === "accepted-decisions";
  const producers = Object.entries(plan?.producers ?? {}).filter(
    ([name, value]) => value.configured || plan?.requiredProducers?.includes(name),
  );

  return (
    <section className="flex flex-col gap-4" aria-label="Study-run overview" aria-busy={loading}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="type-section text-text">How this study will run</h2>
          <p className="mt-1 type-body text-text-muted">Planned configuration, not participant data.</p>
        </div>
        <Button size="sm" variant="outline" onClick={reload} disabled={loading}>Refresh plan</Button>
      </div>
      {error ? (
        <Notice kind="problem">Could not load the run plan. {error} Use Refresh plan to retry.</Notice>
      ) : loading && !plan ? (
        <p className="type-body text-text-muted" role="status">Loading the participant journey…</p>
      ) : empty ? (
        <div className="flex flex-col items-start gap-3">
          <p className="type-body text-text-muted">Accept a design proposal or enter protocol details to see tasks, timing, and capture here.</p>
          <Button asChild size="sm"><Link to={{ search: "?tab=conversation" }}>Set up the study</Link></Button>
        </div>
      ) : plan && (
        <>
          {plan.hasPendingChanges && (
            <Notice>{draft ? "Preview of accepted decisions. These changes are not applied to enrollment." : "Setup has unapplied decisions. Enrollment still uses the current protocol shown here."}</Notice>
          )}
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 type-body text-text">
            <span>{plan.participants?.planned ?? "Unspecified"} planned participants</span>
            <span>{plan.participants?.design?.replaceAll("-", " ") ?? "Design not set"}</span>
            <span>{plan.durationMinutes != null ? `${plan.durationMinutes} minutes per block` : "Timing not set"}</span>
          </div>
          <label className="flex flex-wrap items-center gap-2 type-label text-text">
            Preview assignment for
            <Select aria-label="Preview assignment for" className="w-48" value={String(participant)} onValueChange={(value) => setParticipant(Number(value))}
              options={Array.from({ length: Math.min(Math.max(plan.participants?.planned ?? 2, 1), 12) }, (_, i) => ({ value: String(i), label: `Participant ${i + 1}` }))} />
          </label>
          <p className="type-caption text-text-muted">Assignment examples only; no participant link is created. {plan.participants?.counterbalanced ? "Order is counterbalanced." : "Order is not counterbalanced."}</p>
          <p className="type-caption text-text-muted">{plan.allocationNote}</p>
          <ol className="list-decimal space-y-3 pl-5 type-body text-text">
            <li>Open the assigned folder in VS Code and review consent before capture starts.</li>
            <li>
              Complete the assigned blocks in order.
              {loading ? <p className="mt-1 text-text-muted" role="status">Updating the participant journey…</p> : plan.blocks?.length ? (
                <ol className="mt-2 divide-y divide-border border-y border-border">
                  {plan.blocks.map((block) => (
                    <li key={block.index} className="py-3">
                      <div className="flex flex-wrap gap-x-3 gap-y-1"><span className="font-medium">Block {block.index + 1}: {block.title}</span><span className="text-text-muted">{block.condition.replaceAll("-", " ")}</span></div>
                      {block.description && block.description !== block.title && <p className="mt-1 whitespace-pre-wrap break-words text-text-muted">{block.description}</p>}
                    </li>
                  ))}
                </ol>
              ) : <p className="mt-1 text-text-muted">Set conditions and tasks to preview the assignment.</p>}
            </li>
            <li>End each session and complete the configured debrief.</li>
            <li>Inspect capture integrity in Data, then download the analysis bundle.</li>
          </ol>
          {(plan.errors.length > 0 || !!plan.warnings?.length) && (
            <Notice kind={plan.errors.length ? "problem" : "note"}>
              <p className="font-medium">Resolve before collecting data</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">{[...plan.errors, ...(plan.warnings ?? [])].map((message, i) => <li key={i}>{message}</li>)}</ul>
            </Notice>
          )}
          <details className="border-y border-border py-3">
            <summary className="cursor-pointer type-label text-text">Capture and privacy</summary>
            {plan.fatigueIntervalMinutes != null && <p className="mt-3 type-body text-text">Fatigue prompts: every {plan.fatigueIntervalMinutes} minutes, subject to pause and quiet-tail settings.</p>}
            <ul className="mt-3 space-y-3 type-body text-text">
              {producers.map(([name, value]) => (
                <li key={name}><span className="font-medium">{SOURCE_LABEL[name] ?? name}</span>: {STATE_LABEL[value.state] ?? value.state}{plan.requiredProducers?.includes(name) && " · Required"}<p className="mt-1 text-text-muted">{value.reason}</p></li>
              ))}
            </ul>
            {plan.privacy && <p className="mt-3 type-caption text-text-muted">AI conversation policy: {plan.privacy.agentContentPolicy}. Raw code: {plan.privacy.rawCode ? "enabled; requires explicit consent" : "not collected"}. Clipboard text and individual keystrokes are not collected.</p>}
          </details>
          {preview && !loading && <Button asChild size="sm" className="self-start"><Link to={{ search: draft ? "?tab=conversation" : "?tab=enrollment" }}>{draft ? "Review and apply in Setup" : "Continue to enrollment"}</Link></Button>}
        </>
      )}
    </section>
  );
}
