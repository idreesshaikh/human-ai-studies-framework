import {
  MANDATORY_SLOTS,
  SLOT_LABELS,
  type ProtocolDraft,
  type Understanding,
} from "@/lib/types";
import { summarizeProtocol, type ProtocolSection } from "@/lib/protocolFormat";
import { Button } from "@/components/ui/button";
import { SlotMeter } from "./SlotMeter";
import { ProtocolGuide } from "./ProtocolGuide";

/* The draft rail: the protocol compiled so far, told as prose sections
 * rather than raw YAML  -  a researcher should be able to read it, not parse
 * it. The literal compiled document is still one click away behind "View
 * raw YAML" for anyone (or any agent) that wants it verbatim. */
export function DraftRail({
  draft,
  serverYaml,
  protocol,
  compileValid,
  unresolved,
  onApply,
  applying,
  onFinish,
  understanding,
}: {
  draft: ProtocolDraft;
  serverYaml?: string;
  protocol?: Record<string, unknown>;
  compileValid?: boolean;
  /** Outstanding protocol slots from the server compile, in plain words. */
  unresolved?: string[];
  onApply?: () => void;
  applying?: boolean;
  onFinish?: () => void;
  /** What the conversation still needs to know before a design shape can
   * honestly follow from it (FR-CONV-10). It lives here, beside the draft it
   * is about, rather than as a strip inside the thread: printed under every
   * exchange it read as the assistant apologising in the middle of the
   * conversation, and it says the same thing on every turn until the answer
   * changes, which is exactly what chat is bad at carrying. */
  understanding?: Understanding;
}) {
  /* Readiness is the server's answer, not a count of lit dots  -  the eight
   * conversation sections and the protocol's requirements are different
   * lists. Before the first compile comes back, fall back to the sections so
   * the button still reads sensibly. */
  const complete =
    unresolved !== undefined
      ? unresolved.length === 0
      : MANDATORY_SLOTS.every((s) => draft[s].length > 0);
  const sections: ProtocolSection[] | null = protocol
    ? summarizeProtocol(protocol)
    : null;

  /* This rail carries two different things: how far the CONVERSATION has got
   * (the step path, the "no design shape yet" caution) and what the PROTOCOL
   * currently says. A study can hold a complete protocol without a
   * conversation ever having happened  -  seeded from a template, a merged
   * pair, or a derived paper, and every study anyone is only reading. In that
   * case the conversation half claimed "0/13 steps · Not covered yet:
   * Research questions…" directly above the research questions it was
   * listing. The progress half is simply not about this study, so it is not
   * shown; the protocol still is. */
  const conversationStarted = MANDATORY_SLOTS.some((s) => draft[s].length > 0);
  const showConversationProgress = conversationStarted || !sections?.length;

  return (
    <aside
      data-agent="draft-rail"
      className="flex h-full flex-col bg-surface"
    >
      <div className="flex items-start justify-between gap-2 p-gutter pb-3">
        <div>
          <h2 className="type-subhead text-text">
            Protocol draft
          </h2>
          <p className="type-caption text-text-muted">
            {showConversationProgress
              ? "Compiled from the moves you've accepted."
              : // No moves were accepted here  -  this protocol arrived with the
                // study (a template, a merge, a derived paper) or belongs to
                // someone else's study you are reading.
                "The study's protocol as it currently stands."}
          </p>
        </div>
        <ProtocolGuide />
      </div>

      {showConversationProgress && (
        <SlotMeter draft={draft} unresolved={unresolved} understanding={understanding} />
      )}

      {/* The scroller is the document body. Progress and actions stay outside
        * it, so the rail has a stable command area while the protocol grows. */}
      <div className="min-h-0 flex-1 overflow-auto px-gutter">
        {sections ? (
          sections.length > 0 ? (
            <div className="flex flex-col gap-2.5">
              {/* A freshly created study compiles to a protocol that is not
                * empty  -  it carries scaffolding the researcher never wrote
                * ("Study: led by Researcher", "Phases: design")  -  so
                * `sections.length > 0` was true from the first paint even
                * when no move had ever been accepted. Showing the unfilled
                * `SlotPlate` here too meant every slot it lists as "not yet
                * resolved" sat directly above the real, filled-in section
                * saying the opposite  -  a study whose protocol arrived
                * pre-built (template, merge, derived paper) contradicted
                * itself before a reader got past the first screen. The plate
                * only belongs where there is truly nothing else to show,
                * which is the `sections.length === 0` branch below. */}
              {sections.map((section) => (
                <SectionBlock
                  key={section.heading}
                  section={section}
                  collapsible={sections.length > 4}
                />
              ))}
            </div>
          ) : (
            <SlotPlate draft={draft} />
          )
        ) : serverYaml?.trim() ? (
          <pre className="tabular type-caption whitespace-pre-wrap type-quantity leading-relaxed text-text">
            {serverYaml}
          </pre>
        ) : (
          <SlotPlate draft={draft} />
        )}
      </div>

      <div className="flex flex-col gap-3 border-t border-border bg-surface p-gutter pt-3">
        {sections && sections.length > 0 && serverYaml?.trim() && (
          <details className="group">
            <summary className="type-caption cursor-pointer text-text-muted select-none">
              View raw YAML
            </summary>
            <pre className="tabular type-caption mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded-input border border-border-strong bg-bg p-2 type-quantity leading-relaxed text-text">
              {serverYaml}
            </pre>
          </details>
        )}

        {(onFinish || onApply) && (
          <div className="flex flex-wrap items-center gap-2">
            {onFinish && (
              <Button
                size="sm"
                data-agent="draft-finish"
                onClick={onFinish}
                className="flex-1"
              >
                {complete ? "Finish and review" : "Review draft"}
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
                title={
                  compileValid
                    ? undefined
                    : "The draft has to compile and validate before it can be applied."
                }
              >
                {applying ? "Applying…" : "Apply to protocol"}
              </Button>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}

/* The plate's own frame: every slot the protocol needs, as an address that
 * either carries something or is still blank. An unfilled slot is marked with
 * the open ring  -  the same notation "nothing identified here yet" wears
 * everywhere else  -  instead of repeating the sentence "Not yet resolved."
 * eight times down the rail, which was eight lines of text saying what eight
 * marks say at a glance. */
function SlotPlate({ draft }: { draft: ProtocolDraft }) {
  return (
    <ul className="divide-y divide-border" data-agent="draft-slot-plate">
      {MANDATORY_SLOTS.map((s) => (
        <li key={s} className="flex items-baseline gap-2.5 py-2">
          <span className="type-label min-w-0 flex-1 text-text">{SLOT_LABELS[s]}</span>
          {draft[s].length > 0 ? (
            <ul className="type-body flex min-w-0 flex-[2] flex-col gap-0.5 text-text">
              {draft[s].map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          ) : (
            <span
              className="mark-unsourced shrink-0 self-center"
              role="img"
              aria-label="not yet resolved"
            />
          )}
        </li>
      ))}
    </ul>
  );
}

function SectionBlock({
  section,
  collapsible,
}: {
  section: ProtocolSection;
  collapsible: boolean;
}) {
  return (
    <details
      open={!collapsible}
      className="border-t border-border pt-2.5 first:border-0 first:pt-0"
    >
      <summary className="type-legend cursor-pointer text-text-muted">
        {section.heading}
      </summary>
      {section.lines.length > 1 ? (
        <ul className="mt-1 flex flex-col gap-1">
          {section.lines.map((line, i) => (
            <li key={i} className="type-body text-text">
              {line}
            </li>
          ))}
        </ul>
      ) : (
        <p className="type-body mt-1 text-text">{section.lines[0]}</p>
      )}
    </details>
  );
}
