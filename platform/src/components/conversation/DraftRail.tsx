import {
  MANDATORY_SLOTS,
  OPTIONAL_SLOTS,
  SLOT_LABELS,
  type ProtocolDraft,
  type Understanding,
} from "@/lib/types";
import { formatSlotValue, summarizeProtocol, type ProtocolSection } from "@/lib/protocolFormat";
import { buildProtocolPath } from "@/lib/protocolPath";
import { protocolToDraft } from "@/lib/compiler";
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
  unresolved,
  onApply,
  onEdit,
  applying,
  onFinish,
  understanding,
  loading,
  scopeBlocked,
  onNextStep,
}: {
  draft: ProtocolDraft;
  serverYaml?: string;
  protocol?: Record<string, unknown>;
  compileValid?: boolean;
  compileErrors?: string[];
  compileWarnings?: string[];
  unresolved?: string[];
  onApply?: () => void;
  onEdit?: () => void;
  applying?: boolean;
  onFinish?: () => void;
  understanding?: Understanding;
  loading?: boolean;
  /** The last idea was outside PHOENIX's supported lane. Keep the draft
   *  visible, but stop the rail from asking a developer-study question that
   *  contradicts the boundary message in the conversation. */
  scopeBlocked?: boolean;
  /** Called with the next unfilled section's label; the host drafts a prompt
   *  into the composer without sending it. */
  onNextStep?: (sectionLabel: string) => void;
}) {
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
  /* A study whose protocol exists before any conversation (a template, the
   * example, an applied draft) is not "0 of 7": read the checklist from that
   * protocol until the conversation starts changing it. */
  const shown: ProtocolDraft = sections && protocol ? protocolToDraft(protocol) : draft;
  const nextSlot = MANDATORY_SLOTS.find((s) => shown[s].length === 0);
  const nextStep = (): { label: string } | null =>
    nextSlot ? { label: SLOT_LABELS[nextSlot] } : null;
  const path = buildProtocolPath(shown, scopeBlocked ? undefined : understanding);
  const complete = unresolved !== undefined
    ? unresolved.length === 0
    : MANDATORY_SLOTS.every((slot) => shown[slot].length > 0);
  /* The compiler can validate a partial scaffold while the conversation is
   * still walking the researcher through its core sections. Readiness in this
   * rail is a researcher-facing hand-off, so the visible path must also be
   * complete before the draft can read as runnable. */
  const ready = complete && path.done === path.total && compileValid === true;
  const draftCaption = loading
    ? "Restoring your latest decisions."
    : compileErrors && compileErrors.length > 0
      ? "Needs a correction before it can run."
    : ready
      ? "Ready to review and apply."
      : null;

  return (
    <aside className="flex h-full min-w-0 flex-col bg-surface">
      <div className="shrink-0 border-b border-border px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <p className="mt-1 type-caption text-text" aria-live="polite">
            <span className="type-quantity">{path.done} of {path.total} drafted.</span>
            {!scopeBlocked && !ready && nextStep() && (
              <>
                {" Next: "}
                {onNextStep ? (
                  <button
                    type="button"
                    className="type-caption text-accent underline underline-offset-2 hover:text-text"
                    onClick={() => onNextStep(nextStep()!.label)}
                  >
                    {nextStep()!.label}
                  </button>
                ) : (
                  nextStep()!.label
                )}
              </>
            )}
            {ready && " Review the draft."}
          </p>
          <ProtocolGuide />
        </div>
        {draftCaption && (
          <p className="mt-1 type-note text-text-muted">{draftCaption}</p>
        )}
        <div className="mt-3">
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
          {scopeBlocked ? (
            <p className="mt-3 rounded-input border border-accent/30 bg-accent-wash px-3 py-2 type-note text-text">
              <span className="type-legend text-accent">Setup paused</span>
              <span className="ml-2">Use a supported coding-study brief to continue.</span>
            </p>
          ) : null}
        </div>

      </div>

      <div className="min-h-0 min-w-0 flex-1 overflow-y-auto px-5 py-4">
        {/* One list answers "what is decided and what is next". It replaces
          * a path list, an open-choices list and a section list that each
          * repeated the same seven sections. Compiler notes appear in the
          * Review draft dialog, where they are acted on. */}
        {compileErrors && compileErrors.length > 0 && (
          <details className="mb-4 rounded-input border border-critical bg-surface p-3" open>
            <summary className="type-caption cursor-pointer font-medium text-critical">Draft needs correction</summary>
            <ul className="mt-1 flex flex-col gap-1 type-caption text-text">
              {compileErrors.slice(0, 2).map((error) => <li key={error}>{error}</li>)}
            </ul>
          </details>
        )}
        <SlotPlate draft={shown} next={scopeBlocked || ready ? undefined : nextSlot} />
        {sections && sections.length > 0 && (
          <details className="mt-5 border-t border-border pt-4">
            <summary className="type-control cursor-pointer text-text-muted hover:text-text">Full protocol</summary>
            <div className="mt-3 flex flex-col gap-3">
              {sections.map((section) => (
                <SectionBlock key={section.heading} section={section} />
              ))}
            </div>
            {serverYaml?.trim() && (
              <details className="mt-4">
                <summary className="type-caption cursor-pointer text-text-muted">View raw YAML</summary>
                <pre className="tabular mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded-input border border-border-strong bg-bg p-2 type-quantity leading-relaxed text-text">{serverYaml}</pre>
              </details>
            )}
          </details>
        )}
      </div>

      {(onFinish || onApply || onEdit) && (
        <div className="flex gap-2 border-t border-border bg-surface p-4">
          {onEdit && (
            <Button size="sm" variant="ghost" onClick={onEdit}>
              Edit details
            </Button>
          )}
          {onFinish && (
            <Button size="sm" onClick={onFinish} className="flex-1">
              Review draft
            </Button>
          )}
          {onApply && !onFinish && (
            <Button
              size="sm"
              variant="outline"
              disabled={!ready || applying}
              onClick={onApply}
              className="flex-1"
              title={ready ? undefined : "Finish the required sections before applying this draft."}
            >
              {applying ? "Applying…" : "Apply protocol"}
            </Button>
          )}
        </div>
      )}
    </aside>
  );
}

