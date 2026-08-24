import {
  MANDATORY_SLOTS,
  OPTIONAL_SLOTS,
  SLOT_LABELS,
  type ProtocolDraft,
  type Understanding,
} from "@/lib/types";
import { summarizeProtocol, type ProtocolSection } from "@/lib/protocolFormat";
import { buildProtocolPath } from "@/lib/protocolPath";
import { Button } from "@/components/ui/button";
import { ProtocolGuide } from "./ProtocolGuide";
import { cn } from "@/lib/cn";

/* The rail is the study's working memory, not a second transcript. It answers
 * three things at a glance: what has been decided, what is next, and whether
 * the draft can be reviewed. Full protocol prose stays below the fold. */
export function DraftRail({
  draft,
  serverYaml,
  protocol,
  compileValid,
  compileErrors,
  compileWarnings,
  unresolved,
  onApply,
  applying,
  onFinish,
  understanding,
  loading,
}: {
  draft: ProtocolDraft;
  serverYaml?: string;
  protocol?: Record<string, unknown>;
  compileValid?: boolean;
  compileErrors?: string[];
  compileWarnings?: string[];
  unresolved?: string[];
  onApply?: () => void;
  applying?: boolean;
  onFinish?: () => void;
  understanding?: Understanding;
  loading?: boolean;
}) {
  const path = buildProtocolPath(draft, understanding);
  const complete = unresolved !== undefined
    ? unresolved.length === 0
    : MANDATORY_SLOTS.every((slot) => draft[slot].length > 0);
  const ready = complete && compileValid === true;
  const conversationStarted = MANDATORY_SLOTS.some((slot) => draft[slot].length > 0);
  const protocolStudy = protocol?.study;
  const isFreshDraft = Boolean(
    !conversationStarted &&
      protocolStudy &&
      typeof protocolStudy === "object" &&
      !Array.isArray(protocolStudy) &&
      (protocolStudy as Record<string, unknown>).id === "draft",
  );
  const sections: ProtocolSection[] | null = protocol && !isFreshDraft && !conversationStarted
    ? summarizeProtocol(protocol)
    : null;
  const draftCaption = loading
    ? "Restoring your latest decisions."
    : compileErrors && compileErrors.length > 0
      ? "Needs a correction before it can run."
    : ready
      ? "Ready to review and apply."
      : "Updates as you settle each choice.";

  return (
    <aside data-agent="draft-rail" className="flex h-full flex-col bg-surface">
      <div className="border-b border-border px-5 py-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="type-legend text-accent">STUDY MAP</p>
            <h2 className="mt-1 type-section text-text">Protocol draft</h2>
            <p className="mt-1 type-caption text-text-muted">{draftCaption}</p>
          </div>
          <ProtocolGuide />
        </div>

        <div className="mt-5" data-agent="slot-meter">
          <div className="flex items-baseline justify-between gap-2">
            <span className="type-caption text-text-muted">Draft progress</span>
            <span className="type-quantity text-text">{path.done}/{path.total}</span>
          </div>
          <div
            className="mt-2 h-1.5 overflow-hidden rounded-chip bg-well"
            role="progressbar"
            aria-label="Protocol draft progress"
            aria-valuemin={0}
            aria-valuemax={path.total}
            aria-valuenow={path.done}
          >
            <div
              className="h-full rounded-chip bg-accent transition-[width] duration-standard"
              style={{ width: `${path.total ? (path.done / path.total) * 100 : 0}%` }}
            />
          </div>
          {path.upNext && (
            <p className="mt-3 rounded-input bg-accent-wash px-3 py-2 type-caption text-text" data-agent="protocol-path-current">
              <span className="type-legend text-accent">NEXT</span>
              <span className="ml-2">{path.upNext}</span>
            </p>
          )}
        </div>

        <details className="mt-4" data-agent="protocol-path">
          <summary className="type-control cursor-pointer text-text-muted hover:text-text">Show the path</summary>
          <div className="mt-3 flex flex-col gap-3 border-l border-border pl-3">
            {path.phases.map((phase) => (
              <div key={phase.title}>
                <p className="type-legend text-text-muted">{phase.title}</p>
                <ol className="mt-1 flex flex-col gap-1.5">
                  {phase.steps.map((step) => (
                    <li key={step.id} className="flex items-center gap-2 type-caption text-text">
                      <span
                        aria-hidden
                        className={cn(
                          "size-2 shrink-0 rounded-dot border",
                          step.status === "done" && "border-ink bg-ink",
                          step.status === "current" && "border-accent bg-accent",
                          step.status === "todo" && "border-border-strong",
                        )}
                      />
                      <span className={cn(step.status === "todo" && "text-text-muted")}>{step.label}</span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </details>

        {unresolved && unresolved.length > 0 && (
          <details className="mt-3">
            <summary className="type-caption cursor-pointer text-text-muted">Open choices</summary>
            <ul className="mt-1 flex flex-col gap-1 type-caption text-text-muted">
              {unresolved.map((slot) => (
                <li key={slot}>{SLOT_LABELS[slot as keyof typeof SLOT_LABELS] ?? slot}</li>
              ))}
            </ul>
            <p className="mt-2 type-caption text-text-muted">
              These stay in the draft while you work. They only matter when you review a runnable protocol.
            </p>
          </details>
        )}
        {compileErrors && compileErrors.length > 0 && (
          <details className="mt-3 rounded-input border border-critical bg-surface p-3" open>
            <summary className="type-caption cursor-pointer font-medium text-critical">Draft needs correction</summary>
            <ul className="mt-1 flex flex-col gap-1 type-caption text-text">
              {compileErrors.slice(0, 2).map((error) => <li key={error}>{error}</li>)}
            </ul>
          </details>
        )}
        {compileWarnings && compileWarnings.length > 0 && (
          <details className="mt-3">
            <summary className="type-caption cursor-pointer text-text-muted">Compiler notes ({compileWarnings.length})</summary>
            <ul className="mt-1 flex flex-col gap-1 type-caption text-text-muted">
              {compileWarnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          </details>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-auto px-5 py-4">
        {sections && sections.length > 0 ? (
          <div className="flex flex-col gap-3">
            {sections.map((section) => (
              <SectionBlock key={section.heading} section={section} collapsible={sections.length > 4} />
            ))}
          </div>
        ) : (
          <SlotPlate draft={draft} />
        )}
        {serverYaml?.trim() && sections && (
          <details className="mt-5">
            <summary className="type-caption cursor-pointer text-text-muted">View raw YAML</summary>
            <pre className="tabular mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-input border border-border-strong bg-bg p-2 type-quantity leading-relaxed text-text">{serverYaml}</pre>
          </details>
        )}
      </div>

      {(onFinish || onApply) && (
        <div className="flex gap-2 border-t border-border bg-surface p-4">
          {onFinish && (
            <Button size="sm" data-agent="draft-finish" onClick={onFinish} className="flex-1">
              {ready ? "Review draft" : "Review status"}
            </Button>
          )}
          {onApply && (
            <Button
              size="sm"
              variant="outline"
              disabled={!compileValid || applying}
              data-agent="draft-apply"
              onClick={onApply}
              className="flex-1"
              title={compileValid ? undefined : "Finish the required sections before applying this draft."}
            >
              {applying ? "Applying…" : "Apply protocol"}
            </Button>
          )}
        </div>
      )}
    </aside>
  );
}

function SlotPlate({ draft }: { draft: ProtocolDraft }) {
  return (
    <ul className="divide-y divide-border" data-agent="draft-slot-plate">
      {MANDATORY_SLOTS.map((slot) => (
        <li key={slot} className="flex items-start gap-3 py-3">
          <span className="type-label min-w-0 flex-1 text-text">{SLOT_LABELS[slot]}</span>
          {draft[slot].length > 0 ? (
            <ul className="flex min-w-0 flex-[1.4] flex-col gap-0.5 type-caption text-text">
              {draft[slot].map((value, index) => <li key={index}>{value}</li>)}
            </ul>
          ) : (
            <span className="mt-1.5 size-2 shrink-0 rounded-dot border border-border-strong" role="img" aria-label="not yet resolved" />
          )}
        </li>
      ))}
      {OPTIONAL_SLOTS.map((slot) => (
        <li key={slot} className="flex items-start gap-3 border-t border-border py-3">
          <span className="type-label min-w-0 flex-1 text-text">{SLOT_LABELS[slot]}</span>
          {draft[slot].length > 0 ? (
            <ul className="flex min-w-0 flex-[1.4] flex-col gap-0.5 type-caption text-text">
              {draft[slot].map((value, index) => <li key={index}>{value}</li>)}
            </ul>
          ) : (
            <span className="type-caption text-text-muted">Optional for now</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function SectionBlock({ section, collapsible }: { section: ProtocolSection; collapsible: boolean }) {
  return (
    <details open={!collapsible} className="border-t border-border pt-3 first:border-0 first:pt-0">
      <summary className="type-control cursor-pointer text-text-muted hover:text-text">{section.heading}</summary>
      <ul className="mt-1 flex flex-col gap-1">
        {section.lines.map((line, index) => <li key={index} className="type-caption text-text">{line}</li>)}
      </ul>
    </details>
  );
}