function SlotPlate({
  draft,
  next,
}: {
  draft: ProtocolDraft;
  /** The section to settle next, marked so the list doubles as the path. */
  next?: keyof ProtocolDraft;
}) {
  return (
    <ul className="min-w-0 divide-y divide-border">
      {MANDATORY_SLOTS.map((slot) => (
        <li key={slot} className="flex items-start gap-3 py-3">
          <span
            className={cn(
              "type-label min-w-0 flex-1",
              draft[slot].length > 0 || slot === next ? "text-text" : "text-text-muted",
            )}
          >
            {SLOT_LABELS[slot]}
          </span>
          {draft[slot].length > 0 ? (
            <ul className="flex min-w-0 flex-[1.4] flex-col gap-0.5 type-caption text-text">
              {draft[slot].map((value, index) => <li key={index}>{formatSlotValue(slot, value)}</li>)}
            </ul>
          ) : slot === next ? (
            <span className="type-caption text-accent">Next</span>
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
              {draft[slot].map((value, index) => <li key={index}>{formatSlotValue(slot, value)}</li>)}
            </ul>
          ) : (
            <span className="type-caption text-text-muted">Optional for now</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function SectionBlock({ section }: { section: ProtocolSection }) {
  return (
    <section>
      <h3 className="type-legend text-text-muted">{section.heading}</h3>
      <ul className="mt-1 flex flex-col gap-1">
        {section.lines.map((line, index) => <li key={index} className="break-words type-caption text-text">{line}</li>)}
      </ul>
    </section>
  );
}
